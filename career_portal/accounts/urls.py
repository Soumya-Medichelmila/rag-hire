from django.urls import path

from .views import (
    LoginView,
    ChangePasswordView,
    EmployeeCreateView,
    EmployeeListView,
    EmployeeDetailView,
    EmployeeUpdateView,
    EmployeeDeactivateView
)

urlpatterns = [

    path(
        'login/',
        LoginView.as_view(),
        name='login'
    ),

    path(
        'change-password/',
        ChangePasswordView.as_view(),
        name='change-password'
    ),

    path(
        'employees/create/',
        EmployeeCreateView.as_view(),
        name='employee-create'
    ),

    path(
        'employees/',
        EmployeeListView.as_view(),
        name='employee-list'
    ),

    path(
        'employees/<int:pk>/',
        EmployeeDetailView.as_view(),
        name='employee-detail'
    ),

    path(
        'employees/<int:pk>/update/',
        EmployeeUpdateView.as_view(),
        name='employee-update'
    ),

    path(
        'employees/<int:pk>/deactivate/',
        EmployeeDeactivateView.as_view(),
        name='employee-deactivate'
    ),
]