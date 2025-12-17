from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'turfs', views.TurfViewSet, basename='turf')
router.register(r'matches', views.MatchViewSet, basename='match')

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Join request endpoints
    path('join-requests/<uuid:request_id>/approve/', views.approve_join_request, name='approve-join-request'),
    path('join-requests/<uuid:request_id>/reject/', views.reject_join_request, name='reject-join-request'),
    
    # NetMate endpoints
    path('netmate/bowlers/', views.NetMateBowlerListView.as_view(), name='netmate-bowlers'),
    path('netmate/book/', views.book_netmate, name='book-netmate'),
]

