from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


def api_root(request):
    """Root endpoint to verify API is running"""
    return JsonResponse({
        'message': 'FILL11 API is running',
        'status': 'success',
        'version': '1.0',
        'endpoints': {
            'admin': '/admin/',
            'auth': '/api/auth/',
            'users': '/api/users/',
            'matches': '/api/matches/',
        }
    })


urlpatterns = [
    # Root endpoint
    path('', api_root, name='api-root'),

    # Admin
    path('admin/', admin.site.urls),

    # API endpoints
    path(
        'api/auth/',
        include(('apps.users.urls', 'users'), namespace='auth')
    ),
    path(
        'api/users/',
        include(('apps.users.urls', 'users'), namespace='users')
    ),
    path('api/matches/', include('apps.matches.urls')),
]


# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
