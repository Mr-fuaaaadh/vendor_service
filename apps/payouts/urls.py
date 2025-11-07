from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'accounts', views.PayoutAccountViewSet, basename='payout-account')
router.register(r'payouts', views.PayoutViewSet, basename='payout')

urlpatterns = [
    path('', include(router.urls)),
    path('balance/', views.VendorBalanceView.as_view(), name='vendor-balance'),
    path('schedule/', views.PayoutScheduleView.as_view(), name='payout-schedule'),
    path('summary/', views.PayoutSummaryView.as_view(), name='payout-summary'),
]