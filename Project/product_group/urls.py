from django.urls import path
from .views import ProductGroupListCreateView, ProductGroupNameListView, ProductServicesView, QuoteListCreateView, QuoteDetailView


urlpatterns = [
    path('product-groups/', ProductGroupListCreateView.as_view(), name='product-group-list-create'),
    path('product-groups/<int:pk>/', ProductGroupListCreateView.as_view(), name='product-group-detail'),
    path('product-services/', ProductServicesView.as_view(), name='product-services-list-create'),
    path('product-services/<int:pk>/', ProductServicesView.as_view(), name='product-services-detail'),
    path('product-group-names/', ProductGroupNameListView.as_view(), name='product-group-names-list'),
    # --- QUOTATION URLS ---
    path('quotes/', QuoteListCreateView.as_view(), name='quote-list-create'),
    path('quotes/<int:pk>/', QuoteDetailView.as_view(), name='quote-detail'),
]