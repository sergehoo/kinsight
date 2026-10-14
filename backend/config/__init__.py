# L'application Celery doit être chargée avec Django : sans cela, un `.delay()`
# lancé depuis une vue part vers l'application par défaut de Celery — broker AMQP
# local — au lieu du Redis configuré, et la tâche n'arrive jamais au worker.
from .celery import app as celery_app

__all__ = ("celery_app",)
