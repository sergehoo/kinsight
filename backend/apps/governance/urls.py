from django.urls import path
from .module_views import (
    AiQueryView,
    AlertsView,
    DomainScoreView,
    ExportGroupScoreView,
    GroupScoreView,
    HrScoreView,
    ModuleDataView,
)

from .views import CatalogView, GovernanceOverviewView, HrKpiView

urlpatterns = [
    path("catalog/", CatalogView.as_view(), name="metric-catalog"),
    path("overview/", GovernanceOverviewView.as_view(), name="governance-overview"),
    path("hr/kpi/", HrKpiView.as_view(), name="hr-kpi"),
    path("hr/score/", HrScoreView.as_view(), name="hr-score"),
    path("score-group/", GroupScoreView.as_view(), name="group-score"),
    path("alerts/", AlertsView.as_view(), name="alerts"),
    path("ai/query/", AiQueryView.as_view(), name="ai-query"),
    path("export/groupe.<str:ext>", ExportGroupScoreView.as_view(), name="export-group-score"),
    path("score/<str:domain>/", DomainScoreView.as_view(), name="domain-score"),
    path("module/<str:key>/", ModuleDataView.as_view(), name="module-data"),
]
