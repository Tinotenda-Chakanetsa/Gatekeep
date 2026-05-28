from django.contrib import admin

from .models import AccessLog, GateDevice, Person, Vehicle


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'unit', 'phone', 'is_active']
    search_fields = ['full_name', 'unit', 'email', 'phone']


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['display_plate', 'owner', 'make', 'model', 'color', 'is_active']
    search_fields = ['display_plate', 'plate_number']
    list_filter = ['is_active']


@admin.register(GateDevice)
class GateDeviceAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'is_active', 'last_seen']


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'decision', 'normalized_plate', 'matched_person', 'device', 'source']
    list_filter = ['decision', 'source', 'direction']
    search_fields = ['normalized_plate', 'raw_text']
