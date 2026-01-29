from django.urls import path
from .views import DashboardMetricsAPIView, FinanceOverviewAPIView

urlpatterns = [
    path("dashboard/metrics/",DashboardMetricsAPIView.as_view(),name="dashboard-metrics"),
    path("finance/overview/",FinanceOverviewAPIView.as_view(),name="all-tab-data"),
]
# GET /api/finance/overview/?section=all
# GET /api/finance/overview/?section=financial_reports
# GET /api/finance/overview/?section=project_reports
# GET /api/finance/overview/?section=payment_reports
# GET /api/finance/overview/?section=po_invoice_reports