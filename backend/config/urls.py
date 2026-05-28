from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('gate.urls')),
    path('api/', include('ocr_api.urls')),
    # Serve captured images. Adequate for a prototype; front a CDN/nginx for real load.
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
