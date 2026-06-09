from django.db.models import Q
from django.conf import settings
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from core.api import (
    API_EMPTY_RESPONSE,
    DEFAULT_ERROR_RESPONSES,
    api_response,
    handle_api_exceptions,
    not_found_response,
    paginate_queryset,
    validation_error_response,
)
from core.cloudinary_upload import CloudinaryUploadError
from .models import AccountOTP, ActivityLevel, QuotaConfig, User
from .serializers import (
    AccountOTPAdminSerializer,
    AccountRoleSerializer,
    AccountStatusSerializer,
    ActivityLevelSerializer,
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
from .services import AccountServiceError, issue_otp, reset_password_with_otp, update_account_role, update_account_status, verify_account_otp


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
                "avatar_url": serializers.URLField(),
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

ACTIVITY_LEVEL_LIST_RESPONSE = inline_serializer(
    name="ActivityLevelListResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": ActivityLevelSerializer(many=True, read_only=True),
        "errors": serializers.JSONField(allow_null=True),
    },
)


ACTIVITY_LEVEL_RESPONSE = inline_serializer(
    name="ActivityLevelResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": ActivityLevelSerializer(read_only=True),
        "errors": serializers.JSONField(allow_null=True),
    },
)


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
                "data": {
                    "id": "user_xxxx",
                    "email": "test@gmail.com",
                    "avatar_url": "https://res.cloudinary.com/example/avatar.jpg",
                },
                "errors": None,
            },
        )
    ],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@handle_api_exceptions
def register(request):
    """Chức năng: API đăng ký tài khoản. Đầu vào: thông tin user và password. Đầu ra: id, email hoặc lỗi."""
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
        data={"id": user.id, "email": user.email, "avatar_url": user.avatar_url},
    )


@extend_schema(
    summary="Danh sách mức độ vận động",
    responses={200: ACTIVITY_LEVEL_LIST_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([AllowAny])
@handle_api_exceptions
def activity_level_list(request):
    """Chức năng: API danh sách mức vận động. Đầu vào: không có. Đầu ra: danh sách ActivityLevel."""
    queryset = ActivityLevel.objects.all().order_by("id")
    return api_response(
        message="Activity levels retrieved successfully.",
        data=ActivityLevelSerializer(queryset, many=True).data,
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
    """Chức năng: API đăng nhập. Đầu vào: email và password. Đầu ra: access/refresh token hoặc lỗi."""
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
    """Chức năng: API yêu cầu OTP xác thực. Đầu vào: email. Đầu ra: thông báo gửi OTP hoặc lỗi."""
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
    """Chức năng: API xác thực OTP tài khoản. Đầu vào: email và otp_code. Đầu ra: kích hoạt tài khoản hoặc lỗi."""
    serializer = OTPVerifySerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    contact_info = serializer.validated_data["contact_info"]
    otp_code = serializer.validated_data["otp_code"]
    try:
        verify_account_otp(contact_info, otp_code)
    except AccountServiceError as exc:
        return api_response(
            message=exc.message,
            status_code=status.HTTP_400_BAD_REQUEST,
            errors={exc.field: [exc.message]},
        )

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
    """Chức năng: API quên mật khẩu. Đầu vào: email. Đầu ra: gửi OTP reset hoặc lỗi."""
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
    """Chức năng: API đặt mật khẩu sau OTP. Đầu vào: email, otp_code, new_password. Đầu ra: xác nhận reset hoặc lỗi."""
    serializer = ResetPasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    try:
        reset_password_with_otp(
            serializer.validated_data["email"],
            serializer.validated_data["otp_code"],
            serializer.validated_data["new_password"],
        )
    except AccountServiceError as exc:
        status_code = status.HTTP_404_NOT_FOUND if exc.field == "email" else status.HTTP_400_BAD_REQUEST
        return api_response(
            message=exc.message,
            status_code=status_code,
            errors={exc.field: [exc.message]},
        )
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
    """Chức năng: API xem/cập nhật profile. Đầu vào: GET hoặc PATCH profile. Đầu ra: thông tin profile."""
    if request.method == "GET":
        return api_response(
            message="Profile retrieved successfully.",
            data=ProfileSerializer(request.user).data,
        )

    serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    try:
        user = serializer.save()
    except CloudinaryUploadError as exc:
        return api_response(
            exc.public_message,
            status_code=exc.status_code,
            errors={"avatar": [exc.detail or exc.public_message]},
        )
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
    """Chức năng: API đổi mật khẩu đã đăng nhập. Đầu vào: old_password, new_password. Đầu ra: xác nhận hoặc lỗi."""
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
    """Chức năng: API đăng xuất. Đầu vào: refresh token. Đầu ra: token bị blacklist hoặc lỗi."""
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
        OpenApiParameter(name="start_date", type=OpenApiTypes.DATE),
        OpenApiParameter(name="end_date", type=OpenApiTypes.DATE),
        OpenApiParameter(name="page", type=OpenApiTypes.INT),
    ],
    responses={200: ADMIN_ACCOUNT_LIST_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_account_list(request):
    """Chức năng: API admin danh sách tài khoản. Đầu vào: role/search/date/page. Đầu ra: danh sách user phân trang."""
    queryset = User.objects.all().order_by("-date_joined")
    role = request.query_params.get("role")
    search = request.query_params.get("search")
    start_date = request.query_params.get("start_date")
    end_date = request.query_params.get("end_date")

    if role == "admin":
        queryset = queryset.filter(is_superuser=True)
    elif role == "staff":
        queryset = queryset.filter(is_staff=True, is_superuser=False)
    elif role == "user":
        queryset = queryset.filter(is_staff=False, is_superuser=False)

    if search:
        queryset = queryset.filter(
            Q(id__icontains=search)
            | Q(email__icontains=search)
            | Q(full_name__icontains=search)
            | Q(phone_number__icontains=search)
        )

    if start_date:
        queryset = queryset.filter(date_joined__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(date_joined__date__lte=end_date)

    return api_response(
        message="Accounts retrieved successfully.",
        data=paginate_queryset(request, queryset, AdminAccountListSerializer),
    )


@extend_schema(
    summary="Xem chi tiết một tài khoản",
    responses={200: ADMIN_ACCOUNT_DETAIL_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_account_detail(request, id):
    """Chức năng: API admin chi tiết tài khoản. Đầu vào: user id. Đầu ra: profile chi tiết hoặc lỗi."""
    user = User.objects.filter(id=id).first()
    if not user:
        return not_found_response("Account not found.")
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
    """Chức năng: API admin khóa/mở tài khoản. Đầu vào: user id, is_active. Đầu ra: user đã cập nhật hoặc lỗi."""
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

    try:
        update_account_status(user, new_status)
    except AccountServiceError as exc:
        return api_response(
            message=exc.message,
            status_code=status.HTTP_400_BAD_REQUEST,
            errors={exc.field: [exc.message]},
        )
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
    """Chức năng: API admin reset mật khẩu. Đầu vào: user id, new_password tùy chọn. Đầu ra: xác nhận hoặc lỗi."""
    user = User.objects.filter(id=id).first()
    if not user:
        return not_found_response("Account not found.")

    serializer = AdminPasswordResetSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    new_password = serializer.validated_data.get("new_password") or settings.ADMIN_DEFAULT_RESET_PASSWORD
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
    """Chức năng: API admin đổi vai trò/nhóm quyền. Đầu vào: user id, role/group_ids. Đầu ra: user đã cập nhật."""
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

    try:
        update_account_role(
            user,
            role=serializer.validated_data.get("role"),
            group_ids=serializer.validated_data.get("group_ids") if "group_ids" in serializer.validated_data else None,
        )
    except AccountServiceError as exc:
        return api_response(
            message=exc.message,
            status_code=status.HTTP_400_BAD_REQUEST,
            errors={exc.field: [exc.message]},
        )

    return api_response(
        message="Account role updated successfully.",
        data=AdminAccountDetailSerializer(user).data,
    )


@extend_schema(
    methods=["GET"],
    summary="Xem cấu hình định mức sử dụng",
    responses={200: QUOTA_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@extend_schema(
    methods=["PUT"],
    summary="Cập nhật cấu hình định mức sử dụng",
    request=QuotaConfigSerializer,
    responses={200: QUOTA_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET", "PUT"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_quota(request):
    """Chức năng: API admin xem/cập nhật quota guest. Đầu vào: GET hoặc guest_scan_limit. Đầu ra: quota."""
    quota, _ = QuotaConfig.objects.get_or_create(key="guest_scan_limit")
    if request.method == "GET":
        return api_response(
            message="Quota retrieved successfully.",
            data=QuotaConfigSerializer(quota).data,
        )
    serializer = QuotaConfigSerializer(quota, data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    serializer.save()
    return api_response(
        message="Quota updated successfully.",
        data=serializer.data,
    )


ADMIN_OTP_LIST_RESPONSE = inline_serializer(
    name="AdminOTPListResponse",
    fields={
        "status_code": serializers.IntegerField(),
        "message": serializers.CharField(),
        "data": inline_serializer(
            name="AdminOTPListPage",
            fields={
                "count": serializers.IntegerField(),
                "next": serializers.CharField(allow_null=True, allow_blank=True),
                "previous": serializers.CharField(allow_null=True, allow_blank=True),
                "results": serializers.ListField(),
            },
        ),
        "errors": serializers.JSONField(allow_null=True),
    },
)


@extend_schema(
    summary="Admin danh sách OTP xác thực",
    parameters=[
        OpenApiParameter(name="search", type=OpenApiTypes.STR),
        OpenApiParameter(name="purpose", type=OpenApiTypes.STR),
        OpenApiParameter(name="is_verified", type=OpenApiTypes.BOOL),
        OpenApiParameter(name="page", type=OpenApiTypes.INT),
    ],
    responses={200: ADMIN_OTP_LIST_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_otp_list(request):
    """Chức năng: API admin danh sách OTP. Đầu vào: search/purpose/is_verified/page. Đầu ra: danh sách AccountOTP."""
    from .models import AccountOTP
    queryset = AccountOTP.objects.all().order_by("-expired_at")
    search = request.query_params.get("search")
    purpose = request.query_params.get("purpose")
    is_verified = request.query_params.get("is_verified")

    if search:
        queryset = queryset.filter(Q(contact_info__icontains=search) | Q(otp_code__icontains=search))
    if purpose:
        queryset = queryset.filter(purpose=purpose)
    if is_verified is not None:
        queryset = queryset.filter(is_verified=(is_verified.lower() == "true"))

    return api_response(
        message="OTP records retrieved successfully.",
        data=paginate_queryset(request, queryset, AccountOTPAdminSerializer),
    )


@extend_schema(
    summary="Admin danh sách và tạo mức vận động",
    request=ActivityLevelSerializer,
    responses={200: ACTIVITY_LEVEL_LIST_RESPONSE, 201: ACTIVITY_LEVEL_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_activity_level_list_create(request):
    """Chức năng: API admin list/create mức vận động. Đầu vào: payload nếu POST. Đầu ra: danh sách hoặc ActivityLevel mới."""
    if request.method == "GET":
        queryset = ActivityLevel.objects.all().order_by("id")
        return api_response(
            message="Activity levels retrieved successfully.",
            data=paginate_queryset(request, queryset, ActivityLevelSerializer),
        )

    serializer = ActivityLevelSerializer(data=request.data)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    activity_level = serializer.save()
    return api_response(
        message="Activity level created successfully.",
        status_code=status.HTTP_201_CREATED,
        data=ActivityLevelSerializer(activity_level).data,
    )


@extend_schema(
    summary="Admin chi tiết mức vận động",
    request=ActivityLevelSerializer,
    responses={200: ACTIVITY_LEVEL_RESPONSE, **DEFAULT_ERROR_RESPONSES},
)
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
@handle_api_exceptions
def admin_activity_level_detail(request, id):
    """Chức năng: API admin xem/sửa/xóa mức vận động. Đầu vào: id và payload tùy method. Đầu ra: ActivityLevel hoặc xác nhận xóa."""
    activity_level = ActivityLevel.objects.filter(id=id).first()
    if not activity_level:
        return api_response(
            message="Activity level not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            errors={"id": ["Activity level not found."]},
        )

    if request.method == "GET":
        return api_response(
            message="Activity level retrieved successfully.",
            data=ActivityLevelSerializer(activity_level).data,
        )

    if request.method == "DELETE":
        activity_level.delete()
        return api_response(message="Activity level deleted successfully.")

    serializer = ActivityLevelSerializer(activity_level, data=request.data, partial=True)
    if not serializer.is_valid():
        return validation_error_response(serializer)
    serializer.save()
    return api_response(
        message="Activity level updated successfully.",
        data=serializer.data,
    )
