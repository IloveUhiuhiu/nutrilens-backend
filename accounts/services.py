from datetime import timedelta
import logging
import random

from django.contrib.auth.models import Group
from django.utils import timezone

from .models import AccountOTP, User
from .tasks import send_otp_email_task


logger = logging.getLogger(__name__)


class AccountServiceError(Exception):
    """Chức năng: lỗi nghiệp vụ accounts. Đầu vào: message, field. Đầu ra: exception có field lỗi."""

    def __init__(self, message, field="detail"):
        self.message = message
        self.field = field
        super().__init__(message)


def generate_otp():
    """Chức năng: tạo OTP 6 số. Đầu vào: không có. Đầu ra: chuỗi OTP."""
    return f"{random.randint(100000, 999999)}"


def issue_otp(contact_info, purpose):
    """Chức năng: tạo và gửi OTP. Đầu vào: contact_info, purpose. Đầu ra: AccountOTP mới."""
    now = timezone.now()
    AccountOTP.objects.filter(
        contact_info=contact_info,
        purpose=purpose,
        is_verified=False,
    ).update(expired_at=now)

    otp_code = generate_otp()
    otp = AccountOTP.objects.create(
        contact_info=contact_info,
        otp_code=otp_code,
        purpose=purpose,
        expired_at=now + timedelta(minutes=5),
        is_verified=False,
    )
    logger.info("OTP issued for %s (%s)", contact_info, purpose)
    send_otp_email_task.delay(contact_info, otp_code)
    return otp


def find_valid_otp(contact_info, otp_code, purpose):
    """Chức năng: tìm OTP hợp lệ. Đầu vào: contact, mã OTP, purpose. Đầu ra: AccountOTP hoặc None."""
    return AccountOTP.objects.filter(
        contact_info=contact_info,
        otp_code=otp_code,
        purpose=purpose,
        is_verified=False,
        expired_at__gt=timezone.now(),
    ).first()


def verify_account_otp(contact_info, otp_code):
    """Chức năng: xác thực OTP đăng ký và active user. Đầu vào: email, otp. Đầu ra: User hoặc None."""
    otp = find_valid_otp(contact_info, otp_code, "account_verify")
    if not otp:
        raise AccountServiceError("Invalid or expired OTP.", field="otp_code")

    otp.is_verified = True
    otp.save(update_fields=["is_verified"])

    user = User.objects.filter(email=contact_info).first()
    if user:
        user.is_active = True
        user.save(update_fields=["is_active"])
    return user


def reset_password_with_otp(email, otp_code, new_password):
    """Chức năng: reset password bằng OTP. Đầu vào: email, otp, password mới. Đầu ra: User."""
    otp = find_valid_otp(email, otp_code, "password_reset")
    if not otp:
        raise AccountServiceError("Invalid or expired OTP.", field="otp_code")

    user = User.objects.filter(email=email).first()
    if not user:
        raise AccountServiceError("User with this email not found.", field="email")

    user.set_password(new_password)
    user.save(update_fields=["password"])
    otp.is_verified = True
    otp.save(update_fields=["is_verified"])
    return user


def update_account_status(user, is_active):
    """Chức năng: cập nhật trạng thái account. Đầu vào: user, is_active. Đầu ra: user đã cập nhật."""
    if user.is_superuser and not is_active:
        active_admin_count = User.objects.filter(is_superuser=True, is_active=True).count()
        if active_admin_count <= 1:
            raise AccountServiceError("Cannot lock the only active admin account.", field="is_active")

    user.is_active = is_active
    user.save(update_fields=["is_active"])
    return user


def update_account_role(user, role=None, group_ids=None):
    """Chức năng: cập nhật role/group account. Đầu vào: user, role, group_ids. Đầu ra: user đã cập nhật."""
    if role == "admin":
        user.is_staff = True
        user.is_superuser = True
    elif role == "staff":
        user.is_staff = True
        user.is_superuser = False
    elif role == "user":
        if user.is_superuser and User.objects.filter(is_superuser=True, is_active=True).count() <= 1:
            raise AccountServiceError("Cannot remove admin role from the only active admin account.", field="role")
        user.is_staff = False
        user.is_superuser = False

    if role:
        user.save(update_fields=["is_staff", "is_superuser"])

    if group_ids is not None:
        user.groups.set(Group.objects.filter(id__in=group_ids))

    return user
