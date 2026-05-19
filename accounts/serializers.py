from django.contrib.auth import authenticate
from django.contrib.auth.models import Group
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import ActivityLevel, QuotaConfig, User, WeightHistory


class ActivityLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLevel
        fields = ("id", "level_name", "description", "ratio")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "full_name",
            "phone_number",
            "gender",
            "birth_date",
            "height",
            "goal",
            "activity_level",
        )

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data.get("full_name", ""),
            phone_number=validated_data.get("phone_number"),
            gender=validated_data.get("gender", "M"),
            birth_date=validated_data.get("birth_date"),
            height=validated_data.get("height", 0),
            goal=validated_data.get("goal", "maintain"),
            activity_level=validated_data.get("activity_level"),
            is_active=False,
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["email"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        if not user.is_active:
            raise serializers.ValidationError("Account not verified.")
        refresh = RefreshToken.for_user(user)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}


class OTPRequestSerializer(serializers.Serializer):
    contact_info = serializers.EmailField()


class OTPVerifySerializer(serializers.Serializer):
    contact_info = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class WeightHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WeightHistory
        fields = ("weight", "measured_at")


class ProfileSerializer(serializers.ModelSerializer):
    activity_level = ActivityLevelSerializer(read_only=True)
    current_weight = serializers.FloatField(read_only=True)
    bmi = serializers.FloatField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "email",
            "phone_number",
            "gender",
            "birth_date",
            "height",
            "current_weight",
            "bmi",
            "goal",
            "activity_level",
            "tdee",
        )


class ProfileUpdateSerializer(serializers.ModelSerializer):
    weight = serializers.FloatField(write_only=True, required=False, min_value=1)

    class Meta:
        model = User
        fields = ("height", "weight", "goal", "activity_level")
        extra_kwargs = {
            "height": {"required": False, "min_value": 1},
            "goal": {"required": False},
            "activity_level": {"required": False},
        }

    def update(self, instance, validated_data):
        weight = validated_data.pop("weight", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if weight is not None:
            WeightHistory.objects.create(user=instance, weight=weight)
        instance.refresh_tdee(current_weight=weight)
        return instance


class AdminAccountListSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "full_name", "email", "phone_number", "role", "is_active", "date_joined")

    def get_role(self, obj):
        if obj.is_superuser:
            return "admin"
        if obj.is_staff:
            return "staff"
        return "user"


class AdminAccountDetailSerializer(ProfileSerializer):
    role = serializers.SerializerMethodField()
    weight_histories = WeightHistorySerializer(many=True, read_only=True)
    daily_logs = serializers.SerializerMethodField()

    class Meta(ProfileSerializer.Meta):
        fields = ProfileSerializer.Meta.fields + (
            "role",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "weight_histories",
            "daily_logs",
            "date_joined",
        )

    def get_role(self, obj):
        if obj.is_superuser:
            return "admin"
        if obj.is_staff:
            return "staff"
        return "user"

    def get_daily_logs(self, obj):
        return [
            {
                "id": log.id,
                "date": log.date,
                "total_calories": log.total_calories,
                "total_protein": log.total_protein,
                "total_carbs": log.total_carbs,
                "total_fat": log.total_fat,
                "total_weight": log.total_weight,
            }
            for log in obj.daily_logs.order_by("-date")[:30]
        ]


class AccountStatusSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class AdminPasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(required=False, allow_blank=False, min_length=8)


class AccountRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=("user", "staff", "admin"), required=False)
    group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )

    def validate_group_ids(self, value):
        existing = set(Group.objects.filter(id__in=value).values_list("id", flat=True))
        missing = set(value) - existing
        if missing:
            raise serializers.ValidationError(f"Groups not found: {sorted(missing)}")
        return value


class QuotaConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotaConfig
        fields = ("guest_scan_limit", "updated_at")
        read_only_fields = ("updated_at",)
