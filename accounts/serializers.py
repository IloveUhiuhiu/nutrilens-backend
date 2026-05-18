from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("email", "password", "full_name", "gender", "birth_date", "height", "activity_level")

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data.get("full_name", ""),  
            gender=validated_data.get("gender", "M"),
            birth_date=validated_data.get("birth_date"),
            height=validated_data.get("height", 0),
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
    otp_code = serializers.CharField()