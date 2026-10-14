"""Collecte manuelle de l'historique RH — exploitation et rattrapage.

  manage.py historiser --presence --depuis 2026-07-01 --jusqu-a 2026-10-13
  manage.py historiser --stocks
  manage.py historiser --odoo

Même code que les tâches planifiées, même trace `SyncJob` (déclencheur
« manuel »), même verrou : lancer cette commande pendant qu'une tâche tourne sur
la même journée la saute au lieu de la doubler.
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.governance import historique
from apps.governance.tasks import executer


class Command(BaseCommand):
    help = "Collecte l'historique RH (présence rattrapable, stocks Shield, référentiel Odoo)."

    def add_arguments(self, parser):
        parser.add_argument("--presence", action="store_true", help="Présence Shield, jour par jour")
        parser.add_argument("--stocks", action="store_true", help="Effectifs et sites Shield du jour")
        parser.add_argument("--odoo", action="store_true", help="Référentiel Odoo du jour")
        parser.add_argument("--depuis", type=date.fromisoformat)
        parser.add_argument("--jusqu-a", dest="jusqu_a", type=date.fromisoformat)

    def handle(self, *args, **opts):
        if not (opts["presence"] or opts["stocks"] or opts["odoo"]):
            raise CommandError("Choisissez au moins --presence, --stocks ou --odoo.")
        hier = timezone.localdate() - timedelta(days=1)
        if opts["presence"]:
            debut = opts["depuis"] or hier
            fin = min(opts["jusqu_a"] or hier, hier)
            if debut > fin:
                raise CommandError("Aucune journée close dans cette plage (aujourd'hui reste live).")
            jour = debut
            while jour <= fin:
                bilan = executer("shield", f"Rattrapage présence {jour}",
                                 lambda t, j=jour: historique.collecter_presence_shield(j, tache=t),
                                 declencheur="manual")
                self.stdout.write(f"{jour} présence : {bilan.statut} ({bilan.ecrites} lignes"
                                  f"{', ' + bilan.message if bilan.message else ''})")
                jour += timedelta(days=1)
        if opts["stocks"]:
            bilan = executer("shield", "Effectifs Shield", lambda t: historique.collecter_stocks_shield(tache=t),
                             declencheur="manual")
            self.stdout.write(f"stocks Shield : {bilan.statut} ({bilan.ecrites} lignes)")
        if opts["odoo"]:
            bilan = executer("odoo", "Référentiel Odoo", lambda t: historique.collecter_odoo(tache=t),
                             declencheur="manual")
            self.stdout.write(f"Odoo : {bilan.statut} ({bilan.ecrites} lignes)")
