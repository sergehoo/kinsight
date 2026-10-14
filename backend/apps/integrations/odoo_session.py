"""Liaison permanente Odoo : compte technique, uid partagé, réauthentification seule.

CE QUI REND LA LIAISON PERMANENTE. Pas un jeton : Odoo n'en émet pas. Un compte
technique dédié et sa clé d'API, stockés chiffrés, suffisent à rouvrir une
session à tout moment — `common.authenticate` rend un uid, et chaque appel
repasse la clé. Il n'y a donc ni access, ni refresh, ni rotation à gérer, et ce
module n'en fabrique aucun : il garde l'uid en cache, le redemande quand Odoo le
refuse, et c'est tout.

POURQUOI UN GESTIONNAIRE PARTAGÉ. La première version gardait l'uid DANS le
client — or `build_client` crée un client par requête web. L'uid mourait donc
avec la requête, et chaque écran ouvert se réauthentifiait autant de fois qu'il
avait de cartes. Ici l'uid vit au niveau du processus et, quand le cache Django
est Redis (`REDIS_URL`), au niveau de tous les workers.

SINGLE-FLIGHT. Quand plusieurs requêtes découvrent en même temps qu'il faut se
réauthentifier, UNE seule appelle Odoo ; les autres attendent et réutilisent
l'uid obtenu. Dans un processus, un verrou le garantit. Entre processus, un
verrou posé dans le cache partagé (`cache.add`) le fait — borné dans le temps :
si le détenteur meurt, les autres finissent par s'authentifier eux-mêmes plutôt
que d'attendre indéfiniment.

REFROIDISSEMENT. Après un REFUS d'identifiants, on ne retente pas `authenticate`
avant un délai : chaque carte d'un écran rejouerait sinon le refus, et une
politique de verrouillage côté Odoo finirait par bloquer le compte technique.
Une panne réseau, elle, ne pose aucun refroidissement — ce n'est pas un refus.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone as dj_timezone

from .models import ConnectorCredential, CredentialKind, SourceStatus
from .odoo_client import ClientOdoo, OdooError

# L'uid ne change pas tant que le compte existe ; le relire coûte un aller-retour.
# Court quand même : un compte désactivé doit cesser d'être servi assez vite, même
# si aucun appel n'a encore échoué.
TTL_UID = 10 * 60
REFROIDISSEMENT_REFUS = 60
ATTENTE_MAX_VERROU = 5.0
DUREE_VERROU = 15
# Au-delà, une vérification réussie ne prouve plus grand-chose de l'état présent.
FRAICHEUR_VERIFICATION = timedelta(hours=24)
# Essais d'enregistrement ratés tolérés par fenêtre : un formulaire rejoué en
# boucle ne doit pas servir à faire verrouiller le compte technique côté Odoo.
ESSAIS_ENREGISTREMENT = 5
FENETRE_ENREGISTREMENT = 10 * 60

# Les refus qui portent un VERDICT sur le compte : identifiants, base. Les autres
# causes — réseau, délai, protocole — disent l'état du chemin, pas du compte.
CAUSES_DE_REFUS = ("auth", "base", "config")


def _empreinte(url: str, base: str, login: str, cle: str) -> str:
    """Clé de cache dérivée des identifiants, SANS les révéler.

    HMAC avec la clé secrète Django : un condensat simple d'un mot de passe dans
    une clé Redis se casserait par dictionnaire. Changer de clé d'API change
    l'empreinte — donc la session — sans qu'on ait à invalider quoi que ce soit.
    """
    message = "\x1f".join((url, base, login, cle)).encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()[:32]


def _cache_get(cle: str):
    try:
        return cache.get(cle)
    except Exception:  # noqa: BLE001 — cache injoignable : on reste en local
        return None


def _cache_set(cle: str, valeur, ttl: int) -> None:
    try:
        cache.set(cle, valeur, ttl)
    except Exception:  # noqa: BLE001
        pass


def _cache_delete(cle: str) -> None:
    try:
        cache.delete(cle)
    except Exception:  # noqa: BLE001
        pass


def _cache_add(cle: str, valeur, ttl: int) -> bool:
    """Pose un verrou partagé. Cache injoignable : on fait comme si on l'avait,
    le verrou de processus protège déjà ce worker."""
    try:
        return bool(cache.add(cle, valeur, ttl))
    except Exception:  # noqa: BLE001
        return True


class SessionOdoo:
    """L'uid d'UN jeu d'identifiants, partagé par toutes les requêtes."""

    def __init__(self, empreinte: str):
        self.empreinte = empreinte
        self._cle_uid = f"odoo:uid:{empreinte}"
        self._cle_refus = f"odoo:refus:{empreinte}"
        self._cle_verrou = f"odoo:verrou:{empreinte}"
        self._verrou = threading.Lock()
        self._uid: int | None = None
        self._expire = 0.0
        self._refus_jusqu_a = 0.0
        self._refus: OdooError | None = None
        # Compteur observable : c'est ce que les tests de single-flight mesurent.
        self.authentifications = 0

    def _local(self) -> int | None:
        if self._uid and time.monotonic() < self._expire:
            return self._uid
        return None

    def _partage(self) -> int | None:
        uid = _cache_get(self._cle_uid)
        if isinstance(uid, int) and uid > 0:
            self._uid, self._expire = uid, time.monotonic() + TTL_UID
            return uid
        return None

    def _refroidi(self) -> OdooError | None:
        if time.monotonic() < self._refus_jusqu_a and self._refus is not None:
            return self._refus
        partage = _cache_get(self._cle_refus)
        if partage:
            return OdooError(str(partage), "Odoo a refusé ce compte il y a moins d'une minute : "
                                           "nouvelle tentative différée pour ne pas le faire "
                                           "verrouiller.")
        return None

    def uid(self, client: ClientOdoo) -> int:
        uid = self._local() or self._partage()
        if uid:
            return uid
        refus = self._refroidi()
        if refus is not None:
            raise refus

        with self._verrou:
            # Un autre thread a pu s'authentifier pendant qu'on attendait.
            uid = self._local() or self._partage()
            if uid:
                return uid

            if not _cache_add(self._cle_verrou, 1, DUREE_VERROU):
                # Un AUTRE processus s'authentifie : on attend son résultat.
                limite = time.monotonic() + ATTENTE_MAX_VERROU
                while time.monotonic() < limite:
                    time.sleep(0.1)
                    uid = self._partage()
                    if uid:
                        return uid
                    refus = self._refroidi()
                    if refus is not None:
                        raise refus
                # Détenteur disparu ou trop lent : on s'authentifie nous-mêmes
                # plutôt que d'attendre indéfiniment.

            try:
                self.authentifications += 1
                uid = client.authentifier()
            except OdooError as exc:
                if exc.kind in CAUSES_DE_REFUS:
                    self._refus, self._refus_jusqu_a = exc, time.monotonic() + REFROIDISSEMENT_REFUS
                    _cache_set(self._cle_refus, exc.kind, REFROIDISSEMENT_REFUS)
                raise
            finally:
                _cache_delete(self._cle_verrou)

            self._uid, self._expire = uid, time.monotonic() + TTL_UID
            self._refus, self._refus_jusqu_a = None, 0.0
            _cache_set(self._cle_uid, uid, TTL_UID)
            return uid

    def invalider(self, uid: int | None = None) -> None:
        """Jette l'uid — sauf si un autre appel l'a DÉJÀ remplacé.

        Sans cette précaution, dix requêtes en échec simultané jetteraient
        chacune l'uid neuf obtenu par la première, et la réauthentification se
        produirait dix fois au lieu d'une.
        """
        with self._verrou:
            if uid is not None and self._uid is not None and self._uid != uid:
                return
            partage = _cache_get(self._cle_uid)
            if uid is None or partage in (None, uid):
                _cache_delete(self._cle_uid)
            self._uid, self._expire = None, 0.0

    def amorcer(self, uid: int) -> None:
        """Dépose un uid obtenu par une vérification : la première requête métier
        qui suit n'a pas à se réauthentifier."""
        with self._verrou:
            self._uid, self._expire = uid, time.monotonic() + TTL_UID
            self._refus, self._refus_jusqu_a = None, 0.0
        _cache_set(self._cle_uid, uid, TTL_UID)
        _cache_delete(self._cle_refus)


_sessions: dict[str, SessionOdoo] = {}
_verrou_registre = threading.Lock()


def session_pour(url: str, base: str, login: str, cle: str) -> SessionOdoo:
    empreinte = _empreinte(url, base, login, cle)
    with _verrou_registre:
        if empreinte not in _sessions:
            _sessions[empreinte] = SessionOdoo(empreinte)
        return _sessions[empreinte]


def _vider_les_sessions() -> None:
    """Pour les tests : repartir d'un registre vierge."""
    with _verrou_registre:
        _sessions.clear()


# ── Identifiants ─────────────────────────────────────────────────────────────


def _secret_de(connector, kind: str) -> str:
    cred = connector.credentials.filter(kind=kind).order_by("-created_at").first()
    if cred is None or not cred.is_set:
        return ""
    try:
        return cred.secret
    except Exception:  # noqa: BLE001 — clé de chiffrement changée : secret illisible
        return ""


def _present(connector, kind: str) -> bool:
    """Présence d'un secret, SANS le déchiffrer : l'état de la fiche est lu à
    chaque affichage et n'a jamais besoin du clair."""
    cred = connector.credentials.filter(kind=kind).order_by("-created_at").first()
    return bool(cred and cred.is_set)


def cle_api(connector) -> str:
    """La clé d'API, ou à défaut le mot de passe. Clé d'abord : c'est la voie
    recommandée pour un compte technique, révocable sans toucher au compte."""
    for kind in (CredentialKind.API_KEY, CredentialKind.API_TOKEN, CredentialKind.PASSWORD):
        valeur = _secret_de(connector, kind)
        if valeur:
            return valeur
    return ""


def _base_et_login(connector) -> tuple[str, str]:
    config = connector.config or {}
    base = _secret_de(connector, CredentialKind.DATABASE) or str(
        config.get("database") or config.get("db") or "")
    login = _secret_de(connector, CredentialKind.LOGIN) or str(
        config.get("login") or config.get("username") or "")
    return base, login


def identifiants_odoo(connector) -> tuple[str, str, str, str]:
    """(url, base, login, clé). Chiffrés d'abord ; `config` en repli.

    Le repli sert les connecteurs configurés AVANT que la base et le login ne
    soient chiffrés : ils continuent de fonctionner, et la première saisie par
    la fiche les migre — `enregistrer_compte_odoo` retire alors les valeurs en
    clair de `config`.
    """
    base, login = _base_et_login(connector)
    return (connector.base_url or "").rstrip("/"), base, login, cle_api(connector)


def client_pour(connector, *, delai: int | None = None, max_tentatives: int | None = None) -> ClientOdoo:
    """Client branché sur la session partagée de ces identifiants."""
    url, base, login, cle = identifiants_odoo(connector)
    options: dict[str, Any] = {}
    if delai is not None:
        options["delai"] = delai
    if max_tentatives is not None:
        options["max_tentatives"] = max_tentatives
    return ClientOdoo(url=url, base=base, login=login, cle=cle,
                      session=session_pour(url, base, login, cle), **options)


def masquer_login(login: str) -> str:
    """« service.rh@kaydan.tech » → « ser***@kaydan.tech ».

    Assez pour reconnaître QUEL compte porte la liaison, pas assez pour le
    reconstituer. Le domaine reste lisible : il dit à quelle organisation le
    compte appartient, ce qui est précisément ce qu'on vérifie d'un coup d'œil.
    """
    if not login:
        return ""
    local, arobase, domaine = login.partition("@")
    tete = local[:3] if len(local) > 3 else ""
    return f"{tete}***{arobase}{domaine}"


# ── Mémoire de la liaison ────────────────────────────────────────────────────


def _memo(connector) -> dict:
    return (connector.config or {}).get("odoo_auth") or {}


def _memoriser(connector, **champs) -> None:
    connector.refresh_from_db(fields=["config"])
    config = dict(connector.config or {})
    config["odoo_auth"] = {**(config.get("odoo_auth") or {}), **champs}
    connector.config = config
    connector.save(update_fields=["config", "updated_at"])


def _tracer(connector, *, action: str, succes: bool, cause: str = "", user=None) -> None:
    """Trace d'audit : l'issue et sa cause. Jamais le login, jamais la clé."""
    from apps.audit.models import AccessLog

    AccessLog.record(
        user=user,
        action=action,
        metric_key=connector.source.slug if connector.source_id else "",
        payload={"succes": succes, **({"cause": cause} if cause else {})},
    )


# ── Vérification ─────────────────────────────────────────────────────────────


def _eprouver(client: ClientOdoo) -> dict[str, Any]:
    """Les trois preuves, dans l'ordre : joignable, authentifié, autorisé.

    Lève `OdooError` à la première qui manque. Rend la version, l'uid et la
    latence de la séquence.
    """
    debut = time.monotonic()
    version = client.version()
    uid = client.authentifier()
    # Le client est sans session ici : on lui donne l'uid pour que l'appel métier
    # ne rejoue pas l'authentification.
    client._uid, client._uid_expire = uid, time.monotonic() + TTL_UID
    try:
        client.compter("hr.employee")
    except OdooError as exc:
        if exc.kind in ("droits", "absent"):
            raise OdooError("droits", "Le compte s'authentifie mais ne peut pas lire "
                                      "hr.employee : accordez-lui la lecture RH.") from exc
        raise
    return {
        "version": str(version.get("server_version") or ""),
        "uid": uid,
        "latence_ms": int((time.monotonic() - debut) * 1000),
    }


def verifier_odoo(connector, *, user=None) -> tuple[bool, str, str]:
    """Healthcheck RÉEL : version, authentification, accès RH. Rend (ok, cause, message).

    Contourne le cache et le refroidissement : c'est le geste explicite d'un
    administrateur, qui vient peut-être de réactiver le compte côté Odoo — lui
    resservir un refus mémorisé l'empêcherait de constater la correction.
    """
    url, base, login, cle = identifiants_odoo(connector)
    client = ClientOdoo(url=url, base=base, login=login, cle=cle, max_tentatives=1)
    maintenant = dj_timezone.now().isoformat()
    try:
        preuve = _eprouver(client)
    except OdooError as exc:
        champs = {"derniere_verification": maintenant, "cause_dernier_echec": exc.kind,
                  "dernier_echec": maintenant, "message": str(exc)}
        # Seul un refus porte sur le compte ; une panne réseau ne le condamne pas.
        if exc.kind in CAUSES_DE_REFUS:
            champs["verdict_compte"] = exc.kind
        _memoriser(connector, **champs)
        _tracer(connector, action="odoo.auth.verification", succes=False, cause=exc.kind, user=user)
        return False, exc.kind, str(exc)

    session_pour(url, base, login, cle).amorcer(preuve["uid"])
    _memoriser(connector, derniere_verification=maintenant, derniere_authentification=maintenant,
               latence_ms=preuve["latence_ms"], version=preuve["version"],
               cause_dernier_echec=None, dernier_echec=None, verdict_compte=None, message="")
    _tracer(connector, action="odoo.auth.verification", succes=True, user=user)
    return True, "", (f"Odoo {preuve['version'] or ''} : authentification acceptée et lecture RH "
                      f"autorisée.").replace("  ", " ")


def enregistrer_compte_odoo(connector, *, url: str, base: str, login: str, cle: str,
                            user=None) -> tuple[bool, str, str]:
    """Éprouve le compte technique AUPRÈS D'ODOO, puis seulement l'enregistre.

    Même discipline que pour Shield : écrire d'abord ferait afficher « connecté »
    pour un compte faux, et le refus n'apparaîtrait qu'au premier écran métier.
    Sur échec, RIEN n'est écrit — une faute de frappe ne doit pas remplacer un
    compte qui fonctionnait.
    """
    cle_essais = f"odoo:essais:{connector.pk}"
    essais = _cache_get(cle_essais) or 0
    if isinstance(essais, int) and essais >= ESSAIS_ENREGISTREMENT:
        return False, "trop_d_essais", ("Trop d'essais refusés en peu de temps : patientez quelques "
                                        "minutes avant de réessayer, pour ne pas faire verrouiller "
                                        "le compte côté Odoo.")

    url = (url or "").strip().rstrip("/")
    base, login = (base or "").strip(), (login or "").strip()
    manquants = [n for n, v in (("URL", url), ("nom de la base", base),
                                ("adresse du compte", login), ("clé API", cle)) if not v]
    if manquants:
        return False, "config", f"Champs manquants : {', '.join(manquants)}."

    client = ClientOdoo(url=url, base=base, login=login, cle=cle, max_tentatives=1)
    try:
        preuve = _eprouver(client)
    except OdooError as exc:
        if exc.kind in CAUSES_DE_REFUS or exc.kind == "droits":
            _cache_set(cle_essais, (essais if isinstance(essais, int) else 0) + 1,
                       FENETRE_ENREGISTREMENT)
        _tracer(connector, action="odoo.auth.enregistrement", succes=False, cause=exc.kind, user=user)
        return False, exc.kind, f"{exc} Rien n'a été enregistré."

    # Toutes les preuves sont là : on écrit.
    for kind, valeur, libelle in (
        (CredentialKind.DATABASE, base, "Base Odoo"),
        (CredentialKind.LOGIN, login, "Compte de service Odoo"),
        (CredentialKind.API_KEY, cle, "Clé API du compte de service Odoo"),
    ):
        cred, _ = ConnectorCredential.objects.get_or_create(connector=connector, kind=kind)
        cred.label = libelle
        cred.set_secret(valeur)
        cred.save()
    # Un mot de passe déposé autrefois ne doit pas reprendre la main si la clé
    # était un jour retirée : la clé enregistrée ici est désormais LA référence.
    ConnectorCredential.objects.filter(
        connector=connector, kind__in=(CredentialKind.PASSWORD, CredentialKind.API_TOKEN)).delete()

    connector.refresh_from_db()
    config = {k: v for k, v in (connector.config or {}).items()
              if k not in ("database", "db", "login", "username")}
    maintenant = dj_timezone.now().isoformat()
    config["odoo_auth"] = {
        **(config.get("odoo_auth") or {}),
        "derniere_authentification": maintenant, "derniere_verification": maintenant,
        "latence_ms": preuve["latence_ms"], "version": preuve["version"],
        "cause_dernier_echec": None, "dernier_echec": None, "verdict_compte": None, "message": "",
    }
    connector.config = config
    connector.base_url = url
    connector.last_tested_at = dj_timezone.now()
    connector.last_test_ok = True
    connector.last_test_message = "Compte de service Odoo vérifié et enregistré."
    connector.last_latency_ms = preuve["latence_ms"]
    connector.save()
    connector.source.set_status(SourceStatus.CONNECTED)

    session_pour(url, base, login, cle).amorcer(preuve["uid"])
    _cache_delete(cle_essais)
    _tracer(connector, action="odoo.auth.enregistrement", succes=True, user=user)
    return True, "", ("Compte de service vérifié et enregistré : K-Insight rétablira seul la "
                      "connexion Odoo.")


# ── État exposable ───────────────────────────────────────────────────────────


def etat_odoo(connector) -> dict[str, Any]:
    """Ce que la fiche peut afficher : des états, des dates, des masques.

    Jamais la clé, jamais le login complet, jamais l'uid — il ne sert à rien à
    l'écran et identifie le compte dans Odoo.
    """
    memo = _memo(connector)
    config = connector.config or {}
    base_chiffree = _present(connector, CredentialKind.DATABASE)
    login_chiffre = _present(connector, CredentialKind.LOGIN)
    cle = any(_present(connector, k) for k in (CredentialKind.API_KEY, CredentialKind.API_TOKEN,
                                               CredentialKind.PASSWORD))
    base_en_clair = config.get("database") or config.get("db")
    login_en_clair = config.get("login") or config.get("username")
    complet = bool(connector.base_url and (base_chiffree or base_en_clair)
                   and (login_chiffre or login_en_clair) and cle)

    # Le nom de la base et le login ne sont déchiffrés que pour être AFFICHÉS, et
    # le login seulement masqué. Rien d'autre ne sort d'ici.
    base = ""
    login_masque = ""
    if complet:
        # Surtout pas `identifiants_odoo` : il déchiffrerait aussi la clé d'API,
        # dont l'affichage n'a aucun besoin.
        base, login = _base_et_login(connector)
        login_masque = masquer_login(login)

    verdict = memo.get("verdict_compte")
    cause = memo.get("cause_dernier_echec")
    derniere = memo.get("derniere_verification")
    if not complet:
        etat = "auth_required"
    elif verdict in CAUSES_DE_REFUS:
        etat = "auth_required"
    elif cause:
        # Réseau, délai, droits : la liaison est en échec, mais rien ne dit que
        # le compte soit en cause — ce n'est donc PAS « authentification requise ».
        etat = "error"
    elif not derniere:
        etat = "disconnected"
    else:
        try:
            age = dj_timezone.now() - datetime.fromisoformat(derniere)
        except (TypeError, ValueError):
            age = None
        etat = "stale" if age is not None and age > FRAICHEUR_VERIFICATION else "connected"

    return {
        "etat": etat,
        "identifiants_complets": complet,
        "identifiants_chiffres": bool(base_chiffree and login_chiffre),
        "compte_de_service": login_masque,
        "base": base,
        "version": memo.get("version") or "",
        "derniere_authentification": memo.get("derniere_authentification"),
        "derniere_verification": derniere,
        "latence_ms": memo.get("latence_ms"),
        # Active tant que le compte est complet et qu'aucun refus ne pèse sur
        # lui : c'est ce qui permet au backend de rouvrir la session seul.
        "reconnexion_automatique": complet and verdict not in CAUSES_DE_REFUS,
        "cause_dernier_echec": cause,
        "dernier_echec": memo.get("dernier_echec"),
        "message": memo.get("message") or "",
    }


# ── Sociétés et filiales ─────────────────────────────────────────────────────


def societes_odoo(connector) -> list[dict[str, Any]]:
    """Les sociétés RÉELLEMENT présentes dans Odoo : id et nom, rien d'autre."""
    client = client_pour(connector)
    lignes = client.lire("res.company", ["name"], limite=200, ordre="id")
    return [{"id": int(l["id"]), "name": str(l.get("name") or "")}
            for l in lignes if isinstance(l.get("id"), int)]


def correspondance_societes(connector) -> dict[str, str]:
    """{id société Odoo (texte) : code filiale K-Insight}. Vide tant que rien n'est déclaré.

    Aucune correspondance n'est déduite des noms : « Kaydan Real Estate » et
    « KRE » se ressemblent, mais c'est à un humain de l'affirmer. Une société
    sans correspondance est « non rattachée », jamais rangée d'office.
    """
    brut = (connector.config or {}).get("company_mapping") or {}
    return {str(k): str(v) for k, v in brut.items() if v}


def enregistrer_correspondance(connector, mapping: dict[str, str], codes_valides: set[str]) -> dict[str, str]:
    """Valide puis enregistre. Lève ValueError sur un code inconnu."""
    propre: dict[str, str] = {}
    for societe, code in (mapping or {}).items():
        code = (code or "").strip()
        if not code:
            continue  # « non rattaché » : on n'enregistre rien
        if code not in codes_valides:
            raise ValueError(f"Code filiale inconnu : « {code} ».")
        if not str(societe).isdigit():
            raise ValueError(f"Identifiant de société Odoo invalide : « {societe} ».")
        propre[str(int(societe))] = code
    connector.refresh_from_db(fields=["config"])
    config = dict(connector.config or {})
    config["company_mapping"] = propre
    connector.config = config
    connector.save(update_fields=["config", "updated_at"])
    return propre
