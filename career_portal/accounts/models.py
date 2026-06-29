from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from masters.models import Department, Skill, Location


class EmployeeManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):

        if not email:
            raise ValueError('Email is required')

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            **extra_fields
        )

        user.set_password(password)

        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        return self.create_user(
            email,
            password,
            **extra_fields
        )


class Role(models.Model):

    name = models.CharField(
        max_length=50,
        unique=True
    )

    code = models.CharField(
        max_length=30,
        unique=True
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name


class Employee(AbstractUser):

    username = None

    employee_code = models.CharField(
        max_length=20,
        unique=True
    )

    email = models.EmailField(
        unique=True
    )

    phone = models.CharField(
        max_length=15,
        unique=True
    )

    designation = models.CharField(
        max_length=100
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='employees',
        null=True,
        blank=True
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='employees',
        null=True,
        blank=True
    )

    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        related_name='employees',
        null=True,
        blank=True
    )

    skills = models.ManyToManyField(
        Skill,
        related_name='employees',
        blank=True
    )

    is_password_changed = models.BooleanField(
        default=False
    )

    is_active_employee = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    USERNAME_FIELD = 'email'

    REQUIRED_FIELDS = []

    objects = EmployeeManager()

    def __str__(self):
        return self.email