from rest_framework import serializers
from django.core.validators import MinValueValidator

from .models import PayoutAccount, Payout, PayoutSchedule, VendorBalance


class PayoutAccountCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutAccount
        fields = [
            'account_type', 'account_name', 'bank_name', 'account_number',
            'routing_number', 'iban', 'swift_code', 'email', 'is_primary'
        ]
    
    def validate(self, attrs):
        account_type = attrs.get('account_type')
        
        if account_type == PayoutAccount.AccountType.BANK_ACCOUNT:
            if not attrs.get('account_number') or not attrs.get('routing_number'):
                raise serializers.ValidationError({
                    'account_number': 'Account number and routing number are required for bank accounts.',
                    'routing_number': 'Account number and routing number are required for bank accounts.'
                })
        
        elif account_type == PayoutAccount.AccountType.PAYPAL:
            if not attrs.get('email'):
                raise serializers.ValidationError({
                    'email': 'Email is required for PayPal accounts.'
                })
        
        return attrs
    
    def create(self, validated_data):
        validated_data['vendor'] = self.context['vendor']
        return super().create(validated_data)


class PayoutAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutAccount
        fields = [
            'id', 'account_type', 'account_name', 'is_primary',
            'verification_status', 'bank_name', 'email',
            'verified_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'verification_status', 'verified_at',
            'created_at', 'updated_at'
        ]


class PayoutCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    payout_account_id = serializers.IntegerField()
    
    def validate(self, attrs):
        vendor = self.context['vendor']
        amount = attrs['amount']
        payout_account_id = attrs['payout_account_id']
        
        # Check if payout account belongs to vendor
        try:
            payout_account = vendor.payout_accounts.get(id=payout_account_id)
        except PayoutAccount.DoesNotExist:
            raise serializers.ValidationError({
                'payout_account_id': 'Payout account not found.'
            })
        
        # Check if payout account is verified
        if payout_account.verification_status != PayoutAccount.VerificationStatus.VERIFIED:
            raise serializers.ValidationError({
                'payout_account_id': 'Payout account must be verified.'
            })
        
        # Check vendor balance
        balance = vendor.balance
        if not balance.can_request_payout(amount):
            raise serializers.ValidationError({
                'amount': f'Insufficient balance or amount below minimum payout of ${balance.minimum_payout_amount}.'
            })
        
        attrs['payout_account'] = payout_account
        return attrs


class PayoutSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.business_name', read_only=True)
    account_type = serializers.CharField(source='payout_account.account_type', read_only=True)
    
    class Meta:
        model = Payout
        fields = [
            'id', 'reference_number', 'vendor_name', 'amount', 'currency',
            'net_amount', 'commission_fee', 'processing_fee', 'payout_method',
            'status', 'account_type', 'requested_at', 'processed_at',
            'completed_at', 'failure_reason', 'processor_reference'
        ]
        read_only_fields = fields


class PayoutScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutSchedule
        fields = [
            'id', 'schedule_type', 'is_active', 'next_payout_date',
            'minimum_payout_amount', 'auto_process', 'last_processed_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_processed_at', 'created_at', 'updated_at']


class VendorBalanceSerializer(serializers.ModelSerializer):
    total_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = VendorBalance
        fields = [
            'available_balance', 'pending_balance', 'on_hold_balance',
            'total_earnings', 'total_payouts', 'total_balance',
            'hold_reason', 'currency', 'updated_at'
        ]
        read_only_fields = fields


class PayoutSummarySerializer(serializers.Serializer):
    total_payouts = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_payouts = serializers.DecimalField(max_digits=12, decimal_places=2)
    last_payout_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    last_payout_date = serializers.DateTimeField()
    next_scheduled_payout = serializers.DateField(allow_null=True)