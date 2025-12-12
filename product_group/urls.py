from django.urls import path
from .views import (ProductGroupListCreateView, ProductGroupNameListView, 
                    ProductServicesView, QuoteListCreateView, QuoteDetailView, SendQuoteEmailView, 
                    ProductGroupWithModulesListView, QuoteStatusChoicesView, QuoteItemUnitChoicesView, 
                    PipelineDataAPIView, QuoteInvoiceDownloadView)


urlpatterns = [
    path('product-groups/', ProductGroupListCreateView.as_view(), name='product-group-list-create'),
    path('product-groups/<int:pk>/', ProductGroupListCreateView.as_view(), name='product-group-detail'),
    path('product-services/', ProductServicesView.as_view(), name='product-services-list-create'),
    path('product-services/<int:pk>/', ProductServicesView.as_view(), name='product-services-detail'),
    path('product-group-names/', ProductGroupNameListView.as_view(), name='product-group-names-list'),
    path('product-groups-with-modules/', ProductGroupWithModulesListView.as_view(), name='product-groups-with-modules'),
    path('quote-status-choices/', QuoteStatusChoicesView.as_view(), name='quote-status-choices'),
    path('quote-item-unit-choices/', QuoteItemUnitChoicesView.as_view(), name='quote-item-unit-choices'),
    # --- QUOTATION URLS ---
    path('quotes/', QuoteListCreateView.as_view(), name='quote-list-create'),
    path('quotes/<int:pk>/', QuoteDetailView.as_view(), name='quote-detail'),
    path('quotes/<int:pk>/send/', SendQuoteEmailView.as_view(), name='quote-send-email'),
    path('pipeline-data/', PipelineDataAPIView.as_view(), name='pipeline-data'),
    path('quotes/<int:pk>/invoice/', QuoteInvoiceDownloadView.as_view(), name='quote-download-invoice'),

]