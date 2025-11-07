from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator


class PayoutAccount(models.Model):
    class AccountType(models.TextChoices):
        BANK_ACCOUNT = 'bank_account', _('Bank Account')
        PAYPAL = 'paypal', _('PayPal')
        STRIPE = 'stripe', _('Stripe')
        CASH = 'cash', _('Cash')
    
    class VerificationStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        VERIFIED = 'verified', _('Verified')
        FAILED = 'failed', _('Failed')
    
    vendor = models.ForeignKey(
        'vendors.Vendor',
        on_delete=models.CASCADE,
        related_name='payout_accounts'
    )
    account_type = models.CharField(max_length=50, choices=AccountType.choices)
    account_name = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING
    )
    
    # Bank account details
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    routing_number = models.CharField(max_length=50, blank=True, null=True)
    iban = models.CharField(max_length=50, blank=True, null=True)
    swift_code = models.CharField(max_length=50, blank=True, null=True)
    
    # Digital wallet details
    email = models.EmailField(blank=True, null=True)
    wallet_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Processor-specific IDs
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)
    paypal_merchant_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Verification
    verified_at = models.DateTimeField(blank=True, null=True)
    verification_attempts = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payout_accounts'
        verbose_name = 'Payout Account'
        verbose_name_plural = 'Payout Accounts'
        ordering = ['-is_primary', '-created_at']
    
    def __str__(self):
        return f"{self.vendor.business_name} - {self.get_account_type_display()}"
    
    def save(self, *args, **kwargs):
        # Ensure only one primary account per vendor
        if self.is_primary:
            PayoutAccount.objects.filter(
                vendor=self.vendor, 
                is_primary=True
            ).update(is_primary=False)
        super().save(*args, **kwargs)


class Payout(models.Model):
    class PayoutStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        CANCELLED = 'cancelled', _('Cancelled')
    
    class PayoutMethod(models.TextChoices):
        BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
        PAYPAL = 'paypal', _('PayPal')
        STRIPE = 'stripe', _('Stripe')
        MANUAL = 'manual', _('Manual')
    
    vendor = models.ForeignKey(
        'vendors.Vendor',
        on_delete=models.CASCADE,
        related_name='payouts'
    )
    payout_account = models.ForeignKey(
        PayoutAccount,
        on_delete=models.CASCADE,
        related_name='payouts'
    )
    
    # Payout details
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    currency = models.CharField(max_length=3, default='USD')
    payout_method = models.CharField(max_length=50, choices=PayoutMethod.choices)
    status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.PENDING
    )
    
    # Fees and deductions
    commission_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    processing_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Timeline
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    # References
    reference_number = models.CharField(max_length=100, unique=True)
    processor_reference = models.CharField(max_length=255, blank=True, null=True)
    
    # Failure details
    failure_reason = models.TextField(blank=True, null=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payouts'
        verbose_name = 'Payout'
        verbose_name_plural = 'Payouts'
        indexes = [
            models.Index(fields=['vendor', 'status']),
            models.Index(fields=['reference_number']),
            models.Index(fields=['requested_at']),
        ]
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Payout #{self.reference_number} - {self.vendor.business_name}"
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            import uuid
            self.reference_number = f"PO-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate net amount
        self.net_amount = self.amount - self.commission_fee - self.processing_fee
        
        super().save(*args, **kwargs)


class PayoutSchedule(models.Model):
    class ScheduleType(models.TextChoices):
        MANUAL = 'manual', _('Manual')
        WEEKLY = 'weekly', _('Weekly')
        BI_WEEKLY = 'bi_weekly', _('Bi-Weekly')
        MONTHLY = 'monthly', _('Monthly')
    
    vendor = models.OneToOneField(
        'vendors.Vendor',
        on_delete=models.CASCADE,
        related_name='payout_schedule'
    )
    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices,
        default=ScheduleType.WEEKLY
    )
    is_active = models.BooleanField(default=True)
    
    # Schedule configuration
    next_payout_date = models.DateField(blank=True, null=True)
    minimum_payout_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=50.00
    )
    
    # Auto-payout settings
    auto_process = models.BooleanField(default=True)
    last_processed_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payout_schedules'
        verbose_name = 'Payout Schedule'
        verbose_name_plural = 'Payout Schedules'
    
    def __str__(self):
        return f"{self.vendor.business_name} - {self.get_schedule_type_display()}"


class VendorBalance(models.Model):
    vendor = models.OneToOneField(
        'vendors.Vendor',
        on_delete=models.CASCADE,
        related_name='balance'
    )
    
    # Balance amounts
    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    pending_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_payouts = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Hold amounts
    on_hold_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    hold_reason = models.TextField(blank=True, null=True)
    
    # Currency
    currency = models.CharField(max_length=3, default='USD')
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vendor_balances'
        verbose_name = 'Vendor Balance'
        verbose_name_plural = 'Vendor Balances'
    
    def __str__(self):
        return f"{self.vendor.business_name} Balance"
    
    @property
    def total_balance(self):
        return self.available_balance + self.pending_balance
    
    def can_request_payout(self, amount):
        from django.conf import settings
        return (
            self.available_balance >= amount and 
            amount >= settings.MIN_PAYOUT_AMOUNT
        )