from django.urls import path
from .views import (
    CompanyListCreateAPIView,
    CompanyDetailAPIView,
    CompanyTagListCreateAPIView,
    CompanyTagDetailAPIView,
    PointOfContactListCreateAPIView,
    PointOfContactDetailAPIView,
    CompanyPOCListView,
)

urlpatterns = [
    # companies
    path("client/", CompanyListCreateAPIView.as_view(), name="company-list-create"),
    path("client/<int:pk>/", CompanyDetailAPIView.as_view(), name="company-detail"),

    # company tags
    path("company-tags/", CompanyTagListCreateAPIView.as_view(), name="companytag-list-create"),
    path("company-tags/<int:pk>/", CompanyTagDetailAPIView.as_view(), name="companytag-detail"),

    path("pocs/", PointOfContactListCreateAPIView.as_view(), name="poc-list-create"),
    path("pocs/<int:pk>/", PointOfContactDetailAPIView.as_view(), name="poc-detail"),

    # New URL for getting POCs by company
    path("client/<int:company_id>/pocs/", CompanyPOCListView.as_view(), name="company-poc-list"),
]
