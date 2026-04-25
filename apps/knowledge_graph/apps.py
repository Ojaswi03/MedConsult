from django.apps import AppConfig


class KnowledgeGraphConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.knowledge_graph'
    label = 'knowledge_graph'

    def ready(self):
        import apps.knowledge_graph.signals  # noqa: F401
