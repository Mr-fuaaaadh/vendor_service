from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


class Vendor(models.Model):
    class VendorStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        UNDER_REVIEW = 'under_review', _('Under Review')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        SUSPENDED = 'suspended', _('Suspended')
    
    class BusinessType(models.TextChoices):
        INDIVIDUAL = 'individual', _('Individual')
        SOLE_PROPRIETORSHIP = 'sole_proprietorship', _('Sole Proprietorship')
        PARTNERSHIP = 'partnership', _('Partnership')
        LLC = 'llc', _('Limited Liability Company')
        CORPORATION = 'corporation', _('Corporation')
    
    # Core vendor information
    user_id = models.BigIntegerField(unique=True, db_index=True)  # Reference to auth service user
    business_name = models.CharField(max_length=255)
    business_slug = models.SlugField(max_length=300, unique=True)
    business_type = models.CharField(max_length=50, choices=BusinessType.choices)
    business_description = models.TextField(blank=True, null=True)
    
    # Contact information
    contact_email = models.EmailField()
    contact_phone = PhoneNumberField()
    website = models.URLField(blank=True, null=True)
    
    # Business address
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='US')
    postal_code = models.CharField(max_length=20)
    
    # Business registration
    tax_id = models.CharField(max_length=50, blank=True, null=True)  # EIN/Tax ID
    business_registration_number = models.CharField(max_length=100, blank=True, null=True)
    business_registration_document = models.FileField(
        upload_to='vendor/documents/registration/',
        blank=True,
        null=True
    )
    
    # Status and metrics
    status = models.CharField(
        max_length=20,
        choices=VendorStatus.choices,
        default=VendorStatus.PENDING
    )
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_products = models.PositiveIntegerField(default=0)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_orders = models.PositiveIntegerField(default=0)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=15.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    
    # Review information
    reviewed_by = models.BigIntegerField(blank=True, null=True)  # Admin user ID from auth service
    rejection_reason = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'vendors'
        verbose_name = 'Vendor'
        verbose_name_plural = 'Vendors'
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['status']),
            models.Index(fields=['business_slug']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.business_name} ({self.get_status_display()})"
    
    @property
    def is_approved(self):
        return self.status == self.VendorStatus.APPROVED
    
    @property
    def is_active(self):
        return self.status in [self.VendorStatus.APPROVED, self.VendorStatus.UNDER_REVIEW]
    
    def save(self, *args, **kwargs):
        if not self.business_slug:
            from django.utils.text import slugify
            self.business_slug = slugify(self.business_name)
        super().save(*args, **kwargs)


class VendorDocument(models.Model):
    class DocumentType(models.TextChoices):
        ID_PROOF = 'id_proof', _('Identity Proof')
        ADDRESS_PROOF = 'address_proof', _('Address Proof')
        BUSINESS_LICENSE = 'business_license', _('Business License')
        TAX_CERTIFICATE = 'tax_certificate', _('Tax Certificate')
        BANK_PROOF = 'bank_proof', _('Bank Account Proof')
        OTHER = 'other', _('Other')
    
    vendor = models.ForeignKey(
        Vendor, 
        on_delete=models.CASCADE, 
        related_name='documents'
    )
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    document_file = models.FileField(upload_to='vendor/documents/')
    document_name = models.CharField(max_length=255)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.BigIntegerField(blank=True, null=True)  # Admin user ID
    rejection_reason = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vendor_documents'
        verbose_name = 'Vendor Document'
        verbose_name_plural = 'Vendor Documents'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.vendor.business_name} - {self.get_document_type_display()}"


class VendorSocialMedia(models.Model):
    vendor = models.ForeignKey(
        Vendor, 
        on_delete=models.CASCADE, 
        related_name='social_media'
    )
    platform = models.CharField(max_length=50)  # facebook, instagram, twitter, etc.
    url = models.URLField()
    followers_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vendor_social_media'
        verbose_name = 'Vendor Social Media'
        verbose_name_plural = 'Vendor Social Media'
        unique_together = ['vendor', 'platform']
    
    def __str__(self):
        return f"{self.vendor.business_name} - {self.platform}"


class VendorAnalytics(models.Model):
    vendor = models.OneToOneField(
        Vendor, 
        on_delete=models.CASCADE, 
        related_name='analytics'
    )
    total_views = models.PositiveIntegerField(default=0)
    total_clicks = models.PositiveIntegerField(default=0)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.PositiveIntegerField(default=0)
    
    # Monthly metrics (for reporting)
    monthly_views = models.JSONField(default=dict)
    monthly_sales = models.JSONField(default=dict)
    monthly_orders = models.JSONField(default=dict)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vendor_analytics'
        verbose_name = 'Vendor Analytics'
        verbose_name_plural = 'Vendor Analytics'
    
    def __str__(self):
        return f"{self.vendor.business_name} Analytics"


class VendorSettings(models.Model):
    vendor = models.OneToOneField(
        Vendor, 
        on_delete=models.CASCADE, 
        related_name='settings'
    )
    
    # Notification settings
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    
    # Order settings
    auto_accept_orders = models.BooleanField(default=True)
    low_stock_alert = models.BooleanField(default=True)
    low_stock_threshold = models.PositiveIntegerField(default=10)
    
    # Display settings
    show_social_media = models.BooleanField(default=True)
    show_contact_info = models.BooleanField(default=True)
    show_sales_count = models.BooleanField(default=True)
    
    # Commission settings
    custom_commission_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vendor_settings'
        verbose_name = 'Vendor Settings'
        verbose_name_plural = 'Vendor Settings'
    
    def __str__(self):
        return f"{self.vendor.business_name} Settings"
    
    @property
    def effective_commission_rate(self):
        return self.custom_commission_rate or self.vendor.commission_rate