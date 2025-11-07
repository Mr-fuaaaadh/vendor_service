from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet

from shared.exceptions import CustomException
from .models import PayoutAccount, Payout, PayoutSchedule, VendorBalance
from .serializers import (
    PayoutAccountCreateSerializer, PayoutAccountSerializer,
    PayoutCreateSerializer, PayoutSerializer, PayoutScheduleSerializer,
    VendorBalanceSerializer, PayoutSummarySerializer
)
from .processors.stripe_processor import StripeProcessor
from .processors.paypal_processor import PayPalProcessor
from apps.vendors.permissions import IsVendorOwner


class PayoutAccountViewSet(ModelViewSet):
    permission_classes = [IsVendorOwner]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PayoutAccountCreateSerializer
        return PayoutAccountSerializer
    
    def get_queryset(self):
        return PayoutAccount.objects.filter(vendor__user_id=self.request.user.id)
    
    def perform_create(self, serializer):
        vendor = self.get_vendor()
        serializer.save(vendor=vendor)
    
    def get_vendor(self):
        from apps.vendors.models import Vendor
        return Vendor.objects.get(user_id=self.request.user.id)
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        payout_account = self.get_object()
        
        # Implement verification logic based on account type
        processor = self.get_processor(payout_account.account_type)
        verification_result = processor.verify_account(payout_account)
        
        if verification_result['success']:
            payout_account.verification_status = PayoutAccount.VerificationStatus.VERIFIED
            payout_account.verified_at = timezone.now()
            payout_account.save()
            
            return Response({
                'message': 'Account verified successfully.',
                'account': PayoutAccountSerializer(payout_account).data
            })
        else:
            payout_account.verification_status = PayoutAccount.VerificationStatus.FAILED
            payout_account.save()
            
            raise CustomException(
                f'Account verification failed: {verification_result["error"]}',
                status.HTTP_400_BAD_REQUEST
            )
    
    def get_processor(self, account_type):
        if account_type == PayoutAccount.AccountType.STRIPE:
            return StripeProcessor()
        elif account_type == PayoutAccount.AccountType.PAYPAL:
            return PayPalProcessor()
        else:
            raise CustomException('Unsupported account type.', status.HTTP_400_BAD_REQUEST)


class PayoutViewSet(ModelViewSet):
    serializer_class = PayoutSerializer
    permission_classes = [IsVendorOwner]
    
    def get_queryset(self):
        return Payout.objects.filter(vendor__user_id=self.request.user.id)
    
    def create(self, request, *args, **kwargs):
        serializer = PayoutCreateSerializer(
            data=request.data,
            context={'vendor': self.get_vendor()}
        )
        serializer.is_valid(raise_exception=True)
        
        payout_data = serializer.validated_data
        payout_account = payout_data['payout_account']
        amount = payout_data['amount']
        
        # Create payout
        payout = Payout.objects.create(
            vendor=self.get_vendor(),
            payout_account=payout_account,
            amount=amount,
            payout_method=self.get_payout_method(payout_account.account_type),
            net_amount=amount,  # Will be calculated in save method
            currency='USD'
        )
        
        # Process payout
        processor = self.get_processor(payout_account.account_type)
        processing_result = processor.process_payout(payout)
        
        if processing_result['success']:
            payout.status = Payout.PayoutStatus.PROCESSING
            payout.processor_reference = processing_result['reference']
            payout.save()
            
            # Update vendor balance
            self.update_vendor_balance(payout.vendor, amount)
            
            return Response(
                PayoutSerializer(payout).data,
                status=status.HTTP_201_CREATED
            )
        else:
            payout.status = Payout.PayoutStatus.FAILED
            payout.failure_reason = processing_result['error']
            payout.save()
            
            raise CustomException(
                f'Payout processing failed: {processing_result["error"]}',
                status.HTTP_400_BAD_REQUEST
            )
    
    def get_vendor(self):
        from apps.vendors.models import Vendor
        return Vendor.objects.get(user_id=self.request.user.id)
    
    def get_payout_method(self, account_type):
        method_map = {
            PayoutAccount.AccountType.BANK_ACCOUNT: Payout.PayoutMethod.BANK_TRANSFER,
            PayoutAccount.AccountType.PAYPAL: Payout.PayoutMethod.PAYPAL,
            PayoutAccount.AccountType.STRIPE: Payout.PayoutMethod.STRIPE,
        }
        return method_map.get(account_type, Payout.PayoutMethod.MANUAL)
    
    def get_processor(self, account_type):
        if account_type in [PayoutAccount.AccountType.BANK_ACCOUNT, PayoutAccount.AccountType.STRIPE]:
            return StripeProcessor()
        elif account_type == PayoutAccount.AccountType.PAYPAL:
            return PayPalProcessor()
        else:
            raise CustomException('Unsupported payout method.', status.HTTP_400_BAD_REQUEST)
    
    def update_vendor_balance(self, vendor, amount):
        balance = vendor.balance
        balance.available_balance -= amount
        balance.total_payouts += amount
        balance.save()


class VendorBalanceView(APIView):
    permission_classes = [IsVendorOwner]
    
    def get(self, request):
        try:
            from apps.vendors.models import Vendor
            vendor = Vendor.objects.get(user_id=request.user.id)
            balance = vendor.balance
            serializer = VendorBalanceSerializer(balance)
            return Response(serializer.data)
        except Vendor.DoesNotExist:
            raise CustomException('Vendor not found.', status.HTTP_404_NOT_FOUND)


class PayoutScheduleView(APIView):
    permission_classes = [IsVendorOwner]
    
    def get(self, request):
        try:
            from apps.vendors.models import Vendor
            vendor = Vendor.objects.get(user_id=request.user.id)
            schedule, created = PayoutSchedule.objects.get_or_create(vendor=vendor)
            serializer = PayoutScheduleSerializer(schedule)
            return Response(serializer.data)
        except Vendor.DoesNotExist:
            raise CustomException('Vendor not found.', status.HTTP_404_NOT_FOUND)
    
    def put(self, request):
        try:
            from apps.vendors.models import Vendor
            vendor = Vendor.objects.get(user_id=request.user.id)
            schedule, created = PayoutSchedule.objects.get_or_create(vendor=vendor)
            serializer = PayoutScheduleSerializer(schedule, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        except Vendor.DoesNotExist:
            raise CustomException('Vendor not found.', status.HTTP_404_NOT_FOUND)


class PayoutSummaryView(APIView):
    permission_classes = [IsVendorOwner]
    
    def get(self, request):
        try:
            from apps.vendors.models import Vendor
            vendor = Vendor.objects.get(user_id=request.user.id)
            
            # Calculate payout summary
            total_payouts = vendor.payouts.filter(
                status=Payout.PayoutStatus.COMPLETED
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            pending_payouts = vendor.payouts.filter(
                status__in=[Payout.PayoutStatus.PENDING, Payout.PayoutStatus.PROCESSING]
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            last_payout = vendor.payouts.filter(
                status=Payout.PayoutStatus.COMPLETED
            ).order_by('-completed_at').first()
            
            schedule = getattr(vendor, 'payout_schedule', None)
            
            summary_data = {
                'total_payouts': total_payouts,
                'pending_payouts': pending_payouts,
                'last_payout_amount': last_payout.amount if last_payout else 0,
                'last_payout_date': last_payout.completed_at if last_payout else None,
                'next_scheduled_payout': schedule.next_payout_date if schedule else None
            }
            
            serializer = PayoutSummarySerializer(summary_data)
            return Response(serializer.data)
        except Vendor.DoesNotExist:
            raise CustomException('Vendor not found.', status.HTTP_404_NOT_FOUND)