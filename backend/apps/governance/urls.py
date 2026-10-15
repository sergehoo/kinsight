from django.urls import path

from .history_views import HrDimensionsView, HrHistoryView
from .rapports_views import EnvoyerRapportView, RapportProgrammeView, RapportsProgrammesView
from .signaux_views import HrDecisionView, HrReportExportView, HrSignalsView, HrThresholdsView
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
    path("hr/history/", HrHistoryView.as_view(), name="hr-history"),
    path("hr/dimensions/", HrDimensionsView.as_view(), name="hr-dimensions"),
    path("hr/signaux/", HrSignalsView.as_view(), name="hr-signals"),
    path("hr/seuils/", HrThresholdsView.as_view(), name="hr-thresholds"),
    path("hr/decision/", HrDecisionView.as_view(), name="hr-decision"),
    path("hr/rapport.<str:ext>", HrReportExportView.as_view(), name="hr-report-export"),
    path("hr/rapports-programmes/", RapportsProgrammesView.as_view(), name="hr-scheduled-reports"),
    path("hr/rapports-programmes/<int:pk>/", RapportProgrammeView.as_view(), name="hr-scheduled-report"),
    path("hr/rapports-programmes/<int:pk>/envoyer/", EnvoyerRapportView.as_view(), name="hr-scheduled-report-send"),
    path("score-group/", GroupScoreView.as_view(), name="group-score"),
    path("alerts/", AlertsView.as_view(), name="alerts"),
    path("ai/query/", AiQueryView.as_view(), name="ai-query"),
    path("export/groupe.<str:ext>", ExportGroupScoreView.as_view(), name="export-group-score"),
    path("score/<str:domain>/", DomainScoreView.as_view(), name="domain-score"),
    path("module/<str:key>/", ModuleDataView.as_view(), name="module-data"),
]
