from __future__ import annotations

import os
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AccessLog, GateDevice, Person, Vehicle
from .permissions import IsAdmin, IsAdminOrReadOnly
from .serializers import (
    AccessLogSerializer,
    CurrentUserSerializer,
    GateDeviceSerializer,
    PersonSerializer,
    UserSerializer,
    VehicleSerializer,
)
from .services import decision_payload, process_capture

User = get_user_model()


def _resolve_device(request) -> GateDevice | None:
    """Authenticate a gate device by its API key (header or form field)."""
    key = request.headers.get('X-Device-Key') or request.data.get('device_key')
    if not key:
        return None
    return GateDevice.objects.filter(api_key=key, is_active=True).first()


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.prefetch_related('vehicles').all()
    serializer_class = PersonSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(full_name__icontains=search) | Q(unit__icontains=search) | Q(email__icontains=search))
        return qs


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related('owner').all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        owner = self.request.query_params.get('owner')
        if owner:
            qs = qs.filter(owner_id=owner)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(display_plate__icontains=search) | Q(plate_number__icontains=search.upper()))
        return qs


class GateDeviceViewSet(viewsets.ModelViewSet):
    queryset = GateDevice.objects.all()
    serializer_class = GateDeviceSerializer
    permission_classes = [IsAdmin]

    @action(detail=True, methods=['post'])
    def regenerate_key(self, request, pk=None):
        device = self.get_object()
        device.regenerate_key()
        return Response(self.get_serializer(device).data)


class AccessLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AccessLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = AccessLog.objects.select_related('device', 'matched_vehicle', 'matched_person').all()
        decision = self.request.query_params.get('decision')
        if decision:
            qs = qs.filter(decision=decision)
        device = self.request.query_params.get('device')
        if device:
            qs = qs.filter(device_id=device)
        return qs


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)


class StatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_logs = AccessLog.objects.filter(created_at__gte=today)
        decision_counts = {
            row['decision']: row['n']
            for row in today_logs.values('decision').annotate(n=Count('id'))
        }
        return Response({
            'people': Person.objects.count(),
            'vehicles': Vehicle.objects.filter(is_active=True).count(),
            'devices_online': sum(1 for d in GateDevice.objects.all() if d.is_online),
            'devices_total': GateDevice.objects.count(),
            'today_granted': decision_counts.get(AccessLog.Decision.GRANTED, 0),
            'today_denied': decision_counts.get(AccessLog.Decision.DENIED, 0),
            'today_no_plate': decision_counts.get(AccessLog.Decision.NO_PLATE, 0),
            'today_total': today_logs.count(),
        })


@api_view(['POST'])
@permission_classes([AllowAny])
def gate_check(request):
    """Device endpoint: a captured frame is run through OCR + matching; returns the gate decision.

    Authenticated by device API key (X-Device-Key header or `device_key` form field),
    NOT by JWT, so the ESP32 never needs a user token.
    """
    device = _resolve_device(request)
    if device is None:
        return Response({'error': 'Invalid or missing device key.'}, status=status.HTTP_401_UNAUTHORIZED)

    uploaded = request.FILES.get('image')
    if uploaded is None:
        return Response({'error': 'No image uploaded under field "image".'}, status=status.HTTP_400_BAD_REQUEST)

    direction = request.data.get('direction', AccessLog.Direction.ENTRY)
    image_bytes = uploaded.read()
    _, ext = os.path.splitext(uploaded.name)
    suffix = ext if ext else '.jpg'

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(image_bytes)
            temp_path = tmp.name

        log = process_capture(
            temp_path,
            device=device,
            direction=direction,
            image_bytes=image_bytes,
            image_name=uploaded.name or 'capture.jpg',
        )
        return Response(decision_payload(log))
    except Exception as exc:  # noqa: BLE001 - surface processing errors to the device
        return Response(
            {'error': 'Capture processing failed.', 'details': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@api_view(['GET'])
@permission_classes([AllowAny])
def gate_command(request):
    """Device polls this to discover a pending manual 'open' command. Also a heartbeat."""
    device = _resolve_device(request)
    if device is None:
        return Response({'error': 'Invalid or missing device key.'}, status=status.HTTP_401_UNAUTHORIZED)

    device.last_seen = timezone.now()
    should_open = device.has_pending_open()
    fields = ['last_seen']
    if should_open:
        device.pending_open_at = None  # consume the command
        fields.append('pending_open_at')
    device.save(update_fields=fields)

    return Response({'gate_action': 'open' if should_open else 'none'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_open(request):
    """Dashboard operator/admin manually opens a gate. Queues a command + logs the action."""
    device_id = request.data.get('device')
    direction = request.data.get('direction', AccessLog.Direction.ENTRY)
    device = GateDevice.objects.filter(pk=device_id).first() if device_id else None

    if device is not None:
        device.pending_open_at = timezone.now()
        device.save(update_fields=['pending_open_at'])

    log = AccessLog.objects.create(
        device=device,
        direction=direction,
        source=AccessLog.Source.MANUAL,
        decision=AccessLog.Decision.GRANTED,
        triggered_by=request.user,
        raw_text='MANUAL OVERRIDE',
    )
    return Response(AccessLogSerializer(log, context={'request': request}).data, status=status.HTTP_201_CREATED)
