from rest_framework import serializers
from django.core.validators import FileExtensionValidator
from phonenumber_field.serializerfields import PhoneNumberField

from .models import Vendor, VendorDocument, VendorSocialMedia, VendorSettings, VendorAnalytics


class VendorDocumentSerializer(serializers.ModelSerializer):
    document_file = serializers.FileField(
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'])
        ]
    )
    
    class Meta:
        model = VendorDocument
        fields = [
            'id', 'document_type', 'document_file', 'document_name',
            'is_verified', 'verified_at', 'rejection_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'is_verified', 'verified_at', 'rejection_reason',
            'created_at', 'updated_at'
        ]


class VendorSocialMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorSocialMedia
        fields = ['id', 'platform', 'url', 'followers_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class VendorSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorSettings
        fields = [
            'id', 'email_notifications', 'sms_notifications', 'push_notifications',
            'auto_accept_orders', 'low_stock_alert', 'low_stock_threshold',
            'show_social_media', 'show_contact_info', 'show_sales_count',
            'custom_commission_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class VendorAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorAnalytics
        fields = [
            'id', 'total_views', 'total_clicks', 'conversion_rate',
            'average_rating', 'total_reviews', 'monthly_views',
            'monthly_sales', 'monthly_orders', 'updated_at'
        ]
        read_only_fields = ['id', 'updated_at']


class VendorCreateSerializer(serializers.ModelSerializer):
    contact_phone = PhoneNumberField()
    
    class Meta:
        model = Vendor
        fields = [
            'business_name', 'business_type', 'business_description',
            'contact_email', 'contact_phone', 'website',
            'address_line1', 'address_line2', 'city', 'state', 
            'country', 'postal_code', 'tax_id', 'business_registration_number'
        ]
    
    def validate_business_name(self, value):
        # Check if business name is already taken
        if Vendor.objects.filter(business_name__iexact=value).exists():
            raise serializers.ValidationError("A vendor with this business name already exists.")
        return value
    
    def create(self, validated_data):
        # Get user_id from context (set by view)
        user_id = self.context['request'].user.id
        validated_data['user_id'] = user_id
        return super().create(validated_data)


class VendorListSerializer(serializers.ModelSerializer):
    total_products = serializers.IntegerField(read_only=True)
    total_sales = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    rating = serializers.DecimalField(max_digits=3, decimal_places=2, read_only=True)
    
    class Meta:
        model = Vendor
        fields = [
            'id', 'business_name', 'business_slug', 'business_type',
            'status', 'rating', 'total_products', 'total_sales',
            'contact_email', 'contact_phone', 'city', 'country',
            'created_at', 'approved_at'
        ]
        read_only_fields = fields


class VendorDetailSerializer(serializers.ModelSerializer):
    documents = VendorDocumentSerializer(many=True, read_only=True)
    social_media = VendorSocialMediaSerializer(many=True, read_only=True)
    settings = VendorSettingsSerializer(read_only=True)
    analytics = VendorAnalyticsSerializer(read_only=True)
    total_products = serializers.IntegerField(read_only=True)
    total_sales = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_orders = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Vendor
        fields = [
            'id', 'user_id', 'business_name', 'business_slug', 'business_type',
            'business_description', 'contact_email', 'contact_phone', 'website',
            'address_line1', 'address_line2', 'city', 'state', 'country', 'postal_code',
            'tax_id', 'business_registration_number', 'status', 'rating',
            'total_products', 'total_sales', 'total_orders', 'commission_rate',
            'documents', 'social_media', 'settings', 'analytics',
            'created_at', 'updated_at', 'approved_at', 'reviewed_at'
        ]
        read_only_fields = [
            'id', 'user_id', 'business_slug', 'status', 'rating',
            'total_products', 'total_sales', 'total_orders', 'commission_rate',
            'created_at', 'updated_at', 'approved_at', 'reviewed_at'
        ]


class VendorUpdateSerializer(serializers.ModelSerializer):
    contact_phone = PhoneNumberField()
    
    class Meta:
        model = Vendor
        fields = [
            'business_name', 'business_type', 'business_description',
            'contact_email', 'contact_phone', 'website',
            'address_line1', 'address_line2', 'city', 'state',
            'country', 'postal_code', 'tax_id', 'business_registration_number'
        ]
    
    def validate_business_name(self, value):
        # Check if business name is already taken (excluding current instance)
        instance = self.instance
        if Vendor.objects.filter(business_name__iexact=value).exclude(id=instance.id).exists():
            raise serializers.ValidationError("A vendor with this business name already exists.")
        return value


class VendorStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Vendor.VendorStatus.choices)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        status = attrs.get('status')
        rejection_reason = attrs.get('rejection_reason')
        
        if status == Vendor.VendorStatus.REJECTED and not rejection_reason:
            raise serializers.ValidationError({
                'rejection_reason': 'Rejection reason is required when rejecting a vendor.'
            })
        
        return attrs


class VendorDashboardSerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    total_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_orders = serializers.IntegerField()
    available_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    monthly_sales = serializers.DictField()
    recent_activities = serializers.ListField()