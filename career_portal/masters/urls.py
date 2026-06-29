from django.urls import path

from .views import (
    DepartmentListCreateView,
    SkillListCreateView,
    LocationListCreateView
)

urlpatterns = [

    path(
        'departments/',
        DepartmentListCreateView.as_view(),
        name='department-list-create'
    ),

    path(
        'skills/',
        SkillListCreateView.as_view(),
        name='skill-list-create'
    ),

    path(
        'locations/',
        LocationListCreateView.as_view(),
        name='location-list-create'
    ),
]