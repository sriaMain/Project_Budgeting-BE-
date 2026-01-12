# urls.py
from django.urls import path
from . import views
from django.http import HttpResponse

from .views import (QuotationDetailView, InvoiceListView, InvoiceDetailView,
                    GenerateInvoiceView, RecordPaymentView, InvoicePaymentListView,  
                    DownloadInvoicePDFView, SendInvoiceEmailView, CancelInvoiceView,
                    InvoiceShareableLinkView, PublicInvoiceView, InvoiceStatisticsView, DownloadInvoicePDFView,PublicInvoicePDFView,ShareInvoiceLinkView,
                    ProjectPaymentAPIView, ProjectPaymentSummaryAPIView, ProjectPaymentsListAPIView,
                    PurchaseOrderCreateAPIView, QuotePurchaseOrderListAPIView, PurchaseOrderDetailAPIView,ProjectPurchaseOrderListAPIView,SendPurchaseOrderEmailView,
                    PurchaseOrderStatusUpdateAPIView, VendorBillCreateAPIView, VendorBillListAPIView,VendorBillByNumberAPIView,
                    OutgoingPaymentCreateAPIView, VendorBillPaymentListAPIView, ProjectOutgoingPaymentsAPIView)

urlpatterns = [
   path("test/", lambda r: HttpResponse("FINANCES OK")),

path("quotations/<int:pk>/", QuotationDetailView.as_view()),

path("invoices/", InvoiceListView.as_view()),
path("invoices/<int:invoice_id>/", InvoiceDetailView.as_view()),
path("invoices/generate/", GenerateInvoiceView.as_view()),
path("invoices/<int:invoice_id>/payment/", RecordPaymentView.as_view()),
path("invoices/<int:invoice_id>/payments/", InvoicePaymentListView.as_view()),
path("invoices/<int:invoice_id>/send-email/", SendInvoiceEmailView.as_view()),
path("invoices/<int:invoice_id>/cancel/", CancelInvoiceView.as_view()),
path("invoices/<int:invoice_id>/share/", InvoiceShareableLinkView.as_view()),
path("invoices/view/<int:invoice_id>/<str:token>/", PublicInvoiceView.as_view()),
path("invoices/statistics/", InvoiceStatisticsView.as_view()),
path("invoices/<int:invoice_id>/download/", DownloadInvoicePDFView.as_view()),
path("public/invoice/<str:token>/", PublicInvoicePDFView.as_view()),
path("invoices/<int:invoice_id>/share-link/", ShareInvoiceLinkView.as_view()),

path("projects/<int:project_id>/payments/", ProjectPaymentAPIView.as_view()),
path("projects/<int:project_id>/payments/summary/", ProjectPaymentSummaryAPIView.as_view()),
path("projects/<int:project_id>/payments-list/", ProjectPaymentsListAPIView.as_view()),

path("purchase-orders/", PurchaseOrderCreateAPIView.as_view()),
path("purchase-orders/<int:po_id>/", PurchaseOrderDetailAPIView.as_view()),
path("purchase-orders/<int:po_id>/send-mail/", SendPurchaseOrderEmailView.as_view()),
path("purchase-orders/<int:po_id>/status/", PurchaseOrderStatusUpdateAPIView.as_view()),

path("projects/<int:project_no>/purchase-orders/", ProjectPurchaseOrderListAPIView.as_view()),
path("quotes/<int:quote_id>/purchase-orders/", QuotePurchaseOrderListAPIView.as_view()),

path("vendor-bills/", VendorBillCreateAPIView.as_view()),
path("vendor-bills/<str:bill_no>/",VendorBillByNumberAPIView.as_view(),name="vendor-bill-by-number"),
path("vendor-bills/list/", VendorBillListAPIView.as_view()),
path("vendor-bills/<int:bill_id>/payments/", OutgoingPaymentCreateAPIView.as_view()),
path("vendor-bills/<int:bill_id>/payments/list/", VendorBillPaymentListAPIView.as_view()),

path("projects/<int:project_id>/outgoing-payments/", ProjectOutgoingPaymentsAPIView.as_view()),
]