from django.urls import path
from .views import KnowledgeGraphUIView

app_name = 'knowledge_graph'

urlpatterns = [
    path('', KnowledgeGraphUIView.as_view(), name='graph'),
]
