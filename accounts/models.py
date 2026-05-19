from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from datetime import date
import uuid

class UserManager(BaseUserManager):
    """Custom manager cho việc sử dụng email thay cho username"""
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        """Tạo user thông thường."""
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Tạo superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)

class ActivityLevel(models.Model):
    """Mức độ vận động"""
    level_name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    ratio = models.FloatField(help_text="Hệ số PAL (Physical Activity Level)")

    def __str__(self):
        return self.level_name

class User(AbstractUser):
    """Custom User Model"""
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    GOAL_CHOICES = [
        ('maintain', 'Maintain weight'),
        ('lose_weight', 'Lose weight'),
        ('gain_weight', 'Gain weight'),
    ]
    
    id = models.CharField(
        primary_key=True, 
        max_length=20, 
        editable=False, 
        unique=True
    )

    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    full_name = models.CharField(max_length=150, blank=True, null=True)

    username = None 
    first_name = None
    last_name = None

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    birth_date = models.DateField(null=True, blank=True)
    height = models.FloatField(default=0, help_text="Height in cm")
    goal = models.CharField(max_length=20, choices=GOAL_CHOICES, default='maintain')
    tdee = models.FloatField(default=0, help_text="Total Daily Energy Expenditure")
    # Liên kết với ActivityLevel
    activity_level = models.ForeignKey(ActivityLevel, on_delete=models.SET_NULL, null=True, related_name='users')

    def save(self, *args, **kwargs):
        # Chỉ sinh ID khi bản ghi được tạo lần đầu (chưa có id)
        if not self.id:
            unique_id = uuid.uuid4().hex[:8]
            
            # Kiểm tra vai trò để gán tiền tố tương ứng
            if self.is_superuser or self.is_staff:
                prefix = "admin"
            else:
                prefix = "user"
                
            self.id = f"{prefix}_{unique_id}"
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.id} - {self.email}"

    @property
    def current_weight(self):
        latest = self.weight_histories.order_by('-measured_at').first()
        return latest.weight if latest else 0

    @property
    def bmi(self):
        weight = self.current_weight
        if not self.height or not weight:
            return 0
        height_m = self.height / 100
        return round(weight / (height_m * height_m), 2)

    def calculateTDEE(self, current_weight):
        """
        Tính toán TDEE dựa trên công thức Mifflin-St Jeor
        TDEE = BMR * Activity_Ratio
        """
        if not self.birth_date or not self.height or not self.activity_level:
            return 0
        
        # Tính tuổi
        age = date.today().year - self.birth_date.year
        
        # Tính BMR
        if self.gender == 'M':
            bmr = (10 * current_weight) + (6.25 * self.height) - (5 * age) + 5
        else:
            bmr = (10 * current_weight) + (6.25 * self.height) - (5 * age) - 161
            
        return bmr * self.activity_level.ratio

    def refresh_tdee(self, current_weight=None, commit=True):
        current_weight = current_weight if current_weight is not None else self.current_weight
        self.tdee = round(self.calculateTDEE(current_weight), 2)
        if commit:
            self.save(update_fields=['tdee'])
        return self.tdee

class WeightHistory(models.Model):
    """Lịch sử cân nặng"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='weight_histories')
    weight = models.FloatField()
    measured_at = models.DateTimeField(auto_now_add=True)
 
class AccountOTP(models.Model):
    """Quản lý OTP xác thực"""
    PURPOSE_CHOICES = [
        ('account_verify', 'Account verification'),
        ('password_reset', 'Password reset'),
    ]

    contact_info = models.CharField(max_length=255) # Email 
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default='account_verify')
    expired_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)

class QuotaConfig(models.Model):
    """Cấu hình định mức sử dụng."""
    key = models.CharField(max_length=50, unique=True, default='guest_scan_limit')
    guest_scan_limit = models.PositiveIntegerField(default=2)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key}: {self.guest_scan_limit}"
