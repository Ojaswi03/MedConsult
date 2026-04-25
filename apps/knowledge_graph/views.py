import logging
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from apps.api.permissions import IsAdmin

logger = logging.getLogger(__name__)

_CACHE_KEY = 'knowledge_graph_api'
_CACHE_TTL = 60  # seconds


class KnowledgeGraphAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        data = cache.get(_CACHE_KEY)
        if data is None:
            try:
                from apps.knowledge_graph.models import GraphSnapshot
                snapshot = GraphSnapshot.objects.order_by('-generated_at').first()
                if snapshot:
                    data = snapshot.data
                else:
                    from apps.knowledge_graph.graph_builder import build_graph
                    data = build_graph(quick=False)
            except Exception:
                from apps.knowledge_graph.graph_builder import build_graph
                data = build_graph(quick=False)
            cache.set(_CACHE_KEY, data, _CACHE_TTL)
        return Response(data)


class KnowledgeGraphUIView(View):
    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        return render(request, 'knowledge_graph/graph.html')
