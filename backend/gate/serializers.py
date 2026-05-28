from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from rest_framework import serializers

from .models import AccessLog, GateDevice, Person, Vehicle

User = get_user_model()


class VehicleSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'owner', 'owner_name', 'plate_number', 'display_plate', 'canonical',
            'make', 'model', 'color', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['plate_number', 'canonical', 'created_at', 'updated_at']

    def validate_display_plate(self, value: str) -> str:
        from .plates import normalize_plate

        normalized = normalize_plate(value)
        if not normalized:
            raise serializers.ValidationError('Plate must contain letters or digits.')

        qs = Vehicle.objects.filter(plate_number=normalized)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A vehicle with this plate is already registered.')
        return value


class VehicleBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['id', 'display_plate', 'make', 'model', 'color', 'is_active']


class PersonSerializer(serializers.ModelSerializer):
    vehicles = VehicleBriefSerializer(many=True, read_only=True)
    vehicle_count = serializers.IntegerField(source='vehicles.count', read_only=True)

    class Meta:
        model = Person
        fields = [
            'id', 'full_name', 'email', 'phone', 'unit', 'is_active', 'notes',
            'vehicles', 'vehicle_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class GateDeviceSerializer(serializers.ModelSerializer):
    is_online = serializers.BooleanField(read_only=True)

    class Meta:
        model = GateDevice
        fields = [
            'id', 'name', 'location', 'api_key', 'is_active',
            'is_online', 'last_seen', 'created_at',
        ]
        read_only_fields = ['api_key', 'last_seen', 'created_at']


class AccessLogSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True, default=None)
    owner_name = serializers.CharField(source='matched_person.full_name', read_only=True, default=None)
    vehicle_plate = serializers.CharField(source='matched_vehicle.display_plate', read_only=True, default=None)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = AccessLog
        fields = [
            'id', 'created_at', 'device', 'device_name', 'direction', 'source',
            'decision', 'raw_text', 'normalized_plate', 'ocr_confidence',
            'matched_vehicle', 'vehicle_plate', 'matched_person', 'owner_name',
            'image_url',
        ]

    def get_image_url(self, obj: AccessLog):
        # Root-relative (e.g. /media/captures/...) so the browser fetches it from the
        # current origin. Works same-origin (nginx) and through a Vercel/Cloudflare
        # proxy without mixed-content or cross-origin issues.
        return obj.image.url if obj.image else None


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'password']

    def create(self, validated_data):
        password = validated_data.pop('password', None) or get_random_string(14)
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class CurrentUserSerializer(serializers.ModelSerializer):
    is_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_admin']
