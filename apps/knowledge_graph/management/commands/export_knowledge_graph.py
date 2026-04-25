"""
Management command: export the knowledge graph to knowledge_graph.json.
--quick flag: only project + git_commit + system_health nodes (fast, for git hook).
"""
import json
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Export the knowledge graph to knowledge_graph.json'

    def add_arguments(self, parser):
        parser.add_argument(
            '--quick',
            action='store_true',
            help='Only rebuild project/git/system_health nodes (fast path for git hook)',
        )

    def handle(self, *args, **options):
        from apps.knowledge_graph.graph_builder import build_graph
        from apps.knowledge_graph.models import GraphSnapshot

        quick = options['quick']
        self.stdout.write(f"Building knowledge graph (quick={quick})...")

        data = build_graph(quick=quick)

        # Persist to DB
        git_head = data['metadata'].get('git_head', '')
        snapshot, created = GraphSnapshot.objects.update_or_create(
            id=1,
            defaults={'data': data, 'git_head': git_head},
        )
        action = 'Created' if created else 'Updated'
        self.stdout.write(f"{action} GraphSnapshot (id=1)")

        # Write JSON file
        output_path = settings.BASE_DIR / 'knowledge_graph.json'
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        node_count = len(data.get('nodes', []))
        edge_count = len(data.get('edges', []))
        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {node_count} nodes, {edge_count} edges → {output_path}"
            )
        )
