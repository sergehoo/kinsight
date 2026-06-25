"""Journal des consultations / accès (historique exigé par le brief, ADR-0005).

En prod, ce journal vise le schéma `audit` de l'EDW (le rôle applicatif a INSERT sur
`audit`). En dev/tests, il est stocké dans la base applicative. Le helper `record`
centralise l'écriture.
"""

from django.conf import settings
from django.db import models


class AccessLog(models.Model):
    occurred_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    user_role = models.CharField(max_length=32, blank=True)
    action = models.CharField(max_length=64)  # view_dashboard, query_metric, ai_query, export
    metric_key = models.CharField(max_length=64, blank=True)
    subsidiary_scope = models.JSONField(default=list)  # périmètre filiales appliqué
    payload = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["action", "occurred_at"])]

    @classmethod
    def record(cls, *, user, action, metric_key="", scope_codes=None, payload=None, ip=None):
        return cls.objects.create(
            user=user if getattr(user, "pk", None) else None,
            user_role=getattr(user, "role", "") or "",
            action=action,
            metric_key=metric_key,
            subsidiary_scope=scope_codes or [],
            payload=payload or {},
            ip_address=ip,
        )

    def __str__(self) -> str:
        return f"{self.occurred_at:%Y-%m-%d %H:%M} {self.action} {self.metric_key}"
