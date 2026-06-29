from django.urls import path
from .views import (
    VacancyRequestListCreateView,
    VacancyRequestAcceptView,
    VacancyRequestRejectView,
    JobOpeningListView,
    JobOpeningEditView,
    JobOpeningCloseView,
)

urlpatterns = [
    # Vacancy Requests
    path('vacancy-requests/', VacancyRequestListCreateView.as_view(), name='vacancy-request-list-create'),
    path('vacancy-requests/<int:pk>/accept/', VacancyRequestAcceptView.as_view(), name='vacancy-request-accept'),
    path('vacancy-requests/<int:pk>/reject/', VacancyRequestRejectView.as_view(), name='vacancy-request-reject'),

    # Job Openings
    path('openings/', JobOpeningListView.as_view(), name='job-opening-list'),
    path('openings/<int:pk>/', JobOpeningEditView.as_view(), name='job-opening-edit'),
    path('openings/<int:pk>/close/', JobOpeningCloseView.as_view(), name='job-opening-close'),
]