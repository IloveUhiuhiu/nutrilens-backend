from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, ActivityLevel, WeightHistory, AccountOTP, QuotaConfig

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'email', 'phone_number', 'gender', 'goal', 'is_staff', 'is_active')
    search_fields = ('id', 'email', 'phone_number')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Thông tin cá nhân', {'fields': ('full_name', 'phone_number')}),
        ('Thông tin thể trạng (NutriLens)', {
            'fields': ('gender', 'birth_date', 'height', 'goal', 'tdee', 'activity_level')
        }),
        ('Quyền hạn', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Mốc thời gian', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_superuser'),
        }),
    )

@admin.register(ActivityLevel)
class ActivityLevelAdmin(admin.ModelAdmin):
    list_display = ('level_name', 'ratio')

@admin.register(WeightHistory)
class WeightHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'weight', 'measured_at')
    list_filter = ('user',)

@admin.register(AccountOTP)
class AccountOTPAdmin(admin.ModelAdmin):
    list_display = ('contact_info', 'otp_code', 'purpose', 'is_verified', 'expired_at')

@admin.register(QuotaConfig)
class QuotaConfigAdmin(admin.ModelAdmin):
    list_display = ('key', 'guest_scan_limit', 'updated_at')
