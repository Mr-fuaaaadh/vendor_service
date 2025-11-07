from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.VendorViewSet, basename='vendor')
router.register(r'documents', views.VendorDocumentViewSet, basename='vendor-document')
router.register(r'social-media', views.VendorSocialMediaViewSet, basename='vendor-social-media')

urlpatterns = [
    path('', include(router.urls)),
    path('settings/', views.VendorSettingsView.as_view(), name='vendor-settings'),
    path('admin/vendors/', views.AdminVendorListView.as_view(), name='admin-vendor-list'),
    path('public/vendors/', views.PublicVendorListView.as_view(), name='public-vendor-list'),
]