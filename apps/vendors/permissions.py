from rest_framework import permissions
from rest_framework.permissions import BasePermission
from django.conf import settings

from shared.clients.auth_client import AuthClient


class IsAuthenticated(permissions.IsAuthenticated):
    """
    Allows access only to authenticated users.
    Enhanced to work with JWT tokens from auth service.
    """
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Verify user is active and has valid token
        return request.user and request.user.is_authenticated and request.user.is_active


class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_admin
        )


class IsVendorUser(BasePermission):
    """
    Allows access only to vendor users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_vendor
        )


class IsCustomerUser(BasePermission):
    """
    Allows access only to customer users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_customer
        )


class IsVendorOrAdmin(BasePermission):
    """
    Allows access to vendor and admin users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_vendor or request.user.is_admin)
        )


class IsVendorOwner(BasePermission):
    """
    Allows access only to the vendor who owns the resource.
    """
    def has_permission(self, request, view):
        # First check if user is a vendor
        if not (request.user and request.user.is_authenticated and request.user.is_vendor):
            return False
        
        # For create actions, check if user doesn't already have a vendor account
        if view.action == 'create':
            from .models import Vendor
            return not Vendor.objects.filter(user_id=request.user.id).exists()
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Handle different object types
        if hasattr(obj, 'vendor'):
            # Object has a vendor relationship (like VendorDocument, VendorSocialMedia)
            return obj.vendor.user_id == request.user.id
        elif hasattr(obj, 'user_id'):
            # Object is a Vendor instance
            return obj.user_id == request.user.id
        elif hasattr(obj, 'id'):
            # Direct vendor object comparison
            return obj.id == request.user.id
        
        return False


class IsVendorProfileOwner(BasePermission):
    """
    Allows access only to the vendor who owns the profile.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_vendor
        )
    
    def has_object_permission(self, request, view, obj):
        # obj should be a Vendor instance or related object
        if hasattr(obj, 'user_id'):
            return obj.user_id == request.user.id
        return False


class IsAdminOrReadOnly(BasePermission):
    """
    Allows read-only access to all users, but write access only to admin users.
    """
    def has_permission(self, request, view):
        # Allow GET, HEAD, OPTIONS requests
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for admin users
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsVendorOrReadOnly(BasePermission):
    """
    Allows read-only access to all users, but write access only to vendor users.
    """
    def has_permission(self, request, view):
        # Allow GET, HEAD, OPTIONS requests
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for vendor users
        return bool(request.user and request.user.is_authenticated and request.user.is_vendor)


class IsVendorOwnerOrAdmin(BasePermission):
    """
    Allows access to vendor owners or admin users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_vendor or request.user.is_admin)
        )
    
    def has_object_permission(self, request, view, obj):
        # Admin users have full access
        if request.user.is_admin:
            return True
        
        # Vendor users can only access their own objects
        if hasattr(obj, 'vendor'):
            return obj.vendor.user_id == request.user.id
        elif hasattr(obj, 'user_id'):
            return obj.user_id == request.user.id
        
        return False


class IsApprovedVendor(BasePermission):
    """
    Allows access only to vendors with approved status.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_vendor):
            return False
        
        # Check if vendor is approved
        from .models import Vendor
        try:
            vendor = Vendor.objects.get(user_id=request.user.id)
            return vendor.is_approved
        except Vendor.DoesNotExist:
            return False


class IsActiveVendor(BasePermission):
    """
    Allows access only to vendors with active status (approved or under review).
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_vendor):
            return False
        
        # Check if vendor is active
        from .models import Vendor
        try:
            vendor = Vendor.objects.get(user_id=request.user.id)
            return vendor.is_active
        except Vendor.DoesNotExist:
            return False


class CanManageVendor(BasePermission):
    """
    Allows access to users who can manage vendors (admin or vendor owners).
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_admin or request.user.is_vendor)
        )
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        
        # Vendor users can only manage their own vendor account
        if hasattr(obj, 'user_id'):
            return obj.user_id == request.user.id
        elif hasattr(obj, 'vendor'):
            return obj.vendor.user_id == request.user.id
        
        return False


class CanViewVendorDetails(BasePermission):
    """
    Allows viewing vendor details based on user role and vendor status.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
    
    def has_object_permission(self, request, view, obj):
        from .models import Vendor
        
        # Admin users can view all vendors
        if request.user.is_admin:
            return True
        
        # Vendor users can view their own vendor profile
        if request.user.is_vendor and hasattr(obj, 'user_id'):
            return obj.user_id == request.user.id
        
        # Customer users can only view approved vendors
        if request.user.is_customer:
            return obj.is_approved
        
        return False


class CanCreateVendor(BasePermission):
    """
    Allows users to create vendor accounts if they don't already have one.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Check if user already has a vendor account
        from .models import Vendor
        has_vendor_account = Vendor.objects.filter(user_id=request.user.id).exists()
        
        return not has_vendor_account


class CanManagePayouts(BasePermission):
    """
    Allows access to payout management based on user role.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Admin users can manage all payouts
        if request.user.is_admin:
            return True
        
        # Vendor users can manage their own payouts
        if request.user.is_vendor:
            from .models import Vendor
            try:
                vendor = Vendor.objects.get(user_id=request.user.id)
                return vendor.is_approved
            except Vendor.DoesNotExist:
                return False
        
        return False
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        
        # Vendor users can only manage their own payouts
        if hasattr(obj, 'vendor'):
            return obj.vendor.user_id == request.user.id
        
        return False


class CanUploadDocuments(BasePermission):
    """
    Allows document upload only for vendors during onboarding or admin users.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Admin users can upload documents for any vendor
        if request.user.is_admin:
            return True
        
        # Vendor users can upload their own documents
        if request.user.is_vendor:
            from .models import Vendor
            try:
                vendor = Vendor.objects.get(user_id=request.user.id)
                # Allow document upload during onboarding or for approved vendors
                return vendor.status in [
                    Vendor.VendorStatus.PENDING,
                    Vendor.VendorStatus.UNDER_REVIEW,
                    Vendor.VendorStatus.APPROVED
                ]
            except Vendor.DoesNotExist:
                return False
        
        return False


class CanVerifyDocuments(BasePermission):
    """
    Allows document verification only for admin users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_admin
        )


class CanApproveVendors(BasePermission):
    """
    Allows vendor approval/rejection only for admin users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_admin
        )


class PublicReadOnly(BasePermission):
    """
    Allows read-only access to public endpoints without authentication.
    """
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS


class HasVendorServicePermission(BasePermission):
    """
    Allows access only to internal services with valid service tokens.
    """
    def has_permission(self, request, view):
        # Check for service token in headers
        service_token = request.headers.get('X-Service-Token')
        if not service_token:
            return False
        
        # Validate service token (you might want to use a more secure method)
        valid_tokens = getattr(settings, 'SERVICE_TOKENS', {})
        expected_token = valid_tokens.get('vendor_service')
        
        return service_token == expected_token


class IsVendorWithCompleteProfile(BasePermission):
    """
    Allows access only to vendors with complete profiles.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_vendor):
            return False
        
        from .models import Vendor
        try:
            vendor = Vendor.objects.get(user_id=request.user.id)
            
            # Check if vendor has complete profile
            return all([
                vendor.business_name,
                vendor.contact_email,
                vendor.contact_phone,
                vendor.address_line1,
                vendor.city,
                vendor.state,
                vendor.country,
                vendor.postal_code
            ])
        except Vendor.DoesNotExist:
            return False


class CanAccessVendorDashboard(BasePermission):
    """
    Allows access to vendor dashboard for approved vendors and admin users.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        if request.user.is_admin:
            return True
        
        if request.user.is_vendor:
            from .models import Vendor
            try:
                vendor = Vendor.objects.get(user_id=request.user.id)
                return vendor.is_approved
            except Vendor.DoesNotExist:
                return False
        
        return False


class PermissionFactory:
    """
    Factory class to create permission combinations based on business rules.
    """
    
    @staticmethod
    def get_vendor_create_permissions():
        """Permissions for vendor creation"""
        return [IsAuthenticated, CanCreateVendor]
    
    @staticmethod
    def get_vendor_read_permissions():
        """Permissions for reading vendor data"""
        return [IsAuthenticated, CanViewVendorDetails]
    
    @staticmethod
    def get_vendor_write_permissions():
        """Permissions for modifying vendor data"""
        return [IsAuthenticated, IsVendorOwnerOrAdmin]
    
    @staticmethod
    def get_vendor_admin_permissions():
        """Permissions for vendor administration"""
        return [IsAuthenticated, IsAdminUser]
    
    @staticmethod
    def get_payout_management_permissions():
        """Permissions for payout management"""
        return [IsAuthenticated, CanManagePayouts]
    
    @staticmethod
    def get_document_upload_permissions():
        """Permissions for document upload"""
        return [IsAuthenticated, CanUploadDocuments]
    
    @staticmethod
    def get_public_vendor_list_permissions():
        """Permissions for public vendor listing"""
        return [PublicReadOnly]
    
    @staticmethod
    def get_vendor_dashboard_permissions():
        """Permissions for vendor dashboard"""
        return [IsAuthenticated, CanAccessVendorDashboard]


class DynamicPermission(BasePermission):
    """
    Dynamic permission that can be configured based on view actions.
    """
    def __init__(self, read_perm=None, write_perm=None, admin_perm=None):
        self.read_perm = read_perm or IsAuthenticated
        self.write_perm = write_perm or IsVendorOwnerOrAdmin
        self.admin_perm = admin_perm or IsAdminUser
    
    def has_permission(self, request, view):
        action = getattr(view, 'action', None)
        
        # Map actions to permission classes
        if action in ['list', 'retrieve']:
            return self.read_perm().has_permission(request, view)
        elif action in ['create', 'update', 'partial_update', 'destroy']:
            return self.write_perm().has_permission(request, view)
        elif action in ['approve', 'reject', 'suspend']:
            return self.admin_perm().has_permission(request, view)
        
        return False
    
    def has_object_permission(self, request, view, obj):
        action = getattr(view, 'action', None)
        
        if action in ['list', 'retrieve']:
            if hasattr(self.read_perm, 'has_object_permission'):
                return self.read_perm().has_object_permission(request, view, obj)
        elif action in ['update', 'partial_update', 'destroy']:
            if hasattr(self.write_perm, 'has_object_permission'):
                return self.write_perm().has_object_permission(request, view, obj)
        
        return True


# Permission sets for common use cases
VENDOR_BASIC_PERMISSIONS = [IsAuthenticated, IsVendorUser]
VENDOR_FULL_PERMISSIONS = [IsAuthenticated, IsVendorOwnerOrAdmin]
ADMIN_ONLY_PERMISSIONS = [IsAuthenticated, IsAdminUser]
VENDOR_APPROVED_PERMISSIONS = [IsAuthenticated, IsApprovedVendor]
INTERNAL_SERVICE_PERMISSIONS = [HasVendorServicePermission]
PUBLIC_READ_PERMISSIONS = [PublicReadOnly]