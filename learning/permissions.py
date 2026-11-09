from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import Profile

def role(user):
    if user.is_superuser:
        return 'admin'
    return Profile.objects.get_or_create(user=user)[0].role

class EducatorOnly(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and role(request.user) in ('educator','admin')

class AdminOnly(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and role(request.user) == 'admin'

class MaterialAccess(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.method in SAFE_METHODS or role(request.user) in ('educator','admin'))
    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS or role(request.user) == 'admin' or obj.owner_id is None or obj.owner_id == request.user.id
