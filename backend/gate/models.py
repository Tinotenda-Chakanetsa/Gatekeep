from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from .plates import canonical_plate, normalize_plate


class Person(models.Model):
    """A vehicle owner. One person can own many vehicles."""

    full_name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    unit = models.CharField(max_length=64, blank=True, help_text='Flat / office / unit number')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']
        verbose_name_plural = 'people'

    def __str__(self) -> str:
        return self.full_name


class Vehicle(models.Model):
    """A registered vehicle whose plate grants gate access while active."""

    owner = models.ForeignKey(Person, related_name='vehicles', on_delete=models.CASCADE)
    plate_number = models.CharField(max_length=16, unique=True, db_index=True, editable=False)
    display_plate = models.CharField(max_length=24)
    canonical = models.CharField(max_length=16, db_index=True, editable=False)
    make = models.CharField(max_length=48, blank=True)
    model = models.CharField(max_length=48, blank=True)
    color = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_plate']

    def __str__(self) -> str:
        return self.display_plate

    def save(self, *args, **kwargs):
        source = self.display_plate or self.plate_number
        self.plate_number = normalize_plate(source)
        self.display_plate = self.display_plate or self.plate_number
        self.canonical = canonical_plate(source)
        super().save(*args, **kwargs)


class GateDevice(models.Model):
    """An ESP32-CAM (or simulator) that captures plates and actuates a gate."""

    name = models.CharField(max_length=80)
    location = models.CharField(max_length=120, blank=True)
    api_key = models.CharField(max_length=64, unique=True, db_index=True, editable=False)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    # A pending manual "open" command and when it was issued (consumed by the device poll).
    pending_open_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_hex(24)
        super().save(*args, **kwargs)

    def regenerate_key(self) -> str:
        self.api_key = secrets.token_hex(24)
        self.save(update_fields=['api_key'])
        return self.api_key

    @property
    def is_online(self) -> bool:
        if not self.last_seen:
            return False
        return (timezone.now() - self.last_seen).total_seconds() < 120

    def has_pending_open(self) -> bool:
        if not self.pending_open_at:
            return False
        age = (timezone.now() - self.pending_open_at).total_seconds()
        return age <= settings.GATE_COMMAND_TTL_SECONDS


class AccessLog(models.Model):
    """One gate decision event: a capture, what was read, and whether access was granted."""

    class Decision(models.TextChoices):
        GRANTED = 'granted', 'Granted'
        DENIED = 'denied', 'Denied'
        NO_PLATE = 'no_plate', 'No plate detected'

    class Direction(models.TextChoices):
        ENTRY = 'entry', 'Entry'
        EXIT = 'exit', 'Exit'

    class Source(models.TextChoices):
        DEVICE = 'device', 'Device'
        MANUAL = 'manual', 'Manual override'

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    device = models.ForeignKey(GateDevice, related_name='logs', null=True, blank=True, on_delete=models.SET_NULL)
    direction = models.CharField(max_length=8, choices=Direction.choices, default=Direction.ENTRY)
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.DEVICE)
    decision = models.CharField(max_length=10, choices=Decision.choices)
    raw_text = models.CharField(max_length=128, blank=True)
    normalized_plate = models.CharField(max_length=16, blank=True, db_index=True)
    ocr_confidence = models.FloatField(null=True, blank=True)
    matched_vehicle = models.ForeignKey(Vehicle, related_name='logs', null=True, blank=True, on_delete=models.SET_NULL)
    matched_person = models.ForeignKey(Person, related_name='logs', null=True, blank=True, on_delete=models.SET_NULL)
    image = models.ImageField(upload_to='captures/%Y/%m/%d/', null=True, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='manual_actions'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.decision} {self.normalized_plate}'.strip()
