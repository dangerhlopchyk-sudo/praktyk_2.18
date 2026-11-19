from rest_framework.permissions import BasePermission


class ClosedCatalog(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method == "DELETE":
            return user.is_staff
        return True
