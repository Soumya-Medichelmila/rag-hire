from rest_framework import serializers
from .models import Employee


class LoginSerializer(serializers.Serializer):

    email = serializers.EmailField()

    password = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):

    old_password = serializers.CharField()

    new_password = serializers.CharField()

    confirm_password = serializers.CharField()


class EmployeeSerializer(serializers.ModelSerializer):

    class Meta:

        model = Employee

        fields = [
            'id',
            'employee_code',
            'first_name',
            'last_name',
            'email',
            'phone',
            'designation',
            'role',
            'department',
            'location',
            'skills',
            'is_active_employee'
        ]

        read_only_fields = ['id']