"""Logique de test de connexion et de synchronisation.

Tant qu'aucun ETL n'est branché (Airbyte), `run_sync` journalise et finalise sans
ingérer (la donnée passera par Airbyte → EDW, jamais par Django directement, ADR-0004).
`test_connection` valide la complétude de la configuration (sonde réseau réelle à activer).
"""

from __future__ import annotations

import urllib.error
import urllib.request

from django.utils import timezone

from .models import DataSource, LogLevel, SourceStatus, SyncJob, SyncLog, SyncStatus, SyncTrigger


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
    elif t == "airbyte":
        if not cfg.get("airbyte_connection_id"):
            missing.append("airbyte_connection_id")
    # webhook : pas de prérequis (la source pousse les événements)
    if missing:
        return False, "Configuration incomplète : " + ", ".join(missing)
    return True, "Configuration valide — connexion simulée (sonde réseau réelle à activer)."


def network_probe(url: str, timeout: int = 6) -> tuple[bool, str]:
    """Sonde réseau réelle (best-effort). Une réponse HTTP (même 4xx) = hôte joignable."""
    try:
        request = urllib.request.Request(url, method="GET", headers={"User-Agent": "k-insight-probe"})
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return True, f"Hôte joignable (HTTP {resp.status})"
    except urllib.error.HTTPError as exc:
        return True, f"Hôte joignable (HTTP {exc.code})"
    except Exception as exc:  # noqa: BLE001 — réseau : timeout, DNS, refus…
        return False, f"Hôte injoignable depuis le serveur : {type(exc).__name__}"


def run_test(source: DataSource, probe: bool = False) -> tuple[bool, str]:
    ok, message = validate_config(source)
    connector = getattr(source, "connector", None)
    # Sonde réseau réelle, opt-in, uniquement si la config est valide et l'hôte HTTP renseigné.
    if ok and probe and source.source_type in ("rest", "graphql", "webhook") and connector and connector.base_url:
        ok, message = network_probe(connector.base_url)
    if connector is not None:
        connector.last_tested_at = timezone.now()
        connector.last_test_ok = ok
        connector.last_test_message = message[:300]
        connector.save(update_fields=["last_tested_at", "last_test_ok", "last_test_message", "updated_at"])
    source.set_status(SourceStatus.CONNECTED if ok else SourceStatus.ERROR)
    SyncLog.objects.create(source=source, level=LogLevel.INFO if ok else LogLevel.ERROR, message=f"Test de connexion : {message}")
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
