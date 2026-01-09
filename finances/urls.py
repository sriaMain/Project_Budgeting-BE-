# urls.py
from django.urls import path
from . import views
from django.http import HttpResponse

from .views import (QuotationDetailView, InvoiceListView, InvoiceDetailView,
                    GenerateInvoiceView, RecordPaymentView, InvoicePaymentListView,  
                    DownloadInvoicePDFView, SendInvoiceEmailView, CancelInvoiceView,
                    InvoiceShareableLinkView, PublicInvoiceView, InvoiceStatisticsView, DownloadInvoicePDFView,PublicInvoicePDFView,ShareInvoiceLinkView,
                    ProjectPaymentAPIView, ProjectPaymentSummaryAPIView, ProjectPaymentsListAPIView,
               
                    PurchaseOrderCreateAPIView, QuotePurchaseOrderListAPIView, PurchaseOrderDetailAPIView,
                    PurchaseOrderStatusUpdateAPIView)

urlpatterns = [
    path("test/", lambda r: HttpResponse("FINANCES OK")),
    # Quotation
    path('quotations/<int:pk>/', QuotationDetailView.as_view(),name='quotation-detail'),
   

    
    # Invoice CRUD
    path('invoices/', InvoiceListView.as_view(),name='invoice-list'),
    
    path('invoices/<int:invoice_id>/',InvoiceDetailView.as_view(),name='invoice-detail'),
    
    # Generate Invoice
    path('invoices/generate/',GenerateInvoiceView.as_view(), 
         name='invoice-generate'),
    
    # Payment Operations
    path('invoices/<int:invoice_id>/payment/',RecordPaymentView.as_view(), 
         name='invoice-record-payment'),
    
    path('invoices/<int:invoice_id>/payments/',InvoicePaymentListView.as_view(), 
         name='invoice-payments-list'),
    
    # Milestones
#     path('invoices/<int:invoice_id>/milestones/',InvoiceMilestoneListView.as_view(), 
#          name='invoice-milestones'),
    
#     # PDF & Email
#     path('invoices/<int:invoice_id>/pdf/',DownloadInvoicePDFView.as_view(), 
#          name='invoice-download-pdf'),
    
    path('invoices/<int:invoice_id>/send-email/',SendInvoiceEmailView.as_view(), 
         name='invoice-send-email'),
    
    # Cancel Invoice
    path('invoices/<int:invoice_id>/cancel/',CancelInvoiceView.as_view(), 
         name='invoice-cancel'),
    
    # Share & Public View
    path('invoices/<int:invoice_id>/share/',InvoiceShareableLinkView.as_view(), 
         name='invoice-share'),
    
    path('invoices/view/<int:invoice_id>/<str:token>/',PublicInvoiceView.as_view(), 
         name='invoice-public-view'),
    
    # Statistics
    path('invoices/statistics/',InvoiceStatisticsView.as_view(), 
         name='invoice-statistics'),

#     path(
#         "invoices/<int:invoice_id>/send-email/",
#         SendInvoiceEmailView.as_view(),
#         name="send-invoice-email"
#     ),
    path(
        "invoices/<int:invoice_id>/download/",
        DownloadInvoicePDFView.as_view(),
        name="download-invoice"
    ),
    path(
        "public/invoice/<str:token>/",
        PublicInvoicePDFView.as_view(),
        name="public-invoice-pdf"
    ),
    path(
        "invoices/<int:invoice_id>/share-link/",
        ShareInvoiceLinkView.as_view()
    ),
    path(
        'projects/<int:project_id>/payments/',
        ProjectPaymentAPIView.as_view(),
        name='project-payments'
    ),

    # Project payment summary
    path(
        'projects/<int:project_id>/payments/summary/',
        ProjectPaymentSummaryAPIView.as_view(),
        name='project-payment-summary'
    ),

    # Project payments list
    path(
        'projects/<int:project_id>/payments-list/',
        ProjectPaymentsListAPIView.as_view(),
        name='project-payments-list'
    ),
    
    # Purchase Orders
#     path('purchase-orders/', PurchaseOrderListView.as_view(), name='po-list'),
#     path('purchase-orders/<int:po_id>/', PurchaseOrderDetailView.as_view(), name='po-detail'),
#     path('purchase-orders/create/', CreatePurchaseOrderView.as_view(), name='po-create'),
#     path('vendor-bills/', VendorBillListView.as_view()),
#     path('vendor-bills/create/', CreateVendorBillView.as_view()),
     path(
        'purchase-orders/',
        PurchaseOrderCreateAPIView.as_view(),
        name='purchase-order-create'
    ),

    path(
        'quotes/<int:quote_id>/purchase-orders/',
        QuotePurchaseOrderListAPIView.as_view(),
        name='quote-purchase-orders'
    ),
     path(
        'purchase-orders/<int:po_id>/',
        PurchaseOrderDetailAPIView.as_view(),
        name='purchase-order-detail'
    ),

    path(
        'purchase-orders/<int:po_id>/status/',
        PurchaseOrderStatusUpdateAPIView.as_view(),
        name='purchase-order-status'
    ),



]


# Example usage in main urls.py:
# from django.urls import path, include
# 
# urlpatterns = [
#     path('api/', include('invoice.urls')),
# ]