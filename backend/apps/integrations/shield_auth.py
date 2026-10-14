"""Authentification Shield permanente : renouvellement automatique du jeton.

CE QUE LA DOCUMENTATION SHIELD PERMET, vérifié sur le schéma OpenAPI live
(https://api.kaydanshield.com/api/schema/, 461 chemins) :

  POST /api/v1/auth/token/refresh/   documenté
      requête  : {"refresh": "<jeton>"}                     (TokenRefreshRequest)
      réponse  : {"access": "...", "refresh": "..."}        (TokenRefresh, les DEUX requis)

  Le refresh renvoie donc un NOUVEAU refresh : la rotation est active côté Shield.
  Ne persister que l'access reviendrait à jeter la clé du prochain renouvellement,
  et l'authentification redeviendrait manuelle au premier cycle.

  POST /api/v1/auth/login/           déclaré, mais SANS aucun corps documenté —
      ni requête, ni réponse. L'obtention initiale du couple ne peut donc pas être
      implémentée d'après la documentation sans inventer sa charge utile. Le premier
      couple est déposé à la main sur la fiche de la source ; tout le reste est
      automatique.

  POST /api/v1/auth/api-keys/        existe, portée `integration` (« Intégration
      tierce »), secret rendu « une fois, et une seule », `expires_at` nullable donc
      potentiellement sans expiration. Ce serait la voie préférable — sauf qu'AUCUN
      des 461 chemins ne déclare de schéma de sécurité pour une clé d'API (seuls
      `jwtAuth` et `cookieAuth` existent) et qu'aucun en-tête de présentation n'est
      documenté. L'employer exigerait d'inventer un nom d'en-tête : écarté.

CADENCE — la description du refresh chez Shield est un avertissement direct :
« deux rechargements suffisaient à épuiser le quota d'une minute ». Le renouvellement
a son propre quota, et une page qui rouvre avec un jeton expiré déclenche autant de
renouvellements qu'elle a de requêtes en vol. Le verrou de ce module n'est donc pas
une élégance : sans lui, plusieurs workers gunicorn grilleraient ce quota et Shield
refuserait jusqu'à la connexion elle-même.

ÉCHÉANCE — elle n'est pas renvoyée par l'API. On la lit dans le claim `exp` du jeton
d'accès, qui est un JWT. La signature n'est PAS vérifiée et n'a pas à l'être : on ne
décide rien de sensible avec cette valeur, on choisit seulement le moment de
renouveler. Shield reste seul juge de la validité.
"""

from __future__ import annotations

import base64
import json
import logging
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from django.utils import timezone as dj_timezone

from .models import ConnectorCredential, CredentialKind

logger = logging.getLogger(__name__)

# Chemin documenté du renouvellement.
CHEMIN_REFRESH = "/api/v1/auth/token/refresh/"

# Chemin de CONNEXION, et le contrat que la documentation taisait.
#
# Le schéma OpenAPI déclare ce chemin sans aucun corps — ni requête, ni réponse —
# ce qui avait fait écarter cette voie : on ne devine pas une charge utile. Mais
# l'API, elle, répond. Un POST vide rend :
#     {"email": ["Ce champ est obligatoire."], "password": ["Ce champ est obligatoire."]}
# Le contrat est donc `email` + `password`, établi par l'interrogation du service
# et non par supposition.
CHEMIN_LOGIN = "/api/v1/auth/login/"

# On renouvelle AVANT l'expiration : un jeton qui expire pendant le vol d'une
# requête produirait un 401 évitable, et donc un aller-retour de plus.
MARGE_AVANT_EXPIRATION = 120  # secondes

# Un renouvellement ne doit pas hériter du budget d'une collecte : c'est un appel
# unique et court, sur le chemin critique de toutes les autres requêtes.
DELAI_REFRESH = 10

# Verrous par connecteur. Le processus gunicorn est multi-thread ; ce verrou empêche
# deux threads du MÊME worker de renouveler en parallèle. Entre workers, la
# protection vient du contrôle « le jeton a-t-il déjà changé ? » après acquisition,
# relu depuis la base.
_verrous: dict[str, threading.Lock] = {}
_verrou_du_registre = threading.Lock()


def _verrou_pour(connector) -> threading.Lock:
    cle = str(connector.pk)
    with _verrou_du_registre:
        if cle not in _verrous:
            _verrous[cle] = threading.Lock()
        return _verrous[cle]


# ── Lecture du jeton ─────────────────────────────────────────────────────────


def echeance_du_jeton(jeton: str) -> datetime | None:
    """Instant d'expiration lu dans le claim `exp`, sans vérifier la signature.

    Rend None sur tout jeton qui n'est pas un JWT lisible — on traitera alors le
    jeton comme « échéance inconnue » plutôt que d'inventer une durée de vie.
    """
    if not jeton or jeton.count(".") != 2:
        return None
    charge = jeton.split(".")[1]
    charge += "=" * (-len(charge) % 4)  # base64url sans padding
    try:
        claims = json.loads(base64.urlsafe_b64decode(charge))
        exp = claims.get("exp")
        return datetime.fromtimestamp(float(exp), tz=timezone.utc) if exp else None
    except Exception:  # noqa: BLE001 — jeton opaque ou tronqué : échéance inconnue
        return None


def _identifiant(connector, kind: str) -> ConnectorCredential | None:
    return connector.credentials.filter(kind=kind).order_by("-created_at").first()


def _secret(connector, kind: str) -> str:
    cred = _identifiant(connector, kind)
    if cred is None or not cred.is_set:
        return ""
    try:
        return cred.secret
    except Exception:  # noqa: BLE001 — clé de chiffrement changée
        logger.warning("Secret Shield illisible (%s) : clé de chiffrement modifiée ?", kind)
        return ""


def identifiants_de_service(connector) -> tuple[str, str]:
    """(adresse, mot de passe) du compte de service, ou ("", "").

    L'adresse vit dans `config` — ce n'est pas un secret et la fiche doit pouvoir
    l'afficher pour qu'on sache QUEL compte porte la liaison. Le mot de passe vit
    dans les identifiants chiffrés, et n'en ressort jamais.
    """
    email = str((connector.config or {}).get("service_email") or "")
    return email, _secret(connector, CredentialKind.PASSWORD)


def reconnecter(connector) -> tuple[bool, str]:
    """Rétablit la session par identifiants. C'est le filet qui rend la liaison permanente.

    Appelé quand la chaîne de jetons est rompue — refresh expiré, révoqué, ou
    jamais déposé. Sans ce filet, la seule issue était qu'un humain recolle un
    couple de jetons à la main, ce qui condamnait la liaison à mourir à chaque
    période d'inactivité un peu longue.
    """
    email, mot_de_passe = identifiants_de_service(connector)
    if not (email and mot_de_passe):
        return False, ("Aucun compte de service enregistré : la session ne peut pas se "
                       "rétablir seule. Déposez une adresse et un mot de passe de service "
                       "sur la fiche de la source.")
    base = connector.base_url or ""
    if not base:
        return False, "URL de base absente : impossible d'appeler la connexion."

    ok, cause, charge = _appel_login(base, email, mot_de_passe)
    if not ok:
        _memoriser(connector, dernier_echec=dj_timezone.now().isoformat(),
                   cause_dernier_echec=cause)
        _tracer(connector, succes=False, cause=f"login:{cause}")
        return False, _explication(cause)

    acces = charge.get("access") or charge.get("token") or ""
    refresh = charge.get("refresh") or ""
    if not acces:
        _memoriser(connector, dernier_echec=dj_timezone.now().isoformat(),
                   cause_dernier_echec="access_absent_de_la_reponse")
        _tracer(connector, succes=False, cause="login:access_absent")
        return False, "Shield a accepté la connexion sans renvoyer de jeton d'accès."

    _deposer(connector, CredentialKind.API_TOKEN, acces, "Jeton d'accès Shield (auto)")
    if refresh:
        _deposer(connector, CredentialKind.OAUTH_REFRESH, refresh,
                 "Jeton de renouvellement Shield (auto)")
    echeance = echeance_du_jeton(acces)
    _memoriser(connector,
               derniere_authentification=dj_timezone.now().isoformat(),
               derniere_reconnexion=dj_timezone.now().isoformat(),
               expire_le=echeance.isoformat() if echeance else None,
               dernier_echec=None, cause_dernier_echec=None)
    _tracer(connector, succes=True, cause="login")
    return True, "Session Shield rétablie par le compte de service."


def _deposer(connector, kind: str, valeur: str, libelle: str) -> None:
    """Écrit un secret en REMPLAÇANT celui du même type (contrainte d'unicité)."""
    cred, _ = ConnectorCredential.objects.get_or_create(connector=connector, kind=kind)
    cred.label = libelle
    cred.set_secret(valeur)
    cred.save()


def etat_auth(connector) -> dict:
    """Ce qu'on peut dire de la session, sans jamais révéler un jeton.

    Destiné à l'API et donc à l'écran : uniquement des états, des dates et des
    masques.
    """
    acces = _secret(connector, CredentialKind.API_TOKEN)
    refresh = _identifiant(connector, CredentialKind.OAUTH_REFRESH)
    renouvelable = bool(refresh and refresh.is_set)
    echeance = echeance_du_jeton(acces) if acces else None
    memo = (connector.config or {}).get("shield_auth") or {}

    # Le compte de service change la nature de la liaison : tant qu'il répond, la
    # session se rétablit seule, même après des semaines d'inactivité. Un refresh
    # mort cesse d'être terminal.
    email_service, mdp_service = identifiants_de_service(connector)
    compte_de_service = bool(email_service and mdp_service)
    compte_refuse = memo.get("cause_dernier_echec") == "identifiants_refuses"

    # Un refresh que Shield vient de refuser est encore « présent » en base, mais il
    # est mort : le présenter comme renouvelable ferait attendre un renouvellement
    # qui ne viendra jamais. On tient compte de ce qu'on a appris.
    refresh_condamne = memo.get("cause_dernier_echec") == "refresh_refuse"

    # Un compte de service qui répond encore rend la liaison récupérable, quoi
    # qu'il advienne des jetons.
    recuperable = compte_de_service and not compte_refuse

    if (refresh_condamne or not renouvelable) and not recuperable:
        # Sans recours possible, seul un access encore valide sauve la session.
        expire = echeance is not None and echeance <= dj_timezone.now()
        etat = "auth_required" if (not acces or expire) else "valide"
    elif not acces or (echeance is not None and echeance <= dj_timezone.now()):
        # Expiré, ou jamais déposé, mais renouvelable : ce n'est pas une panne — le
        # prochain appel s'en chargera tout seul.
        etat = "renouvelable"
    else:
        etat = "valide"

    return {
        "etat": etat,
        "access_present": bool(acces),
        "expire_le": echeance.isoformat() if echeance else None,
        "expiration_connue": echeance is not None,
        # « Automatique » suppose un refresh vivant : un refresh refusé ne renouvelle
        # plus rien, l'annoncer actif serait une fausse promesse.
        "renouvellement_automatique": (renouvelable and not refresh_condamne) or recuperable,
        "refresh_present": renouvelable,
        # Ce que l'écran doit pouvoir dire : la liaison tient-elle toute seule,
        # et par quel moyen ?
        "compte_de_service": compte_de_service,
        "compte_de_service_refuse": compte_refuse,
        "liaison_permanente": recuperable,
        "service_email": email_service,
        "derniere_reconnexion": memo.get("derniere_reconnexion"),
        "derniere_authentification": memo.get("derniere_authentification"),
        "dernier_echec": memo.get("dernier_echec"),
        "cause_dernier_echec": memo.get("cause_dernier_echec"),
    }


def jeton_utilisable(connector) -> str:
    """Le jeton d'accès s'il est encore bon, chaîne vide sinon."""
    acces = _secret(connector, CredentialKind.API_TOKEN)
    if not acces:
        return ""
    echeance = echeance_du_jeton(acces)
    if echeance is None:
        # Échéance inconnue : on l'utilise, et c'est le 401 de Shield qui tranchera.
        return acces
    reste = (echeance - dj_timezone.now()).total_seconds()
    return acces if reste > MARGE_AVANT_EXPIRATION else ""


# ── Renouvellement ───────────────────────────────────────────────────────────


def _origine(base_url: str) -> str:
    """L'URL saisie finit par /api/v1 ; les chemins d'auth le portent déjà."""
    origine = base_url.rstrip("/")
    return origine[: -len("/api/v1")] if origine.endswith("/api/v1") else origine


def _poster(url: str, charge: dict) -> tuple[bool, str, dict]:
    """POST JSON, avec les mêmes causes qualifiées partout."""
    corps = json.dumps(charge).encode()
    requete = urllib.request.Request(
        url, data=corps, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": "k-insight"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=DELAI_REFRESH) as reponse:  # noqa: S310
            return True, "", json.loads(reponse.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401, 403):
            return False, "identifiants_refuses" if url.endswith(CHEMIN_LOGIN) else "refresh_refuse", {}
        if exc.code == 429:
            return False, "quota_refresh", {}
        return False, f"http_{exc.code}", {}
    except (TimeoutError, urllib.error.URLError) as exc:
        raison = getattr(exc, "reason", exc)
        if isinstance(raison, ssl.SSLCertVerificationError):
            return False, "certificats_invalides", {}
        return False, f"reseau_{type(raison).__name__}", {}
    except json.JSONDecodeError:
        return False, "reponse_illisible", {}


def _appel_login(base_url: str, email: str, mot_de_passe: str) -> tuple[bool, str, dict]:
    """Connexion par identifiants. C'est ce qui rend la liaison PERMANENTE.

    Le renouvellement par jeton est une chaîne mortelle : la rotation est active
    chez Shield, et il suffit que l'application reste inactive plus longtemps que
    la durée de vie du refresh pour que la chaîne casse définitivement. C'est
    exactement ce qui s'est produit — jeton déposé le 21/09, chaîne rompue, et
    plus aucun moyen de repartir sans qu'un humain recolle un couple à la main.

    Avec un compte de service, la session se rétablit seule.
    """
    return _poster(_origine(base_url) + CHEMIN_LOGIN,
                   {"email": email, "password": mot_de_passe})


def _appel_refresh(base_url: str, refresh: str) -> tuple[bool, str, dict]:
    """POST documenté vers Shield. Rend (succès, cause, charge)."""
    # L'utilisateur saisit l'URL documentée, qui se termine par /api/v1 ; le chemin
    # du renouvellement porte déjà ce préfixe. On ramène donc la base à son origine
    # avant de concaténer, comme le fait le client pour tous les autres appels.
    origine = base_url.rstrip("/")
    if origine.endswith("/api/v1"):
        origine = origine[: -len("/api/v1")]
    url = origine + CHEMIN_REFRESH
    corps = json.dumps({"refresh": refresh}).encode()
    requete = urllib.request.Request(
        url, data=corps, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": "k-insight"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=DELAI_REFRESH) as reponse:  # noqa: S310
            return True, "", json.loads(reponse.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return False, "refresh_refuse", {}
        if exc.code == 429:
            return False, "quota_refresh", {}
        return False, f"http_{exc.code}", {}
    except (TimeoutError, urllib.error.URLError) as exc:
        raison = getattr(exc, "reason", exc)
        if isinstance(raison, ssl.SSLCertVerificationError):
            # Même diagnostic que dans `shield_client` : symptôme cryptique, cause
            # banale. Le fondre dans « injoignable » ferait chercher une panne de
            # réseau alors que c'est le magasin de certificats qui manque.
            return False, "certificats_invalides", {}
        return False, f"reseau_{type(raison).__name__}", {}
    except json.JSONDecodeError:
        return False, "reponse_illisible", {}


def _memoriser(connector, **champs) -> None:
    config = dict(connector.config or {})
    config["shield_auth"] = {**(config.get("shield_auth") or {}), **champs}
    connector.config = config
    connector.save(update_fields=["config", "updated_at"])


def renouveler(connector, *, force: bool = False) -> tuple[bool, str]:
    """Renouvelle le couple de jetons. Un seul renouvellement à la fois.

    Rend (succès, message). `force=False` : si un autre appelant vient de
    renouveler pendant qu'on attendait le verrou, on réutilise SON jeton au lieu
    d'en demander un second — c'est le point qui protège le quota de Shield.
    """
    with _verrou_pour(connector):
        connector.refresh_from_db(fields=["config"])
        if not force and jeton_utilisable(connector):
            return True, "Jeton déjà renouvelé par un autre appel."

        refresh = _secret(connector, CredentialKind.OAUTH_REFRESH)
        if not refresh:
            # Pas de jeton à renouveler : si un compte de service existe, on se
            # connecte plutôt que de réclamer un collage manuel.
            if all(identifiants_de_service(connector)):
                return reconnecter(connector)
            _memoriser(connector, dernier_echec=dj_timezone.now().isoformat(),
                       cause_dernier_echec="refresh_absent")
            return False, ("Aucun jeton de renouvellement enregistré : la session ne peut pas "
                           "se prolonger seule. Déposez un compte de service, ou un couple "
                           "access + refresh, sur la fiche de la source.")

        base = connector.base_url or ""
        if not base:
            _memoriser(connector, dernier_echec=dj_timezone.now().isoformat(),
                       cause_dernier_echec="base_absente")
            return False, "URL de base absente : impossible d'appeler le renouvellement."

        ok, cause, charge = _appel_refresh(base, refresh)
        if not ok:
            # LE FILET. Un refresh refusé était jusqu'ici terminal : la fiche
            # passait en « réauthentification requise » et attendait un humain.
            # Avec un compte de service, on repart par la connexion — c'est ce
            # qui transforme une chaîne mortelle en liaison permanente.
            #
            # Seul un REFUS déclenche le filet. Un quota dépassé ou un réseau
            # coupé ne sont pas des refus : se reconnecter alors gaspillerait une
            # tentative de connexion sur une panne passagère, et pourrait faire
            # verrouiller le compte.
            if cause == "refresh_refuse" and all(identifiants_de_service(connector)):
                _tracer(connector, succes=False, cause="refresh_refuse_bascule_login")
                return reconnecter(connector)
            _memoriser(connector, dernier_echec=dj_timezone.now().isoformat(),
                       cause_dernier_echec=cause)
            _tracer(connector, succes=False, cause=cause)
            return False, _explication(cause)

        acces = charge.get("access") or ""
        nouveau_refresh = charge.get("refresh") or ""
        if not acces:
            _memoriser(connector, dernier_echec=dj_timezone.now().isoformat(),
                       cause_dernier_echec="access_absent_de_la_reponse")
            _tracer(connector, succes=False, cause="access_absent_de_la_reponse")
            return False, "Shield a répondu sans jeton d'accès : réponse inattendue."

        _deposer(connector, CredentialKind.API_TOKEN, acces, "Jeton d'accès Shield (auto)")
        if nouveau_refresh:
            # La rotation est active : sans cette ligne, le prochain renouvellement
            # présenterait un refresh déjà consommé.
            _deposer(connector, CredentialKind.OAUTH_REFRESH, nouveau_refresh,
                     "Jeton de renouvellement Shield (auto)")

        echeance = echeance_du_jeton(acces)
        _memoriser(
            connector,
            derniere_authentification=dj_timezone.now().isoformat(),
            expire_le=echeance.isoformat() if echeance else None,
            dernier_echec=None,
            cause_dernier_echec=None,
        )
        _tracer(connector, succes=True, cause="")
        return True, "Session Shield renouvelée."


def _explication(cause: str) -> str:
    if cause.startswith("reseau_"):
        # Ni refus, ni faute de saisie : le dire évite d'envoyer chercher un
        # nouveau jeton là où c'est la sortie réseau du conteneur qui manque.
        return ("Shield est injoignable depuis le backend : ce n'est pas un refus "
                "d'authentification. Réessayez, puis vérifiez l'URL de base et la sortie "
                "réseau du conteneur.")
    if cause.startswith("http_"):
        return (f"Shield a répondu {cause.removeprefix('http_')} au renouvellement : "
                "réponse inattendue de la plateforme.")
    return {
        "refresh_refuse": ("Le jeton de renouvellement est refusé par Shield : expiré ou révoqué. "
                           "Une réauthentification manuelle est nécessaire."),
        "quota_refresh": ("Shield limite le débit des renouvellements. Réessayez dans une minute — "
                          "sans multiplier les tentatives, elles aggravent la limite."),
        "reponse_illisible": "Réponse de renouvellement illisible.",
        "base_absente": "URL de base absente : impossible d'appeler le renouvellement.",
        "refresh_absent": ("Aucun jeton de renouvellement enregistré : déposez un compte de "
                           "service, ou un couple access + refresh."),
        "identifiants_refuses": ("Shield refuse le compte de service : adresse ou mot de passe "
                                 "incorrect, ou compte désactivé. La liaison ne peut plus se "
                                 "rétablir seule tant que ce compte n'est pas corrigé."),
        "certificats_invalides": ("Certificat TLS de Shield non vérifiable : le magasin de "
                                  "certificats de l'environnement est absent ou incomplet. "
                                  "Le défaut est chez nous, pas chez Shield."),
    }.get(cause, f"Renouvellement impossible ({cause}).")


def _explication_depot(cause: str) -> str:
    """Même refus, autre contexte : ici l'opérateur vient DE saisir un couple.

    Lui répondre « une réauthentification manuelle est nécessaire » alors qu'il
    la tente à l'instant n'aiderait pas ; ce qu'il doit savoir, c'est que le
    jeton collé ne vaut rien et que la session en place n'a pas été touchée.
    """
    if cause == "refresh_refuse":
        return ("Shield refuse ce jeton de renouvellement : expiré, révoqué, ou copié "
                "incomplètement. Rien n'a été enregistré, la session en place est inchangée.")
    return _explication(cause)


def _tracer(connector, *, succes: bool, cause: str) -> None:
    """Trace le renouvellement — jamais le jeton, ni sa longueur, ni son masque."""
    from apps.audit.models import AccessLog

    AccessLog.record(
        user=None,
        action="shield.auth.refresh",
        metric_key=connector.source.slug if connector.source_id else "",
        payload={"succes": succes, **({"cause": cause} if cause else {})},
    )


def jeton_pour_appel(connector) -> tuple[str, str]:
    """Le jeton à présenter maintenant, en renouvelant si besoin.

    Rend (jeton, message). Un jeton vide signifie qu'aucune session n'est
    disponible : l'appelant doit rendre un état `auth_required`, pas réessayer.
    """
    jeton = jeton_utilisable(connector)
    if jeton:
        return jeton, ""
    ok, message = renouveler(connector)
    return (jeton_utilisable(connector) or _secret(connector, CredentialKind.API_TOKEN), "") if ok else ("", message)


def deposer_couple(connector, *, acces: str, refresh: str) -> dict:
    """Dépose un couple access + refresh, en remplaçant celui en place.

    Exiger les DEUX est délibéré : un access seul redonnerait une session qui
    expire sans recours, c'est-à-dire le problème qu'on cherche à supprimer.

    Écrit sans rien vérifier : réservé aux appels qui ont DÉJÀ obtenu le couple
    de Shield. Un couple saisi à la main passe par `verifier_et_deposer`.
    """
    _deposer(connector, CredentialKind.API_TOKEN, acces, "Jeton d'accès Shield")
    _deposer(connector, CredentialKind.OAUTH_REFRESH, refresh, "Jeton de renouvellement Shield")
    echeance = echeance_du_jeton(acces)
    _memoriser(
        connector,
        derniere_authentification=dj_timezone.now().isoformat(),
        expire_le=echeance.isoformat() if echeance else None,
        dernier_echec=None,
        cause_dernier_echec=None,
    )
    _tracer(connector, succes=True, cause="depot_manuel")
    return etat_auth(connector)


def verifier_et_deposer(connector, *, acces: str, refresh: str) -> tuple[bool, str, str]:
    """Éprouve le couple saisi auprès de Shield AVANT de l'écrire.

    Rend (succès, cause, message). Écrire d'abord et vérifier ensuite était le
    défaut à corriger : un couple erroné s'enregistrait, la fiche annonçait
    « Connecté », et le refus n'apparaissait qu'au premier appel métier — un vert
    non mérité, exactement ce que l'ADR-0007 interdit. On appelle donc le
    renouvellement documenté avec le refresh fourni : Shield seul dit s'il vaut
    quelque chose.

    Deux conséquences voulues :

      Le jeton d'accès finalement enregistré est celui que Shield vient d'émettre,
        pas celui qui a été collé. Il est vivant par construction et son `exp` est
        lisible, donc l'échéance affichée est exacte. Le champ « access » du
        formulaire reste exigé — un opérateur qui n'a qu'un refresh n'a pas de
        couple, et le collage à l'aveugle d'un seul jeton est justement ce qu'on
        refuse.

      Sur refus, RIEN n'est écrit et le mémo n'est pas touché. La session déjà en
        place — peut-être saine — ne doit pas être condamnée par une frappe
        malheureuse.
    """
    base = connector.base_url or ""
    if not base:
        return False, "base_absente", ("URL de base absente : impossible de vérifier le couple "
                                       "auprès de Shield. Renseignez-la avant de réauthentifier.")

    ok, cause, charge = _appel_refresh(base, refresh)
    if not ok:
        _tracer(connector, succes=False, cause=f"depot_refuse:{cause}")
        return False, cause, _explication_depot(cause)

    acces_emis = charge.get("access") or ""
    if not acces_emis:
        _tracer(connector, succes=False, cause="depot_refuse:access_absent_de_la_reponse")
        return False, "access_absent_de_la_reponse", ("Shield a accepté le renouvellement mais n'a "
                                                      "renvoyé aucun jeton d'accès : réponse inattendue, "
                                                      "rien n'a été enregistré.")

    # La rotation est active côté Shield : le refresh renvoyé remplace celui qui
    # vient d'être consommé. Conserver le refresh collé le rendrait inutilisable
    # au cycle suivant.
    deposer_couple(connector, acces=acces_emis, refresh=charge.get("refresh") or refresh)
    return True, "", "Session Shield rétablie et vérifiée auprès de Shield."


def enregistrer_le_compte_de_service(connector, *, email: str, mot_de_passe: str) -> tuple[bool, str, str]:
    """Éprouve le compte AUPRÈS DE SHIELD avant de l'écrire.

    Même discipline que pour le dépôt d'un couple de jetons, et pour la même
    raison : écrire d'abord ferait annoncer « liaison permanente » à une fiche
    dont le compte est faux, et le refus n'apparaîtrait qu'au premier appel
    métier. On se connecte donc pour de vrai ; les jetons rapportés par cette
    connexion sont ceux qu'on garde, vivants par construction.

    Sur refus, RIEN n'est écrit : une frappe malheureuse ne doit pas détruire un
    compte de service qui fonctionnait.
    """
    base = connector.base_url or ""
    if not base:
        return False, "base_absente", ("URL de base absente : impossible de vérifier le compte "
                                       "auprès de Shield.")

    ok, cause, charge = _appel_login(base, email, mot_de_passe)
    if not ok:
        _tracer(connector, succes=False, cause=f"compte_service_refuse:{cause}")
        return False, cause, _explication(cause)

    acces = charge.get("access") or charge.get("token") or ""
    if not acces:
        _tracer(connector, succes=False, cause="compte_service:access_absent")
        return False, "access_absent_de_la_reponse", ("Shield a accepté la connexion mais n'a "
                                                      "renvoyé aucun jeton d'accès : rien n'a été "
                                                      "enregistré.")

    config = dict(connector.config or {})
    config["service_email"] = email
    connector.config = config
    connector.save(update_fields=["config", "updated_at"])
    _deposer(connector, CredentialKind.PASSWORD, mot_de_passe, "Mot de passe du compte de service Shield")
    _deposer(connector, CredentialKind.API_TOKEN, acces, "Jeton d'accès Shield (auto)")
    if charge.get("refresh"):
        _deposer(connector, CredentialKind.OAUTH_REFRESH, charge["refresh"],
                 "Jeton de renouvellement Shield (auto)")
    echeance = echeance_du_jeton(acces)
    _memoriser(connector,
               derniere_authentification=dj_timezone.now().isoformat(),
               derniere_reconnexion=dj_timezone.now().isoformat(),
               expire_le=echeance.isoformat() if echeance else None,
               dernier_echec=None, cause_dernier_echec=None)
    _tracer(connector, succes=True, cause="compte_service_enregistre")
    return True, "", ("Compte de service vérifié et enregistré : la liaison se rétablira "
                      "désormais seule.")


def statut_http(cause: str, *, ok: bool) -> int:
    """Le code HTTP qui dit la vérité sur un échec d'authentification.

    Tout renvoyer en 400 ou en 409 obligerait l'écran à deviner : un quota
    dépassé se réessaie dans une minute, un refresh révoqué jamais, et Shield
    injoignable n'est pas un refus du tout.

    `ok` est demandé séparément parce qu'un échec sans cause identifiée doit
    rester un échec : le déduire de la seule chaîne vide rendrait un 200 pour un
    renouvellement raté.
    """
    if ok:
        return 200
    if cause == "refresh_refuse":
        # Un 401 comme un 403 de Shield disent la même chose du jeton : il est
        # refusé. On les rend en 401 et on garde 403 pour les droits K-Insight,
        # sinon l'écran ne saurait plus si c'est l'opérateur ou le jeton qui est
        # en cause.
        return 401
    if cause == "quota_refresh":
        return 429
    if cause == "identifiants_refuses":
        return 401   # Shield a refusé le compte lui-même.
    if cause in ("refresh_absent", "base_absente"):
        return 409  # Rien à renouveler : état de la source, pas refus de Shield.
    if cause.startswith("reseau_") or cause == "certificats_invalides":
        return 503  # Shield injoignable : ni refus, ni erreur de saisie.
    return 502  # Shield a répondu autre chose que prévu.
