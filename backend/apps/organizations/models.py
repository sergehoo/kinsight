"""Référentiel des filiales / entités du groupe (côté applicatif).

C'est le miroir applicatif de la dimension conforme `warehouse.dim_subsidiary` :
il sert à définir les périmètres RBAC et à libeller les résultats. Les chiffres,
eux, viennent toujours du mart (ADR-0004).
"""

from django.db import models


class Subsidiary(models.Model):
    """Filiale du groupe (KRE = K-Express, KSH = K-Shield, MYK = MyKaydan…)."""

    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=128)
    entity_code = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=2, default="CI")
    currency = models.CharField(max_length=3, default="XOF")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Filiale"
        verbose_name_plural = "Filiales"

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"
