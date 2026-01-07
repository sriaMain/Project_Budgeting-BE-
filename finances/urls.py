# urls.py
from django.urls import path
from . import views
from django.http import HttpResponse

from .views import (QuotationDetailView, InvoiceListView, InvoiceDetailView,
                    GenerateInvoiceView, RecordPaymentView, InvoicePaymentListView,  
                    DownloadInvoicePDFView, SendInvoiceEmailView, CancelInvoiceView,
                    InvoiceShareableLinkView, PublicInvoiceView, InvoiceStatisticsView, DownloadInvoicePDFView,PublicInvoicePDFView,ShareInvoiceLinkView)

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
]


# Example usage in main urls.py:
# from django.urls import path, include
# 
# urlpatterns = [
#     path('api/', include('invoice.urls')),
# ]