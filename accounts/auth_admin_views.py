from django.contrib.auth.models import Group, Permission
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes

from core.api import (
    api_response,
    handle_api_exceptions,
    not_found_response,
    paginate_queryset,
    validation_error_response,
)
from core.permissions import method_perm, require_perm
from .auth_admin_serializers import GroupDetailSerializer, GroupListSerializer, PermissionSerializer
from .models import User


@api_view(["GET", "POST"])
@permission_classes([method_perm(GET="auth.view_group", POST="auth.add_group")])
@handle_api_exceptions
def admin_group_list_create(request):
    """Danh sách và tạo Django Group."""
    if request.method == "GET":
        search = request.query_params.get("search")
        queryset = Group.objects.all().order_by("name")
        if search:
            queryset = queryset.filter(name__icontains=search)
        return api_response(
            message="Groups retrieved successfully.",
            data=paginate_queryset(request, queryset, GroupListSerializer),
        )

    serializer = GroupDetailSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    group = serializer.save()
    return api_response(
        message="Group created successfully.",
        status_code=status.HTTP_201_CREATED,
        data=GroupDetailSerializer(group).data,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([method_perm(
    GET="auth.view_group",
    PATCH="auth.change_group",
    DELETE="auth.delete_group",
)])
@handle_api_exceptions
def admin_group_detail(request, id):
    """Chi tiết, cập nhật, xóa một Django Group."""
    group = Group.objects.filter(id=id).first()
    if not group:
        return not_found_response("Group not found.")

    if request.method == "GET":
        return api_response(
            message="Group retrieved successfully.",
            data=GroupDetailSerializer(group).data,
        )

    if request.method == "DELETE":
        group.delete()
        return api_response(message="Group deleted successfully.")

    serializer = GroupDetailSerializer(group, data=request.data, partial=True)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    serializer.save()
    return api_response(
        message="Group updated successfully.",
        data=GroupDetailSerializer(group).data,
    )


@api_view(["GET"])
@permission_classes([require_perm("auth.view_permission")])
@handle_api_exceptions
def admin_permission_list(request):
    """Danh sách tất cả Django Permission (dùng để gán vào Group)."""
    search = request.query_params.get("search")
    app_label = request.query_params.get("app_label")
    queryset = Permission.objects.select_related("content_type").order_by(
        "content_type__app_label", "codename"
    )
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(codename__icontains=search)
        )
    if app_label:
        queryset = queryset.filter(content_type__app_label=app_label)
    return api_response(
        message="Permissions retrieved successfully.",
        data=paginate_queryset(request, queryset, PermissionSerializer),
    )


@api_view(["GET"])
@permission_classes([require_perm("accounts.view_user")])
@handle_api_exceptions
def admin_user_permissions(request, id):
    """Xem toàn bộ quyền hiệu lực của một user (từ groups + user_permissions)."""
    user = User.objects.filter(id=id).prefetch_related("groups__permissions", "user_permissions").first()
    if not user:
        return not_found_response("Account not found.")

    groups = list(user.groups.values("id", "name"))
    all_perms = sorted(user.get_all_permissions())

    return api_response(
        message="User permissions retrieved successfully.",
        data={
            "user_id": user.id,
            "email": user.email,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "groups": groups,
            "effective_permissions": all_perms,
        },
    )
