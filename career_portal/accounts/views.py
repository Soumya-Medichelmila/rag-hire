from django.contrib.auth import authenticate

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken

from drf_yasg.utils import swagger_auto_schema

from .models import Employee

from .serializers import (
    LoginSerializer,
    ChangePasswordSerializer,
    EmployeeSerializer
)

from .permissions import IsAdminOrHR,IsAdminHROrJuniorHR


class LoginView(APIView):

    permission_classes = []

    @swagger_auto_schema(request_body=LoginSerializer)
    def post(self, request):

        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        employee = authenticate(request, email=email, password=password)

        if employee is None:
            return Response(
                {'message': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not employee.is_active:
            return Response(
                {'message': 'Employee account is inactive'},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(employee)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'employee': {
                'id': employee.id,
                'employee_code': employee.employee_code,
                'email': employee.email,
                'first_name': employee.first_name,
                'last_name': employee.last_name,
                'role': employee.role.code if employee.role else None,
                'role_name': employee.role.name if employee.role else None,
                'is_password_changed': employee.is_password_changed,
                'department_name': employee.department.name if employee.department else '',  # ← ADDED
            }
        })


class ChangePasswordView(APIView):

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=ChangePasswordSerializer)
    def post(self, request):

        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']
        confirm_password = serializer.validated_data['confirm_password']

        employee = request.user

        if not employee.check_password(old_password):
            return Response(
                {'message': 'Old password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            return Response(
                {'message': 'Passwords do not match'},
                status=status.HTTP_400_BAD_REQUEST
            )

        employee.set_password(new_password)
        employee.is_password_changed = True
        employee.save()

        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass

        return Response({'message': 'Password changed successfully'})


class EmployeeCreateView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrHR]

    @swagger_auto_schema(request_body=EmployeeSerializer)
    def post(self, request):

        serializer = EmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

        temp_password = 'Temp123'
        employee.set_password(temp_password)
        employee.save()

        return Response(
            {
                'message': 'Employee created successfully',
                'temporary_password': temp_password
            },
            status=status.HTTP_201_CREATED
        )


class EmployeeListView(APIView):

    permission_classes = [IsAuthenticated,IsAdminHROrJuniorHR]

    def get(self, request):
        employees = Employee.objects.all()
        serializer = EmployeeSerializer(employees, many=True)
        return Response(serializer.data)


class EmployeeDetailView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            employee = Employee.objects.get(pk=pk)
        except Employee.DoesNotExist:
            return Response(
                {'message': 'Employee not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if request.user.role and request.user.role.code in ['ADMIN', 'HR']:
            serializer = EmployeeSerializer(employee)
            return Response(serializer.data)

        if request.user.id != employee.id:
            return Response(
                {'message': 'You can only view your own profile'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = EmployeeSerializer(employee)
        return Response(serializer.data)


class EmployeeUpdateView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrHR]

    @swagger_auto_schema(request_body=EmployeeSerializer)
    def put(self, request, pk):
        try:
            employee = Employee.objects.get(pk=pk)
        except Employee.DoesNotExist:
            return Response(
                {'message': 'Employee not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = EmployeeSerializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({'message': 'Employee updated successfully'})


class EmployeeDeactivateView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrHR]

    def patch(self, request, pk):
        try:
            employee = Employee.objects.get(pk=pk)
        except Employee.DoesNotExist:
            return Response(
                {'message': 'Employee not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if employee == request.user:
            return Response(
                {'message': 'You cannot deactivate your own account'},
                status=status.HTTP_400_BAD_REQUEST
            )

        employee.is_active = False
        employee.is_active_employee = False
        employee.save()

        return Response({'message': 'Employee deactivated successfully'})