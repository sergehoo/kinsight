from django.urls import path

from .views import CatalogView, GovernanceOverviewView, HrKpiView

urlpatterns = [
    path("catalog/", CatalogView.as_view(), name="metric-catalog"),
    path("overview/", GovernanceOverviewView.as_view(), name="governance-overview"),
    path("hr/kpi/", HrKpiView.as_view(), name="hr-kpi"),
]
