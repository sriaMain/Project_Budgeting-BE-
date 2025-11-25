from django.urls import path
from .views import (
    CompanyListCreateAPIView,
    CompanyDetailAPIView,
    CompanyTagListCreateAPIView,
    CompanyTagDetailAPIView,
)

urlpatterns = [
    # companies
    path("companies/", CompanyListCreateAPIView.as_view(), name="company-list-create"),
    path("companies/<int:pk>/", CompanyDetailAPIView.as_view(), name="company-detail"),

    # company tags
    path("company-tags/", CompanyTagListCreateAPIView.as_view(), name="companytag-list-create"),
    path("company-tags/<int:pk>/", CompanyTagDetailAPIView.as_view(), name="companytag-detail"),
]
