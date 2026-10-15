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

from django.conf import settings
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


class SeuilRh(models.Model):
    """Seuils d'un signal RH tels que la direction les a ARBITRÉS.

    Seules les surcharges sont stockées : un signal sans ligne applique la valeur
    par défaut écrite dans le code (`seuils_rh.DEFAUTS`). Une modification passe
    par l'API — validée, tracée dans le journal d'accès —, jamais par l'admin.
    """

    signal = models.CharField(max_length=40, unique=True)
    surveillance = models.FloatField()
    critique = models.FloatField()
    modifie_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Seuil de signal RH"
        verbose_name_plural = "Seuils de signaux RH"
        ordering = ["signal"]

    def __str__(self) -> str:
        return f"{self.signal} : surveillance {self.surveillance} · critique {self.critique}"


class RapportProgramme(models.Model):
    """Un rapport Capital Humain envoyé périodiquement par e-mail.

    LE PÉRIMÈTRE EST CELUI DU DESTINATAIRE. Chaque destinataire reçoit le rapport
    assemblé sous SES droits, jamais sous ceux de l'auteur : programmer un envoi
    ne peut pas faire sortir un chiffre qu'un destinataire ne verrait pas à
    l'écran. Les filtres sont RELATIFS (« 30 derniers jours », « trimestre en
    cours ») et se résolvent au moment de l'envoi.
    """

    class Frequence(models.TextChoices):
        QUOTIDIEN = "quotidien", "Chaque jour"
        HEBDOMADAIRE = "hebdomadaire", "Chaque lundi"
        MENSUEL = "mensuel", "Le 1er du mois"

    class Format(models.TextChoices):
        XLSX = "xlsx", "Excel"
        PDF = "pdf", "PDF"
        PPTX = "pptx", "PowerPoint"

    nom = models.CharField(max_length=120)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rapports_programmes")
    destinataires = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="rapports_recus")
    frequence = models.CharField(max_length=16, choices=Frequence.choices, default=Frequence.HEBDOMADAIRE)
    format = models.CharField(max_length=8, choices=Format.choices, default=Format.PDF)
    filtres = models.JSONField(default=dict, blank=True)
    actif = models.BooleanField(default=True)
    prochain_envoi = models.DateTimeField()
    dernier_envoi = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rapport programmé"
        verbose_name_plural = "Rapports programmés"
        ordering = ["nom"]

    def __str__(self) -> str:
        return f"{self.nom} ({self.get_frequence_display()}, {self.format})"


class EnvoiRapport(models.Model):
    """Trace d'un envoi : à qui, quand, avec quel résultat. Un échec SMTP est un
    échec — jamais un « envoyé » optimiste."""

    class Statut(models.TextChoices):
        ENVOYE = "envoye", "Envoyé"
        ECHEC = "echec", "Échec"
        IGNORE = "ignore", "Non envoyé"

    rapport = models.ForeignKey(RapportProgramme, on_delete=models.CASCADE, related_name="envois")
    destinataire = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    statut = models.CharField(max_length=8, choices=Statut.choices)
    detail = models.CharField(max_length=300, blank=True)
    envoye_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Envoi de rapport"
        verbose_name_plural = "Envois de rapports"
        ordering = ["-envoye_le"]
