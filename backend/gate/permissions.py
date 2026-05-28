from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdmin(BasePermission):
    """Only admin-role users (or superusers)."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, 'is_admin', False))


class IsAdminOrReadOnly(BasePermission):
    """Any authenticated user can read; only admins can write."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return getattr(user, 'is_admin', False)
