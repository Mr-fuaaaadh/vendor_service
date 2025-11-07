from django.db.models import Q, Count, Sum
from django.utils import timezone
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet

from shared.exceptions import CustomException
from shared.clients.auth_client import AuthClient
from .models import Vendor, VendorDocument, VendorSocialMedia, VendorSettings
from .serializers import (
    VendorCreateSerializer, VendorListSerializer, VendorDetailSerializer,
    VendorUpdateSerializer, VendorStatusUpdateSerializer, VendorDocumentSerializer,
    VendorSocialMediaSerializer, VendorSettingsSerializer, VendorDashboardSerializer
)
from .permissions import IsVendorOwner, IsAdminUser, IsVendorOrAdmin
from .tasks import send_vendor_approval_email, send_vendor_rejection_email


class VendorViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_admin:
            return Vendor.objects.all().select_related('settings', 'analytics')
        elif user.is_vendor:
            return Vendor.objects.filter(user_id=user.id).select_related('settings', 'analytics')
        else:
            return Vendor.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return VendorCreateSerializer
        elif self.action == 'list':
            return VendorListSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return VendorDetailSerializer
        return VendorListSerializer
    
    def get_permissions(self):
        if self.action in ['create']:
            return [permissions.IsAuthenticated()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsVendorOwner()]
        elif self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        elif self.action in ['approve', 'reject', 'suspend']:
            return [IsAdminUser()]
        return super().get_permissions()
    
    def create(self, request, *args, **kwargs):
        # Check if user already has a vendor account
        if Vendor.objects.filter(user_id=request.user.id).exists():
            raise CustomException('You already have a vendor account.', status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save()
        
        # Create related objects
        VendorSettings.objects.create(vendor=vendor)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            VendorDetailSerializer(vendor).data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        vendor = self.get_object()
        
        if vendor.status == Vendor.VendorStatus.APPROVED:
            raise CustomException('Vendor is already approved.', status.HTTP_400_BAD_REQUEST)
        
        vendor.status = Vendor.VendorStatus.APPROVED
        vendor.approved_at = timezone.now()
        vendor.reviewed_by = request.user.id
        vendor.save()
        
        # Send approval email
        send_vendor_approval_email.delay(vendor.id)
        
        return Response({
            'message': 'Vendor approved successfully.',
            'vendor': VendorDetailSerializer(vendor).data
        })
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        vendor = self.get_object()
        serializer = VendorStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        vendor.status = Vendor.VendorStatus.REJECTED
        vendor.rejection_reason = serializer.validated_data.get('rejection_reason')
        vendor.reviewed_by = request.user.id
        vendor.reviewed_at = timezone.now()
        vendor.save()
        
        # Send rejection email
        send_vendor_rejection_email.delay(vendor.id)
        
        return Response({
            'message': 'Vendor rejected successfully.',
            'vendor': VendorDetailSerializer(vendor).data
        })
    
    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        vendor = self.get_object()
        
        # Get vendor statistics (you would integrate with order service here)
        dashboard_data = {
            'total_products': vendor.total_products,
            'total_orders': vendor.total_orders,
            'total_sales': vendor.total_sales,
            'pending_orders': 0,  # Would come from order service
            'available_balance': vendor.balance.available_balance if hasattr(vendor, 'balance') else 0,
            'rating': vendor.rating,
            'monthly_sales': vendor.analytics.monthly_sales if hasattr(vendor, 'analytics') else {},
            'recent_activities': []  # Would come from various services
        }
        
        serializer = VendorDashboardSerializer(dashboard_data)
        return Response(serializer.data)


class VendorDocumentViewSet(ModelViewSet):
    serializer_class = VendorDocumentSerializer
    permission_classes = [IsVendorOwner]
    
    def get_queryset(self):
        return VendorDocument.objects.filter(vendor__user_id=self.request.user.id)
    
    def perform_create(self, serializer):
        vendor = Vendor.objects.get(user_id=self.request.user.id)
        serializer.save(vendor=vendor)


class VendorSocialMediaViewSet(ModelViewSet):
    serializer_class = VendorSocialMediaSerializer
    permission_classes = [IsVendorOwner]
    
    def get_queryset(self):
        return VendorSocialMedia.objects.filter(vendor__user_id=self.request.user.id)
    
    def perform_create(self, serializer):
        vendor = Vendor.objects.get(user_id=self.request.user.id)
        serializer.save(vendor=vendor)


class VendorSettingsView(APIView):
    permission_classes = [IsVendorOwner]
    
    def get(self, request):
        try:
            vendor = Vendor.objects.get(user_id=request.user.id)
            settings = vendor.settings
            serializer = VendorSettingsSerializer(settings)
            return Response(serializer.data)
        except Vendor.DoesNotExist:
            raise CustomException('Vendor not found.', status.HTTP_404_NOT_FOUND)
    
    def put(self, request):
        try:
            vendor = Vendor.objects.get(user_id=request.user.id)
            settings = vendor.settings
            serializer = VendorSettingsSerializer(settings, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        except Vendor.DoesNotExist:
            raise CustomException('Vendor not found.', status.HTTP_404_NOT_FOUND)


class AdminVendorListView(generics.ListAPIView):
    serializer_class = VendorListSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['status', 'business_type', 'country']
    search_fields = ['business_name', 'contact_email', 'city']
    ordering_fields = ['created_at', 'total_sales', 'rating']
    
    def get_queryset(self):
        status_filter = self.request.query_params.get('status')
        search_query = self.request.query_params.get('search')
        
        queryset = Vendor.objects.all().select_related('settings', 'analytics')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if search_query:
            queryset = queryset.filter(
                Q(business_name__icontains=search_query) |
                Q(contact_email__icontains=search_query) |
                Q(city__icontains=search_query)
            )
        
        return queryset


class PublicVendorListView(generics.ListAPIView):
    serializer_class = VendorListSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    
    def get_queryset(self):
        return Vendor.objects.filter(
            status=Vendor.VendorStatus.APPROVED
        ).select_related('analytics').only(
            'id', 'business_name', 'business_slug', 'business_type',
            'business_description', 'rating', 'total_products', 'total_sales',
            'city', 'country', 'created_at'
        )