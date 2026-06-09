from django.contrib.auth.models import Group, Permission
from rest_framework import serializers


class PermissionSerializer(serializers.ModelSerializer):
    content_type_label = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = ("id", "name", "codename", "content_type", "content_type_label")

    def get_content_type_label(self, obj):
        return f"{obj.content_type.app_label}.{obj.content_type.model}"


class GroupDetailSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        write_only=True,
        required=False,
        source="permissions",
    )
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ("id", "name", "permissions", "permission_ids", "member_count")

    def get_member_count(self, obj):
        return obj.user_set.count()

    def create(self, validated_data):
        permissions = validated_data.pop("permissions", [])
        group = Group.objects.create(**validated_data)
        group.permissions.set(permissions)
        return group

    def update(self, instance, validated_data):
        permissions = validated_data.pop("permissions", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if permissions is not None:
            instance.permissions.set(permissions)
        return instance


class GroupListSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    permission_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ("id", "name", "member_count", "permission_count")

    def get_member_count(self, obj):
        return obj.user_set.count()

    def get_permission_count(self, obj):
        return obj.permissions.count()
