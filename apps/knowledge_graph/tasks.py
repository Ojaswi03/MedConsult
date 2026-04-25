import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def rebuild_knowledge_graph(self):
    try:
        from django.core.cache import cache
        from apps.knowledge_graph.graph_builder import build_graph
        from apps.knowledge_graph.models import GraphSnapshot

        data = build_graph(quick=False)
        git_head = data['metadata'].get('git_head', '')

        GraphSnapshot.objects.update_or_create(
            id=1,
            defaults={'data': data, 'git_head': git_head},
        )
        cache.delete('knowledge_graph_api')

        node_count = len(data.get('nodes', []))
        logger.info("Knowledge graph rebuilt: %d nodes", node_count)
        return f"OK: {node_count} nodes"
    except Exception as exc:
        logger.exception("rebuild_knowledge_graph failed")
        raise self.retry(exc=exc)
