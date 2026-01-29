from decimal import Decimal

from django.db.models import Sum, DecimalField
from django.db.models.functions import Coalesce
from django.core.cache import cache

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from Project.models import ProjectBudget
from finances.models import Invoice, InvoicePayment, OutgoingPayment

from .serializers import DashboardMetricsSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .services import (
    get_all_tab_data,
    get_financial_tab_data,
    get_project_tab_data,
    get_payment_tab_data,
    get_po_invoice_tab_data,
)


class DashboardMetricsAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 🔹 Cache (60 seconds)
        cached_data = cache.get("dashboard_metrics")
        if cached_data:
            return Response(cached_data)

        # 1️⃣ Budget → ProjectBudget.total_budget (only active projects)
        total_budget = ProjectBudget.objects.filter(
            project__status__in=[
                "planning",
                "development",
                "testing",
                "uat",
                "ready_for_deployment",
                "deployed",
            ]
        ).aggregate(
            total=Coalesce(
                Sum("total_budget"),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
        )["total"]

        # 2️⃣ Invoiced → Invoice.total_amount (valid business statuses)
        total_invoiced = Invoice.objects.filter(
            status__in=["Issued", "Partially Paid", "Paid", "Overdue"]
        ).aggregate(
            total=Coalesce(
                Sum("total_amount"),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
        )["total"]

        # 3️⃣ Received → InvoicePayment.amount
        total_received = InvoicePayment.objects.aggregate(
            total=Coalesce(
                Sum("amount"),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
        )["total"]

        # 4️⃣ Expenses → OutgoingPayment.amount
        total_expenses = OutgoingPayment.objects.aggregate(
            total=Coalesce(
                Sum("amount"),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
        )["total"]

        # 5️⃣ Profit → Received - Expenses
        profit = (total_received or Decimal("0.00")) - (total_expenses or Decimal("0.00"))

        data = {
            "budget": {
                "value": total_budget,
                "change": 0,
            },
            "invoiced": {
                "value": total_invoiced,
                "change": 0,
            },
            "received": {
                "value": total_received,
                "change": 0,
            },
            "expenses": {
                "value": total_expenses,
                "change": 0,
            },
            "profit": {
                "value": profit,
                "change": 0,
            },
        }

        serializer = DashboardMetricsSerializer(data)
        cache.set("dashboard_metrics", serializer.data, timeout=60)

        return Response(serializer.data)



class FinanceOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]    

    def get(self, request):
        section = request.query_params.get("section", "all")

        filters = {
            "from_date": request.query_params.get("from_date"),
            "to_date": request.query_params.get("to_date"),
            "client": request.query_params.get("client"),
            "project": request.query_params.get("project"),
        }

        if section == "all":
            data = get_all_tab_data(filters)

        elif section == "financial_reports":
            data = get_financial_tab_data(filters)

        elif section == "project_reports":
            data = get_project_tab_data(filters)

        elif section == "payment_reports":
            data = get_payment_tab_data(filters)

        elif section == "po_invoice_reports":
            data = get_po_invoice_tab_data(filters)

        else:
            return Response(
                {"error": "Invalid section"},
                status=400
            )

        return Response(data)   
    

from Reports.services import generate_financial_excel
from Project.models import Project
from django.http import HttpResponse
from finances.models import Invoice, Expense

class FinancialReportExport(APIView):
    """
    Export financial report as Excel
    Filters:
    - project_id (required)
    - date_from (YYYY-MM-DD)
    - date_to (YYYY-MM-DD)
    - status (optional: PAID / PENDING)
    """

    def get(self, request):
        project_id = request.GET.get("project_id")
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        status = request.GET.get("status")

        if not project_id or not date_from or not date_to:
            return HttpResponse(
                "project_id, date_from, date_to are required",
                status=400
            )

        project = Project.objects.get(id=project_id)

        invoices = Invoice.objects.filter(
            project=project,
            created_at__date__range=[date_from, date_to]
        )

        if status:
            invoices = invoices.filter(status=status)

        expenses = Expense.objects.filter(
            project=project,
            created_at__date__range=[date_from, date_to]
        )

        wb = generate_financial_excel(
            project=project,
            invoices=invoices,
            expenses=expenses,
            date_from=date_from,
            date_to=date_to
        )

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="financial_report_project_{project.id}.xlsx"'
        )

        wb.save(response)
        return response