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
    echeance = echeance_du_jeton(acces) if acces else None
    maintenant = dj_timezone.now()

    if not acces and not (refresh and refresh.is_set):
        etat = "auth_required"
    elif echeance is not None and echeance <= maintenant:
        # Expiré mais renouvelable : ce n'est pas une panne.
        etat = "renouvelable" if (refresh and refresh.is_set) else "auth_required"
    else:
        etat = "valide"

    memo = (connector.config or {}).get("shield_auth") or {}
    return {
        "etat": etat,
        "access_present": bool(acces),
        "expire_le": echeance.isoformat() if echeance else None,
        "expiration_connue": echeance is not None,
        "renouvellement_automatique": bool(refresh and refresh.is_set),
        "refresh_present": bool(refresh and refresh.is_set),
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
            _memoriser(connector, dernier_echec=dj_timezone.now().isoformat(),
                       cause_dernier_echec="refresh_absent")
            return False, ("Aucun jeton de renouvellement enregistré : la session ne peut pas "
                           "se prolonger seule. Déposez le couple access + refresh sur la fiche "
                           "de la source.")

        base = connector.base_url or ""
        if not base:
            return False, "URL de base absente : impossible d'appeler le renouvellement."

        ok, cause, charge = _appel_refresh(base, refresh)
        if not ok:
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
    return {
        "refresh_refuse": ("Le jeton de renouvellement est refusé par Shield : expiré ou révoqué. "
                           "Une réauthentification manuelle est nécessaire."),
        "quota_refresh": ("Shield limite le débit des renouvellements. Réessayez dans une minute — "
                          "sans multiplier les tentatives, elles aggravent la limite."),
        "reponse_illisible": "Réponse de renouvellement illisible.",
    }.get(cause, f"Renouvellement impossible ({cause}).")


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
