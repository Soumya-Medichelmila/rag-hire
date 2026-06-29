from django.contrib import admin

from django.urls import path, include

from rest_framework import permissions

from drf_yasg.views import get_schema_view

from drf_yasg import openapi


schema_view = get_schema_view(

    openapi.Info(

        title="Employee Management API",

        default_version='v1',

        description="Employee Management Backend APIs",

    ),

    public=True,

    permission_classes=[permissions.AllowAny],
)


urlpatterns = [

    path(
        'admin/',
        admin.site.urls
    ),

    path(
        'api/accounts/',
        include('accounts.urls')
    ),

    path(
        'api/masters/',
        include('masters.urls')
    ),

    path(
        'swagger/',
        schema_view.with_ui(
            'swagger',
            cache_timeout=0
        ),
        name='schema-swagger-ui'
    ),
    path('api/jobs/', include('jobs.urls')),
    path('api/recruitment/', include('recruitment.urls')),
]



from django.conf import settings
from django.conf.urls.static import static

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)