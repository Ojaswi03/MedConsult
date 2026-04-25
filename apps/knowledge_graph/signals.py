"""
Django signals → debounced Celery rebuild of the knowledge graph.
Max one rebuild per 10 seconds to prevent signal storms.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)

_DEBOUNCE_KEY = 'kg_rebuild_debounce'
_DEBOUNCE_TTL = 10  # seconds


def _schedule_rebuild():
    try:
        from django.core.cache import cache
        from apps.knowledge_graph.tasks import rebuild_knowledge_graph

        if cache.add(_DEBOUNCE_KEY, 1, timeout=_DEBOUNCE_TTL):
            rebuild_knowledge_graph.apply_async(countdown=_DEBOUNCE_TTL)
    except Exception:
        logger.exception("Failed to schedule knowledge graph rebuild")


def _connect_signals():
    from apps.accounts.models import User
    from apps.scheduling.models import Appointment, Slot

    for model in (User, Appointment, Slot):
        post_save.connect(_on_model_change, sender=model, weak=False)
        post_delete.connect(_on_model_change, sender=model, weak=False)

    try:
        from apps.messaging.models import Conversation
        post_save.connect(_on_model_change, sender=Conversation, weak=False)
        post_delete.connect(_on_model_change, sender=Conversation, weak=False)
    except ImportError:
        pass

    try:
        from apps.payments.models import Payment
        post_save.connect(_on_model_change, sender=Payment, weak=False)
        post_delete.connect(_on_model_change, sender=Payment, weak=False)
    except ImportError:
        pass


def _on_model_change(sender, **kwargs):
    _schedule_rebuild()


# Connect when signals module is imported (called from apps.py ready())
_connect_signals()
