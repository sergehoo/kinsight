"""Modèles du K-Insight AI Copilot (Phase 1 — fondation gouvernée).

Principes (ADR-0007, ADR-0005) : l'IA s'appuie sur le Data Warehouse / les API governance
(jamais d'invention) ; toute action sensible passe par une demande d'approbation explicite
avant exécution ; tout est journalisé et tracé.

Différés aux phases suivantes : AIKnowledgeContext (le contexte est construit à la volée),
AIReport (génération/loi de rapports IA), AIAutomation (tâches planifiées).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ProviderKind(models.TextChoices):
    DEEPSEEK = "deepseek", "DeepSeek"
    CLAUDE = "claude", "Claude (Anthropic)"
    OPENAI = "openai", "OpenAI"
    MISTRAL = "mistral", "Mistral"
    OFFLINE = "offline", "Repli déterministe ancré"


class AIProvider(models.Model):
    """Moteur LLM configuré. Le router les essaie par `priority` croissante (fallback)."""

    name = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=16, choices=ProviderKind.choices)
    model_name = models.CharField(max_length=128, blank=True)
    base_url = models.CharField(max_length=256, blank=True)
    priority = models.PositiveSmallIntegerField(default=100, help_text="Ordre d'essai (croissant).")
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["priority"]

    def __str__(self) -> str:
        return f"{self.name} ({self.kind}, p{self.priority})"


class AIConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_conversations")
    title = models.CharField(max_length=200, blank=True)
    mode = models.CharField(max_length=24, default="analyse")  # analyse|guide|action|rapport|connecteur|automatisation
    context = models.JSONField(default=dict, blank=True)  # instantané du contexte à l'ouverture
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class AIMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Utilisateur"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "Système"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=12, choices=Role.choices)
    content = models.TextField()
    provider = models.CharField(max_length=32, blank=True)   # provider ayant produit la réponse
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    grounded = models.BooleanField(default=False)            # réponse sourcée sur le catalogue/mart
    metric_key = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict, blank=True)     # données structurées (KPI, tableau, blocs)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class AITool(models.Model):
    """Déclaration persistée d'un outil exposé à l'IA (miroir de ToolRegistry)."""

    class Mode(models.TextChoices):
        READ = "read", "Lecture"
        WRITE = "write", "Écriture"

    name = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=300)
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.READ)
    sensitive = models.BooleanField(default=False, help_text="Exige une approbation explicite avant exécution.")
    required_role = models.CharField(max_length=32, blank=True)
    enabled = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.mode}{'/sensible' if self.sensitive else ''})"


class AIToolExecution(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Succès"
        ERROR = "error", "Erreur"

    tool_name = models.CharField(max_length=64)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="ai_tool_executions")
    args = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AIActionRequest(models.Model):
    """Demande d'action SENSIBLE en attente d'approbation (rien n'est exécuté avant)."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Approuvée"
        REJECTED = "rejected", "Rejetée"
        EXECUTED = "executed", "Exécutée"
        FAILED = "failed", "Échec"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_action_requests")
    conversation = models.ForeignKey(AIConversation, on_delete=models.SET_NULL, null=True, blank=True, related_name="action_requests")
    tool_name = models.CharField(max_length=64)
    args = models.JSONField(default=dict, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    destructive = models.BooleanField(default=False)
    # Nombre de confirmations requises avant exécution (1 = écriture, 2 = destructif/double validation).
    required_confirmations = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AIActionApproval(models.Model):
    class Decision(models.TextChoices):
        APPROVED = "approved", "Approuvée"
        REJECTED = "rejected", "Rejetée"

    # ForeignKey (pas OneToOne) : une action destructrice exige plusieurs confirmations.
    request = models.ForeignKey(AIActionRequest, on_delete=models.CASCADE, related_name="approvals")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="ai_approvals")
    decision = models.CharField(max_length=10, choices=Decision.choices)
    note = models.CharField(max_length=300, blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 4-eyes : un même utilisateur ne peut compter qu'une fois → double validation = 2 personnes.
        constraints = [
            models.UniqueConstraint(fields=["request", "approver"], name="uniq_approval_per_user")
        ]


class AIAutomation(models.Model):
    """Tâche planifiée du Copilot (Phase 5). Exécutée par Celery Beat.

    Gouverné : une automatisation déclenchant un outil SENSIBLE ne l'exécute pas — elle crée
    une demande d'approbation (comme une action manuelle). Seuls les outils de lecture
    s'exécutent automatiquement.
    """

    name = models.CharField(max_length=120)
    tool_name = models.CharField(max_length=64)
    args = models.JSONField(default=dict, blank=True)
    context = models.JSONField(default=dict, blank=True)
    interval_minutes = models.PositiveIntegerField(default=1440)  # quotidien par défaut
    enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="ai_automations")
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def is_due(self, now) -> bool:
        if not self.enabled:
            return False
        if self.last_run_at is None:
            return True
        return (now - self.last_run_at).total_seconds() >= self.interval_minutes * 60


class AIAuditLog(models.Model):
    """Trace complète des interactions IA (provider, latence, erreurs, actions)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="ai_audit")
    action = models.CharField(max_length=40)   # chat|provider_call|tool_execute|action_request|approve|reject
    provider = models.CharField(max_length=32, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField(default=True)
    detail = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]

    @classmethod
    def record(cls, *, user, action, provider="", latency_ms=None, success=True, detail=None, ip=None):
        return cls.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            provider=provider,
            latency_ms=latency_ms,
            success=success,
            detail=detail or {},
            ip=ip,
        )
