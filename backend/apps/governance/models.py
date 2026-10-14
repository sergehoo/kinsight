"""Historique K-Insight : instantanés datés des métriques RH, en PostgreSQL.

POURQUOI. Shield et Odoo répondent sur l'état PRÉSENT : l'effectif, la synthèse
du jour. Sans historique, un filtre « T3 2026 » ou « 90 jours » ne pouvait rien
changer aux mesures Shield/Odoo — il ne s'appliquait qu'au mart, absent en
production. Chaque collecte dépose donc ici la valeur du jour, et ce sont ces
lignes qui rendent les périodes et les comparaisons réelles.

LE GRAIN. (jour, source, métrique, dimension, code) — unique. Rejouer la collecte
d'une journée MET À JOUR sa ligne, elle n'en ajoute pas : la collecte est
idempotente par construction, pas par discipline.

LE NON-MESURÉ N'EST PAS ZÉRO. Un jour que la source n'a pas pu couvrir est stocké
`unknown` avec une valeur NULL. Le transformer en 0 ferait chuter un taux de
présence de période pour une panne de réseau.

LE PÉRIMÈTRE. Une ligne Shield de dimension `groupe` ou `site` est une donnée
GROUPE (ADR-0009) : elle ne se sert qu'au périmètre Groupe. Les lignes Odoo de
dimension `societe` portent l'identifiant de société, ce qui permet de recomposer
le chiffre d'une filiale à partir de ses sociétés déclarées.
"""

from __future__ import annotations

from django.db import models


class Dimension(models.TextChoices):
    GROUPE = "groupe", "Groupe"
    SITE = "site", "Site"
    TYPE = "type", "Type de personnel"
    DEPARTEMENT = "departement", "Département"
    SOCIETE = "societe", "Société Odoo"


class StatutMesure(models.TextChoices):
    MESURE = "measured", "Mesurée"
    INCONNU = "unknown", "Non mesurée"
    ERREUR = "error", "Erreur de collecte"


class KpiSnapshot(models.Model):
    jour = models.DateField(db_index=True)
    source = models.CharField(max_length=16)                    # shield | odoo
    metric_id = models.CharField(max_length=64)                 # identifiant canonique (hr_registry)
    dimension = models.CharField(max_length=16, choices=Dimension.choices, default=Dimension.GROUPE)
    code = models.CharField(max_length=128, blank=True, default="")
    libelle = models.CharField(max_length=200, blank=True, default="")
    valeur = models.FloatField(null=True, blank=True)
    statut = models.CharField(max_length=12, choices=StatutMesure.choices, default=StatutMesure.MESURE)
    collecte_le = models.DateTimeField()
    tache = models.ForeignKey("integrations.SyncJob", null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="instantanes")

    class Meta:
        verbose_name = "Instantané de métrique"
        verbose_name_plural = "Instantanés de métriques"
        constraints = [
            models.UniqueConstraint(fields=["jour", "source", "metric_id", "dimension", "code"],
                                    name="uniq_instantane_jour_metrique"),
            # Une valeur mesurée a une valeur ; un jour inconnu n'en a pas. La base
            # le garantit, pas seulement le code qui écrit.
            models.CheckConstraint(
                condition=(models.Q(statut="measured", valeur__isnull=False)
                           | ~models.Q(statut="measured")),
                name="mesure_porte_une_valeur",
            ),
        ]
        indexes = [
            models.Index(fields=["metric_id", "dimension", "jour"], name="instantane_serie"),
        ]
        ordering = ["jour"]

    def __str__(self) -> str:
        return f"{self.jour} {self.metric_id} [{self.dimension}:{self.code or '*'}] = {self.valeur}"
