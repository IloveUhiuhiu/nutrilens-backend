from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, ActivityLevel, WeightHistory, AccountOTP

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'gender', 'is_staff')
    search_fields = ('id', 'username', 'email')
    
    # Chia nhóm các trường thông tin trong trang chi tiết
    fieldsets = UserAdmin.fieldsets + (
        ('Thông tin thể trạng (NutriLens)', {
            'fields': ('gender', 'birth_date', 'height', 'activity_level')
        }),
    )
    # Sắp xếp theo ID mới nhất
    ordering = ('-date_joined',)

@admin.register(ActivityLevel)
class ActivityLevelAdmin(admin.ModelAdmin):
    list_display = ('level_name', 'ratio')

@admin.register(WeightHistory)
class WeightHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'weight', 'measured_at')
    list_filter = ('user',)

@admin.register(AccountOTP)
class AccountOTPAdmin(admin.ModelAdmin):
    list_display = ('contact_info', 'otp_code', 'is_verified', 'expired_at')