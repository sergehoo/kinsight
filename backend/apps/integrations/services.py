"""Logique de test de connexion et de synchronisation.

Tant qu'aucun ETL n'est branché (Airbyte), `run_sync` journalise et finalise sans
ingérer (la donnée passera par Airbyte → EDW, jamais par Django directement, ADR-0004).
`test_connection` valide la complétude de la configuration (sonde réseau réelle à activer).
"""

from __future__ import annotations

import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from django.utils import timezone

from .models import (
    DataSource, LogLevel, SourceStatus, SourceType, SyncJob, SyncLog, SyncStatus, SyncTrigger,
)


def validate_config(source: DataSource) -> tuple[bool, str]:
    connector = getattr(source, "connector", None)
    if connector is None:
        return False, "Connecteur non configuré."
    cfg = connector.config or {}
    t = source.source_type
    missing: list[str] = []
    if t in ("rest", "graphql"):
        if not connector.base_url:
            missing.append("URL de base")
    elif t in ("postgres", "mysql"):
        for k in ("host", "dbname"):
            if not cfg.get(k):
                missing.append(k)
    elif t == "csv":
        if not (cfg.get("file_path") or cfg.get("url")):
            missing.append("file_path ou url")
    elif t == "excel":
        if not cfg.get("file_path"):
            missing.append("file_path")
    elif t == "gsheets":
        if not cfg.get("sheet_id"):
            missing.append("sheet_id")
    elif t in ("kaydan_shield", "odoo_hr", "sap"):
        # Ces connecteurs parlent HTTP : sans URL de base, il n'y a rien à joindre.
        if not connector.base_url:
            missing.append("URL de base")
        if t == "odoo_hr" and not cfg.get("database"):
            missing.append("base de données Odoo")
    elif t == "edw":
        # Le mart est lu par le gateway, pas par un connecteur HTTP : rien à exiger ici.
        pass
    elif t == "airbyte":
        if not cfg.get("airbyte_connection_id"):
            missing.append("airbyte_connection_id")
    # webhook : pas de prérequis (la source pousse les événements)
    if missing:
        return False, "Configuration incomplète : " + ", ".join(missing)
    return True, "Configuration valide."


# Ces codes prouvent qu'un serveur HTTP répond, PAS qu'on peut y lire quoi que ce
# soit. Chacun appelle un geste différent : les confondre sous « hôte joignable »
# revenait à déclarer connectée une source dont on n'a jamais rien obtenu.
_DIAGNOSTIC_HTTP = {
    401: "L'hôte répond mais refuse le jeton (HTTP 401) : jeton absent, expiré ou invalide.",
    403: "L'hôte répond mais refuse l'accès (HTTP 403) : le compte n'a pas les permissions requises.",
    404: "Aucun endpoint à cette adresse (HTTP 404) : vérifiez l'URL de base et le chemin interrogé.",
    405: "L'endpoint existe mais refuse la méthode GET (HTTP 405).",
    429: "L'hôte demande de ralentir (HTTP 429) : quota atteint.",
}


def _qualifier_exception(exc: Exception) -> str:
    """Nomme la cause réelle. « Injoignable » ne dit pas s'il faut corriger un
    certificat, un DNS, un pare-feu ou attendre."""
    if isinstance(exc, urllib.error.URLError):
        exc = exc.reason if isinstance(exc.reason, Exception) else exc
    if isinstance(exc, ssl.SSLCertVerificationError):
        return ("Certificat TLS non vérifiable : le magasin de certificats du serveur K-Insight "
                "est absent ou incomplet, ou le certificat de la source est invalide.")
    if isinstance(exc, ssl.SSLError):
        return f"Échec de la négociation TLS : {type(exc).__name__}."
    if isinstance(exc, socket.gaierror):
        return "Nom d'hôte non résolu : le DNS du serveur K-Insight ne connaît pas cette adresse."
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "Délai dépassé : l'hôte n'a pas répondu à temps."
    if isinstance(exc, ConnectionRefusedError):
        return "Connexion refusée : rien n'écoute sur ce port."
    return f"Hôte injoignable depuis le serveur : {type(exc).__name__}."


def probe_target(source: DataSource) -> str:
    """L'URL à interroger pour prouver que la source est lisible.

    On préfère un endpoint métier DÉCLARÉ à l'URL de base : interroger la racine
    d'une API renvoie très souvent 404, ce qui ne prouve ni ne réfute rien.
    """
    connector = getattr(source, "connector", None)
    if connector is None or not connector.base_url:
        return ""
    base = connector.base_url.rstrip("/")
    endpoint = connector.endpoints.filter(is_active=True).exclude(path="").order_by("name").first()
    if endpoint:
        return f"{base}/{endpoint.path.lstrip('/')}"
    return base


def network_probe(url: str, timeout: int = 6) -> tuple[bool, str]:
    """Sonde réseau réelle. « Connectée » exige une réponse VALIDE, pas une réponse.

    La version précédente traitait toute réponse HTTP comme un succès, 404 compris :
    une source dont l'URL de base ne correspondait à aucun endpoint passait en
    `connected`, ce qui autorisait ensuite sa synchronisation. Seul un 2xx prouve
    qu'on lit réellement quelque chose ; tout le reste est rendu avec sa cause.
    """
    try:
        request = urllib.request.Request(url, method="GET", headers={"User-Agent": "k-insight-probe"})
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            if 200 <= resp.status < 300:
                return True, f"Endpoint interrogé avec succès (HTTP {resp.status})."
            return False, f"Réponse inattendue (HTTP {resp.status}) : rien d'exploitable n'a été renvoyé."
    except urllib.error.HTTPError as exc:
        diagnostic = _DIAGNOSTIC_HTTP.get(exc.code)
        if diagnostic:
            return False, diagnostic
        if exc.code >= 500:
            return False, f"La source est en erreur (HTTP {exc.code}) : la panne est de son côté."
        return False, f"Réponse d'erreur de la source (HTTP {exc.code})."
    except Exception as exc:  # noqa: BLE001 — réseau : TLS, DNS, timeout, refus…
        return False, _qualifier_exception(exc)


def _real_healthcheck(source: DataSource) -> tuple[bool, str] | None:
    """Sonde métier RÉELLE quand un connecteur dédié existe.

    Pour Kaydan Shield, on réutilise le client du connecteur : il interroge un
    vrai endpoint avec le vrai jeton. Une sonde purement réseau répondrait « hôte
    joignable » alors que le jeton est expiré — la distinction compte, c'est
    exactement ce qui sépare « connecté » de « refusé ».
    """
    if source.source_type == SourceType.KAYDAN_SHIELD:
        from .shield import build_client

        try:
            # `max_attempts=1` : c'est un test interactif. Trois essais espacés de
            # pauses feraient patienter l'utilisateur ~26 s et immobiliseraient un
            # worker sur trois pendant tout ce temps, pour un verdict qui aurait été
            # le même au premier essai dans l'immense majorité des cas.
            client = build_client(source, max_attempts=1)
        except Exception as exc:  # noqa: BLE001
            # La construction du client déchiffre le secret. Hors de ce `try`, une
            # clé de chiffrement changée faisait remonter un 500 Django : l'écran
            # annonçait une panne serveur là où il fallait ressaisir un jeton.
            return False, (f"Connecteur Shield inutilisable ({type(exc).__name__}) : le secret enregistré "
                           f"est illisible. Ré-enregistrez le jeton depuis la fiche de la source.")
        return client.healthcheck()
    return None


def run_test(source: DataSource, probe: bool = True) -> tuple[bool, str]:
    """Teste la connexion, mesure la latence, et ne déclare « connectée » qu'une
    source qui a RÉELLEMENT répondu.

    Trois issues distinctes, et non deux :
      - preuve obtenue et positive  → `connected`
      - preuve obtenue et négative  → `error`, avec la cause
      - aucune preuve possible      → `configured` : la configuration tient, mais
        rien n'a été vérifié. C'est le cas des sources sans sonde (base de données,
        fichiers, Airbyte, mart) et du mode `?probe=0`.

    La version précédente confondait la troisième avec la première : une source
    dont on n'avait jamais rien lu ressortait « connectée », et la synchronisation
    s'autorisait alors à partir sur une source muette.
    """
    ok, message = validate_config(source)
    connector = getattr(source, "connector", None)
    latency_ms = None
    preuve = False

    if ok and probe:
        started = time.monotonic()
        real = _real_healthcheck(source)
        if real is not None:
            ok, message = real
            preuve = True
        elif source.source_type in ("rest", "graphql", "webhook", "sap", "odoo_hr") and connector and connector.base_url:
            cible = probe_target(source)
            ok, message = network_probe(cible)
            preuve = True
            # La racine d'une API ne renvoie presque jamais de ressource : un 404 y
            # est le comportement NORMAL, pas le signe d'une mauvaise URL. Sans
            # cette précision, le message envoie corriger une URL qui est juste.
            if not ok and cible == connector.base_url.rstrip("/"):
                message += (" Aucun endpoint déclaré : le test a interrogé la racine de l'API. "
                            "Déclarez un endpoint dans l'onglet « Endpoints » pour tester une lecture réelle.")
        latency_ms = int((time.monotonic() - started) * 1000) if preuve else None
        if not preuve:
            message = (f"Configuration valide. Aucune sonde n'existe pour une source de type "
                       f"« {source.get_source_type_display()} » : l'état reste « configurée », "
                       f"non « connectée ».")
    elif ok:
        message = "Configuration valide. Aucune sonde n'a été lancée (probe=0) : rien n'est vérifié."

    if connector is not None:
        connector.last_tested_at = timezone.now()
        # `None` et non `True` sans preuve : `run_sync` s'appuie sur ce champ pour
        # refuser de synchroniser une source non connectée.
        connector.last_test_ok = (ok if preuve else None)
        connector.last_test_message = message[:300]
        connector.last_latency_ms = latency_ms
        connector.save(update_fields=["last_tested_at", "last_test_ok", "last_test_message",
                                      "last_latency_ms", "updated_at"])

    if not ok:
        statut = SourceStatus.ERROR
    elif preuve:
        statut = SourceStatus.CONNECTED
    else:
        statut = SourceStatus.CONFIGURED
    source.set_status(statut)
    SyncLog.objects.create(source=source, level=LogLevel.INFO if ok else LogLevel.ERROR,
                           message=f"Test de connexion : {message}")
    return ok, message


def run_sync(source: DataSource, trigger: str = SyncTrigger.MANUAL) -> SyncJob:
    connector = getattr(source, "connector", None)
    job = SyncJob.objects.create(
        source=source,
        trigger=trigger,
        status=SyncStatus.RUNNING,
        started_at=timezone.now(),
        incremental=source.sync_frequency != "manual",
    )
    source.set_status(SourceStatus.SYNCING)

    connected = connector is not None and connector.last_test_ok is True
    if not connected and not source.demo_mode:
        job.status = SyncStatus.ERROR
        job.message = "Source non connectée — testez la connexion d'abord."
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "message", "finished_at", "updated_at"])
        SyncLog.objects.create(source=source, job=job, level=LogLevel.ERROR, message=job.message)
        source.set_status(SourceStatus.ERROR)
        return job

    # ETL réel (Airbyte) à brancher : on finalise en succès sans ingestion directe.
    job.status = SyncStatus.SUCCESS
    job.rows_ingested = 0
    job.message = "Synchronisation simulée — connecteur ETL (Airbyte) à brancher pour alimenter le mart."
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "rows_ingested", "message", "finished_at", "updated_at"])
    SyncLog.objects.create(source=source, job=job, level=LogLevel.INFO, message=job.message)
    source.set_status(SourceStatus.CONNECTED if connected else SourceStatus.CONFIGURED)
    return job
