from django.contrib import admin
from .models import  JobOpening,VacancyRequest
# Register your models here.
admin.site.register( JobOpening)
admin.site.register(VacancyRequest)