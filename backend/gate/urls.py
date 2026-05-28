from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    AccessLogViewSet,
    CurrentUserView,
    GateDeviceViewSet,
    PersonViewSet,
    StatsView,
    UserViewSet,
    VehicleViewSet,
    gate_check,
    gate_command,
    manual_open,
)

router = DefaultRouter()
router.register('people', PersonViewSet, basename='person')
router.register('vehicles', VehicleViewSet, basename='vehicle')
router.register('devices', GateDeviceViewSet, basename='device')
router.register('access-logs', AccessLogViewSet, basename='accesslog')
router.register('users', UserViewSet, basename='user')

urlpatterns = [
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', CurrentUserView.as_view(), name='current_user'),
    path('stats/', StatsView.as_view(), name='stats'),
    path('gate/check/', gate_check, name='gate_check'),
    path('gate/command/', gate_command, name='gate_command'),
    path('gate/open/', manual_open, name='manual_open'),
    path('', include(router.urls)),
]
