from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegisterSerializer, LoginSerializer, OTPRequestSerializer, OTPVerifySerializer
from .models import AccountOTP, User
import logging
from .tasks import send_otp_email_task 
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiTypes, inline_serializer
from rest_framework import serializers
logger = logging.getLogger(__name__)

def generate_otp():
    """Generate a 6-digit OTP."""
    import random
    return f"{random.randint(100000, 999999)}"

@extend_schema(
    summary="Đăng ký",
    request=RegisterSerializer,
    responses={201: OpenApiTypes.OBJECT},
    examples=[OpenApiExample("Success", value={"id": "user_xxxx", "email": "test@gmail.com"})],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    """API to register a new user."""
    email = request.data.get("email")
    if email and User.objects.filter(email=email).exists():
        return Response({"detail": "Email already registered."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response({"id": user.id, "email": user.email}, status=status.HTTP_201_CREATED)

@extend_schema(
    summary="Đăng nhập",
    request=LoginSerializer,
    responses={200: OpenApiTypes.OBJECT},
    examples=[OpenApiExample("Success", value={"refresh": "token", "access": "token"})],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    """API to log in a user and return JWT tokens."""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(serializer.validated_data)

@extend_schema(
    summary="Gửi OTP",
    request=OTPRequestSerializer,
    responses={200: OpenApiTypes.OBJECT},
    examples=[OpenApiExample("Success", value={"detail": "OTP sent."})],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def otp_request(request):
    """API to request an OTP for email verification."""
    serializer = OTPRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    contact_info = serializer.validated_data["contact_info"]  # Email

    # Kiểm tra xem User có tồn tại không trước khi làm các việc khác
    if not User.objects.filter(email=econtact_info).exists():
        return Response({"detail": "User with this email not found."}, status=status.HTTP_404_NOT_FOUND)

    # Vô hiệu hóa các OTP cũ của email này trước khi tạo cái mới
    AccountOTP.objects.filter(contact_info=contact_info, is_verified=False).update(expired_at=timezone.now())

    otp = generate_otp()

    # Save OTP to the database
    AccountOTP.objects.create(
        contact_info=contact_info,
        otp_code=otp,
        expired_at=timezone.now() + timedelta(minutes=5),
        is_verified=False,
    )

    # Log OTP to console
    logger.info("OTP for %s: %s", contact_info, otp)

    # Send OTP via email
    send_otp_email_task.delay(contact_info, otp)

    return Response({"detail": "OTP sent."})

@extend_schema(
    summary="Xác thực OTP",
    request=OTPVerifySerializer,
    responses={200: OpenApiTypes.OBJECT},
    examples=[OpenApiExample("Success", value={"detail": "OTP verified and account activated."})],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def otp_verify(request):
    """API to verify an OTP and activate the user."""
    serializer = OTPVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    contact_info = serializer.validated_data["contact_info"]
    otp_code = serializer.validated_data["otp_code"]

    # Check if OTP is valid
    otp_obj = AccountOTP.objects.filter(
        contact_info=contact_info,
        otp_code=otp_code,
        is_verified=False,
        expired_at__gt=timezone.now(),
    ).first()
    if not otp_obj:
        return Response({"detail": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)

    # Mark OTP as verified
    otp_obj.is_verified = True
    otp_obj.save()

    # Activate the user associated with the email
    user = User.objects.filter(email=contact_info).first()
    if user:
        user.is_active = True
        user.save()

    return Response({"detail": "OTP verified and account activated."})

@extend_schema(
    summary="Đăng xuất",
    request=inline_serializer(name="LogoutRequest", fields={"refresh": serializers.CharField()}),
    responses={200: OpenApiTypes.OBJECT},
    examples=[OpenApiExample("Success", value={"detail": "Logged out successfully."})],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"detail": "Refresh token required."}, status=status.HTTP_400_BAD_REQUEST)
        token = RefreshToken(refresh)
        token.blacklist()
        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)
    except Exception:
        return Response({"detail": "Token is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
