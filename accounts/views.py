from datetime import timedelta
from functools import wraps
import logging
import random

from django.contrib.auth.models import Group
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AccountOTP, QuotaConfig, User
from .serializers import (
    AccountRoleSerializer,
    AccountStatusSerializer,
    AdminAccountDetailSerializer,
    AdminAccountListSerializer,
    AdminPasswordResetSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    QuotaConfigSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
)
from .tasks import send_otp_email_task

logger = logging.getLogger(__name__)


API_ERROR_RESPONSE = inline_serializer(
    name="ApiErrorResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": serializers.JSONField(allow_null=True),
        "errors": serializers.JSONField(allow_null=True),
    },
)


API_EMPTY_RESPONSE = inline_serializer(
    name="ApiEmptyResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": serializers.JSONField(allow_null=True),
        "errors": serializers.JSONField(allow_null=True),
    },
)


REGISTER_RESPONSE = inline_serializer(
    name="RegisterResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": inline_serializer(
            name="RegisterResponseData",
            fields={
                "id": serializers.CharField(),
                "email": serializers.EmailField(),
            },
        ),
        "errors": serializers.JSONField(allow_null=True),
    },
)


LOGIN_RESPONSE = inline_serializer(
    name="LoginResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": inline_serializer(
            name="LoginResponseData",
            fields={
                "refresh": serializers.CharField(),
                "access": serializers.CharField(),
            },
        ),
        "errors": serializers.JSONField(allow_null=True),
    },
)


PROFILE_RESPONSE = inline_serializer(
    name="ProfileResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": ProfileSerializer(read_only=True),
        "errors": serializers.JSONField(allow_null=True),
    },
)


ADMIN_ACCOUNT_LIST_RESPONSE = inline_serializer(
    name="AdminAccountListResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": inline_serializer(
            name="AdminAccountListPage",
            fields={
                "count": serializers.IntegerField(),
                "next": serializers.CharField(allow_null=True, allow_blank=True),
                "previous": serializers.CharField(allow_null=True, allow_blank=True),
                "results": AdminAccountListSerializer(many=True, read_only=True),
            },
        ),
        "errors": serializers.JSONField(allow_null=True),
    },
)


ADMIN_ACCOUNT_DETAIL_RESPONSE = inline_serializer(
    name="AdminAccountDetailResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": AdminAccountDetailSerializer(read_only=True),
        "errors": serializers.JSONField(allow_null=True),
    },
)


QUOTA_RESPONSE = inline_serializer(
    name="QuotaResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": QuotaConfigSerializer(read_only=True),
        "errors": serializers.JSONField(allow_null=True),
    },
)


DEFAULT_ERROR_RESPONSES = {
    400: API_ERROR_RESPONSE,
    401: API_ERROR_RESPONSE,
    403: API_ERROR_RESPONSE,
    404: API_ERROR_RESPONSE,
    500: API_ERROR_RESPONSE,
}


def api_response(message, status_code=status.HTTP_200_OK, data=None, errors=None):
    body = {
        "status_code": status_code,
        "message": message,
        "data": data,
        "errors": errors,
    }
    return Response(body, status=status_code)


def validation_error_response(serializer):
    return api_response(
        message="Validation failed.",
        status_code=status.HTTP_400_BAD_REQUEST,
        errors=serializer.errors,
    )


def handle_api_exceptions(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as exc:
            logger.exception("Unhandled accounts API error in %s", view_func.__name__)
            return api_response(
                message="Internal server error.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                errors={"detail": [str(exc)]},
            )

    return wrapper


def generate_otp():
    """Generate a 6-digit OTP."""
    return f"{random.randint(100000, 999999)}"


def issue_otp(contact_info, purpose):
    AccountOTP.objects.filter(
        contact_info=contact_info,
        purpose=purpose,
        is_verified=False,
    ).update(expired_at=timezone.now())

    otp = generate_otp()
    AccountOTP.objects.create(
        contact_info=contact_info,
        otp_code=otp,
        purpose=purpose,
        expired_at=timezone.now() + timedelta(minutes=5),
        is_verified=False,
    )
    logger.info("OTP for %s (%s): %s", contact_info, purpose, otp)
    send_otp_email_task.delay(contact_info, otp)


@extend_schema(
    summary="Đăng ký",
    request=RegisterSerializer,
    responses={201: REGISTER_RESPONSE, **DEFAULT_ERROR_RESPONSES},
    examples=[
        OpenApiExample(
            "Success",
            value={
                "status_code": 201,
                "message": "Account registered successfully.",
                "data": {"id": "user_xxxx", "email": "test@gmail.com"},
                "errors": None,
            },
        )
    ],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@handle_api_exceptions
def register(request):
    email = request.data.get("email")
    if email and User.objects.filter(email=email).exists():
        return api_response(
            message="Email already registered.",
            status_code=status.HTTP_400_BAD_REQUEST,
            errors={"email": ["Email already registered."]},
        )

    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    user = serializer.save()
    return api_response(
        message="Account registered successfully.",
        status_code=status.HTTP_201_CREATED,
        data={"id": user.id, "email": user.email},
    )


@extend_schema(
    summary="Đăng nhập",
    request=LoginSerializer,
    responses={200: LOGIN_RESPONSE, **DEFAULT_ERROR_RESPONSES},
    examples=[
        OpenApiExample(
            "Success",
            value={
                "status_code": 200,
                "message": "Logged in successfully.",
                "data": {"refresh": "token", "access": "token"},
                "errors": None,
            },
        )
    ],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@handle_api_exceptions
def login(request):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    return api_response(
        message="Logged in successfully.",
        data=serializer.validated_data,
    )


@extend_schema(
    summary="Gửi OTP xác thực tài khoản",
    request=OTPRequestSerializer,
    responses={200: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES},
    examples=[
        OpenApiExample(
            "Success",
            value={"status_code": 200, "message": "OTP sent.", "data": None, "errors": None},
        )
    ],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@handle_api_exceptions
def otp_request(request):
    serializer = OTPRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    contact_info = serializer.validated_data["contact_info"]

    if not User.objects.filter(email=contact_info).exists():
        return api_response(
            message="User with this email not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            errors={"contact_info": ["User with this email not found."]},
        )

    issue_otp(contact_info, "account_verify")
    return api_response(message="OTP sent.")


@extend_schema(
    summary="Xác thực OTP tài khoản",
    request=OTPVerifySerializer,
    responses={200: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES},
    examples=[
        OpenApiExample(
            "Success",
            value={
                "status_code": 200,
                "message": "OTP verified and account activated.",
                "data": None,
                "errors": None,
            },
        )
    ],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@handle_api_exceptions
def otp_verify(request):
    serializer = OTPVerifySerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    contact_info = serializer.validated_data["contact_info"]
    otp_code = serializer.validated_data["otp_code"]

    otp_obj = AccountOTP.objects.filter(
        contact_info=contact_info,
        otp_code=otp_code,
        purpose="account_verify",
        is_verified=False,
        expired_at__gt=timezone.now(),
    ).first()
    if not otp_obj:
        return api_response(
            message="Invalid or expired OTP.",
            status_code=status.HTTP_400_BAD_REQUEST,
            errors={"otp_code": ["Invalid or expired OTP."]},
        )

    otp_obj.is_verified = True
    otp_obj.save(update_fields=["is_verified"])

    user = User.objects.filter(email=contact_info).first()
    if user:
        user.is_active = True
        user.save(update_fields=["is_active"])

    return api_response(message="OTP verified and account activated.")


@extend_schema(
    summary="Yêu cầu khôi phục mật khẩu",
    request=ForgotPasswordSerializer,
    responses={200: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["POST"])
@permission_classes([AllowAny])
@handle_api_exceptions
def password_forgot(request):
    serializer = ForgotPasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    email = serializer.validated_data["email"]

    if not User.objects.filter(email=email).exists():
        return api_response(
            message="User with this email not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            errors={"email": ["User with this email not found."]},
        )

    issue_otp(email, "password_reset")
    return api_response(message="OTP sent.")


@extend_schema(
    summary="Đặt mật khẩu mới sau OTP",
    request=ResetPasswordSerializer,
    responses={200: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["POST"])
@permission_classes([AllowAny])
@handle_api_exceptions
def password_reset(request):
    serializer = ResetPasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    email = serializer.validated_data["email"]
    otp_code = serializer.validated_data["otp_code"]

    otp_obj = AccountOTP.objects.filter(
        contact_info=email,
        otp_code=otp_code,
        purpose="password_reset",
        is_verified=False,
        expired_at__gt=timezone.now(),
    ).first()
    if not otp_obj:
        return api_response(
            message="Invalid or expired OTP.",
            status_code=status.HTTP_400_BAD_REQUEST,
            errors={"otp_code": ["Invalid or expired OTP."]},
        )

    user = User.objects.filter(email=email).first()
    if not user:
        return api_response(
            message="User with this email not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            errors={"email": ["User with this email not found."]},
        )

    user.set_password(serializer.validated_data["new_password"])
    user.save(update_fields=["password"])
    otp_obj.is_verified = True
    otp_obj.save(update_fields=["is_verified"])
    return api_response(message="Password reset successfully.")


@extend_schema(
    methods=["GET"],
    summary="Xem thông tin cá nhân hiện tại",
    responses={200: PROFILE_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@extend_schema(
    methods=["PATCH"],
    summary="Cập nhật thông số thể chất",
    request=ProfileUpdateSerializer,
    responses={200: PROFILE_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def profile(request):
    if request.method == "GET":
        return api_response(
            message="Profile retrieved successfully.",
            data=ProfileSerializer(request.user).data,
        )

    serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    user = serializer.save()
    return api_response(
        message="Profile updated successfully.",
        data=ProfileSerializer(user).data,
    )


@extend_schema(
    summary="Đổi mật khẩu khi đã đăng nhập",
    request=ChangePasswordSerializer,
    responses={200: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def password_change(request):
    serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return validation_error_response(serializer)
    request.user.set_password(serializer.validated_data["new_password"])
    request.user.save(update_fields=["password"])
    return api_response(message="Password changed successfully.")


@extend_schema(
    summary="Đăng xuất",
    request=inline_serializer(name="LogoutRequest", fields={"refresh": serializers.CharField()}),
    responses={200: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES},
    examples=[
        OpenApiExample(
            "Success",
            value={
                "status_code": 200,
                "message": "Logged out successfully.",
                "data": None,
                "errors": None,
            },
        )
    ],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@handle_api_exceptions
def logout(request):
    try:
        refresh = request.data.get("refresh")
        if not refresh:
            return api_response(
                message="Refresh token required.",
                status_code=status.HTTP_400_BAD_REQUEST,
                errors={"refresh": ["Refresh token required."]},
            )
        token = RefreshToken(refresh)
        token.blacklist()
        return api_response(message="Logged out successfully.")
    except Exception:
        return api_response(
            message="Token is invalid or expired.",
            status_code=status.HTTP_400_BAD_REQUEST,
            errors={"refresh": ["Token is invalid or expired."]},
        )


@extend_schema(
    summary="Danh sách & tìm kiếm tài khoản",
    parameters=[
        OpenApiParameter(name="role", type=OpenApiTypes.STR, enum=["admin", "staff", "user"]),
        OpenApiParameter(name="search", type=OpenApiTypes.STR),
        OpenApiParameter(name="page", type=OpenApiTypes.INT),
    ],
    responses={200: ADMIN_ACCOUNT_LIST_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_account_list(request):
    queryset = User.objects.all().order_by("-date_joined")
    role = request.query_params.get("role")
    search = request.query_params.get("search")

    if role == "admin":
        queryset = queryset.filter(is_superuser=True)
    elif role == "staff":
        queryset = queryset.filter(is_staff=True, is_superuser=False)
    elif role == "user":
        queryset = queryset.filter(is_staff=False, is_superuser=False)

    if search:
        queryset = queryset.filter(Q(email__icontains=search) | Q(phone_number__icontains=search))

    paginator = PageNumberPagination()
    paginator.page_size = 20
    page = paginator.paginate_queryset(queryset, request)
    serializer = AdminAccountListSerializer(page, many=True)
    paginated = paginator.get_paginated_response(serializer.data)
    return api_response(
        message="Accounts retrieved successfully.",
        data=paginated.data,
    )


@extend_schema(
    summary="Xem chi tiết một tài khoản",
    responses={200: ADMIN_ACCOUNT_DETAIL_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_account_detail(request, id):
    user = User.objects.filter(id=id).first()
    if not user:
        return api_response(
            message="Account not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            errors={"id": ["Account not found."]},
        )
    return api_response(
        message="Account retrieved successfully.",
        data=AdminAccountDetailSerializer(user).data,
    )


@extend_schema(
    summary="Khóa hoặc mở khóa tài khoản",
    request=AccountStatusSerializer,
    responses={200: ADMIN_ACCOUNT_DETAIL_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["PATCH"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_account_status(request, id):
    user = User.objects.filter(id=id).first()
    if not user:
        return api_response(
            message="Account not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            errors={"id": ["Account not found."]},
        )

    serializer = AccountStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    new_status = serializer.validated_data["is_active"]

    if user.is_superuser and not new_status:
        active_admin_count = User.objects.filter(is_superuser=True, is_active=True).count()
        if active_admin_count <= 1:
            return api_response(
                message="Cannot lock the only active admin account.",
                status_code=status.HTTP_400_BAD_REQUEST,
                errors={"is_active": ["Cannot lock the only active admin account."]},
            )

    user.is_active = new_status
    user.save(update_fields=["is_active"])
    return api_response(
        message="Account status updated successfully.",
        data=AdminAccountDetailSerializer(user).data,
    )


@extend_schema(
    summary="Đặt lại mật khẩu bởi admin",
    request=AdminPasswordResetSerializer,
    responses={200: API_EMPTY_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_account_reset_password(request, id):
    user = User.objects.filter(id=id).first()
    if not user:
        return api_response(
            message="Account not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            errors={"id": ["Account not found."]},
        )

    serializer = AdminPasswordResetSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    new_password = serializer.validated_data.get("new_password") or "NutriLens@123"
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return api_response(message="Password reset successfully.")


@extend_schema(
    summary="Thay đổi vai trò hoặc nhóm quyền",
    request=AccountRoleSerializer,
    responses={200: ADMIN_ACCOUNT_DETAIL_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["PATCH"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_account_role(request, id):
    user = User.objects.filter(id=id).first()
    if not user:
        return api_response(
            message="Account not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            errors={"id": ["Account not found."]},
        )

    serializer = AccountRoleSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)

    role = serializer.validated_data.get("role")
    if role == "admin":
        user.is_staff = True
        user.is_superuser = True
    elif role == "staff":
        user.is_staff = True
        user.is_superuser = False
    elif role == "user":
        if user.is_superuser and User.objects.filter(is_superuser=True, is_active=True).count() <= 1:
            return api_response(
                message="Cannot remove admin role from the only active admin account.",
                status_code=status.HTTP_400_BAD_REQUEST,
                errors={"role": ["Cannot remove admin role from the only active admin account."]},
            )
        user.is_staff = False
        user.is_superuser = False

    user.save(update_fields=["is_staff", "is_superuser"])

    if "group_ids" in serializer.validated_data:
        user.groups.set(Group.objects.filter(id__in=serializer.validated_data["group_ids"]))

    return api_response(
        message="Account role updated successfully.",
        data=AdminAccountDetailSerializer(user).data,
    )


@extend_schema(
    summary="Cấu hình định mức sử dụng",
    request=QuotaConfigSerializer,
    responses={200: QUOTA_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["PUT"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_quota_update(request):
    quota, _ = QuotaConfig.objects.get_or_create(key="guest_scan_limit")
    serializer = QuotaConfigSerializer(quota, data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    serializer.save()
    return api_response(
        message="Quota updated successfully.",
        data=serializer.data,
    )
