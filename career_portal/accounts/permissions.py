from rest_framework.permissions import BasePermission


class IsAdminOrHR(BasePermission):
    """
    Allows access only to users with role ADMIN or HR.
    Used by: HR dashboard, shortlisting, screening results.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not request.user.role:
            return False
        return request.user.role.code in ['ADMIN', 'HR']


class IsJuniorHR(BasePermission):
    """
    Allows access only to users with role JR_HR.
    Used by: interview scheduling, sending emails.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not request.user.role:
            return False
        return request.user.role.code == 'JR_HR'


class IsAdminHROrJuniorHR(BasePermission):
    """
    Allows access to ADMIN, HR, and JR_HR.
    Used by: viewing shortlists and interviews.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not request.user.role:
            return False
        return request.user.role.code in ['ADMIN', 'HR', 'JR_HR']