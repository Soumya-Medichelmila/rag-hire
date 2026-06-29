from django.contrib.auth.backends import ModelBackend
from .models import Employee


class EmailBackend(ModelBackend):

    def authenticate(self, request, username=None, email=None, password=None, **kwargs):

        try:
            user = Employee.objects.get(email=email or username)

            if user.check_password(password):
                return user

            return None

        except Employee.DoesNotExist:
            return None

    def get_user(self, user_id):
        
        try:
            return Employee.objects.get(pk=user_id)

        except Employee.DoesNotExist:
            return None