"""Tâches Celery de l'historique RH.

Planification (settings.CELERY_BEAT_SCHEDULE) :
  - présence de la VEILLE, chaque nuit — la journée est close, ses pointages sont
    définitifs ;
  - stocks Shield (effectifs, sites), chaque heure — idempotent : la dernière
    écriture du jour l'emporte, et une heure manquée ne laisse pas de trou ;
  - référentiel Odoo, chaque nuit.

Chaque exécution laisse une trace `SyncJob` (déclencheur « planifiée ») sur la
source concernée : lignes écrites, statut, message. Une collecte déjà en cours
pour la même journée n'est pas doublée — elle est tracée comme sautée.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

from . import historique

logger = logging.getLogger(__name__)


def _source(nom: str):
    if nom == "shield":
        from apps.integrations.shield import get_shield_source

        return get_shield_source()
    from apps.integrations.odoo import get_odoo_source

    return get_odoo_source()


def executer(nom_source: str, libelle: str, collecte, *, declencheur: str = "scheduled"):
    """Exécute une collecte avec sa trace. Rend le bilan."""
    from apps.integrations.models import SyncJob, SyncStatus

    source = _source(nom_source)
    tache = None
    if source is not None:
        tache = SyncJob.objects.create(source=source, trigger=declencheur, status=SyncStatus.RUNNING,
                                       started_at=timezone.now(), message=libelle[:300])
    try:
        bilan = collecte(tache)
    except historique.CollecteEnCours as exc:
        bilan = historique.Bilan(statut="skipped", message=str(exc))
    except Exception as exc:  # noqa: BLE001 — une collecte ratée se trace, elle ne casse pas le worker
        logger.exception("Collecte %s en échec", libelle)
        bilan = historique.Bilan(statut="failed", message=f"{type(exc).__name__}: {exc}"[:300])
    if tache is not None:
        statuts = {"success": SyncStatus.SUCCESS, "partial": SyncStatus.PARTIAL,
                   "failed": SyncStatus.ERROR, "skipped": SyncStatus.ERROR}
        tache.status = statuts.get(bilan.statut, SyncStatus.ERROR)
        tache.finished_at = timezone.now()
        tache.rows_ingested = bilan.ecrites
        tache.message = (f"{libelle} — {bilan.message}" if bilan.message else libelle)[:300]
        tache.save(update_fields=["status", "finished_at", "rows_ingested", "message", "updated_at"])
    return bilan


@shared_task(name="historique.presence_veille")
def presence_veille():
    veille = timezone.localdate() - timedelta(days=1)
    bilan = executer("shield", f"Historique présence {veille}",
                     lambda t: historique.collecter_presence_shield(veille, tache=t))
    return {"jour": veille.isoformat(), "statut": bilan.statut, "ecrites": bilan.ecrites}


@shared_task(name="historique.stocks_shield")
def stocks_shield():
    bilan = executer("shield", "Historique effectifs Shield",
                     lambda t: historique.collecter_stocks_shield(tache=t))
    return {"statut": bilan.statut, "ecrites": bilan.ecrites}


@shared_task(name="historique.odoo_quotidien")
def odoo_quotidien():
    bilan = executer("odoo", "Historique référentiel Odoo",
                     lambda t: historique.collecter_odoo(tache=t))
    return {"statut": bilan.statut, "ecrites": bilan.ecrites}


@shared_task(name="historique.rattrapage_presence")
def rattrapage_presence(depuis: str, jusqu_a: str):
    """Reconstitue la présence jour par jour sur une plage CLOSE.

    Une journée à la fois : c'est ce qui tient sous le plafond de pages de la
    collecte Shield, là où une plage de trois mois le dépasserait dès le
    quatrième jour."""
    debut, fin = date.fromisoformat(depuis), date.fromisoformat(jusqu_a)
    fin = min(fin, timezone.localdate() - timedelta(days=1))
    resultats = []
    jour = debut
    while jour <= fin:
        bilan = executer("shield", f"Rattrapage présence {jour}",
                         lambda t, j=jour: historique.collecter_presence_shield(j, tache=t),
                         declencheur="manual")
        resultats.append({"jour": jour.isoformat(), "statut": bilan.statut})
        jour += timedelta(days=1)
    return resultats


@shared_task(name="rapports.envoyer_dus")
def rapports_envoyer_dus() -> dict:
    """Rapports Capital Humain programmés arrivés à échéance (Celery Beat, 15 min)."""
    from .rapports_programmes import envoyer_les_dus

    return envoyer_les_dus()
