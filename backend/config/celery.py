"""Celery — orchestration des syncs Airbyte / runs dbt / alertes / rapports (ADR-0003).

Les tâches concrètes seront ajoutées par incrément (déclenchement dbt, calcul des
alertes, génération de rapports programmés). Beat porte la planification.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("k_insight")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
