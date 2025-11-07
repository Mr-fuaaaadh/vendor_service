import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db import IntegrityError, DatabaseError
from django.http import Http404
import requests

logger = logging.getLogger(__name__)


class CustomException(Exception):
    """
    Base custom exception class for the application.
    """
    def __init__(self, message, status_code=status.HTTP_400_BAD_REQUEST, details=None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class VendorServiceException(CustomException):
    """Base exception for vendor service specific errors"""
    pass


class VendorNotFoundError(VendorServiceException):
    """Raised when a vendor is not found"""
    def __init__(self, vendor_id=None, message="Vendor not found"):
        if vendor_id:
            message = f"Vendor with ID {vendor_id} not found"
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class VendorAlreadyExistsError(VendorServiceException):
    """Raised when trying to create a vendor that already exists"""
    def __init__(self, user_id=None, business_name=None):
        if user_id:
            message = f"Vendor account already exists for user {user_id}"
        elif business_name:
            message = f"Vendor with business name '{business_name}' already exists"
        else:
            message = "Vendor already exists"
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class VendorNotApprovedError(VendorServiceException):
    """Raised when a vendor tries to perform an action that requires approval"""
    def __init__(self, vendor_id=None):
        message = "Vendor account is not approved"
        if vendor_id:
            message = f"Vendor {vendor_id} is not approved"
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class VendorSuspendedError(VendorServiceException):
    """Raised when a suspended vendor tries to perform an action"""
    def __init__(self, vendor_id=None):
        message = "Vendor account is suspended"
        if vendor_id:
            message = f"Vendor {vendor_id} is suspended"
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class DocumentValidationError(VendorServiceException):
    """Raised when a document fails validation"""
    def __init__(self, message="Document validation failed", details=None):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class DocumentNotFoundError(VendorServiceException):
    """Raised when a document is not found"""
    def __init__(self, document_id=None):
        message = "Document not found"
        if document_id:
            message = f"Document with ID {document_id} not found"
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class PayoutError(VendorServiceException):
    """Base exception for payout related errors"""
    pass


class InsufficientBalanceError(PayoutError):
    """Raised when vendor has insufficient balance for payout"""
    def __init__(self, available_balance, requested_amount):
        message = f"Insufficient balance. Available: {available_balance}, Requested: {requested_amount}"
        details = {
            'available_balance': float(available_balance),
            'requested_amount': float(requested_amount)
        }
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class PayoutAccountError(PayoutError):
    """Raised when there's an issue with payout account"""
    def __init__(self, message="Payout account error", details=None):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class PayoutAccountNotVerifiedError(PayoutAccountError):
    """Raised when trying to use an unverified payout account"""
    def __init__(self, account_id=None):
        message = "Payout account is not verified"
        if account_id:
            message = f"Payout account {account_id} is not verified"
        super().__init__(message)


class MinimumPayoutAmountError(PayoutError):
    """Raised when payout amount is below minimum threshold"""
    def __init__(self, requested_amount, minimum_amount):
        message = f"Payout amount {requested_amount} is below minimum {minimum_amount}"
        details = {
            'requested_amount': float(requested_amount),
            'minimum_amount': float(minimum_amount)
        }
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class ExternalServiceError(VendorServiceException):
    """Raised when there's an error communicating with external services"""
    def __init__(self, service_name, message="External service error", status_code=None):
        self.service_name = service_name
        full_message = f"{service_name} service error: {message}"
        super().__init__(full_message, status_code=status_code or status.HTTP_503_SERVICE_UNAVAILABLE)


class AuthServiceError(ExternalServiceError):
    """Raised when there's an error with auth service"""
    def __init__(self, message="Authentication service error", status_code=None):
        super().__init__("Auth", message, status_code)


class ProductServiceError(ExternalServiceError):
    """Raised when there's an error with product service"""
    def __init__(self, message="Product service error", status_code=None):
        super().__init__("Product", message, status_code)


class OrderServiceError(ExternalServiceError):
    """Raised when there's an error with order service"""
    def __init__(self, message="Order service error", status_code=None):
        super().__init__("Order", message, status_code)


class PaymentProcessorError(VendorServiceException):
    """Raised when there's an error with payment processors"""
    def __init__(self, processor_name, message="Payment processor error", details=None):
        self.processor_name = processor_name
        full_message = f"{processor_name} error: {message}"
        super().__init__(full_message, status_code=status.HTTP_502_BAD_GATEWAY, details=details)


class StripeError(PaymentProcessorError):
    """Raised when there's an error with Stripe"""
    def __init__(self, message="Stripe payment error", details=None):
        super().__init__("Stripe", message, details)


class PayPalError(PaymentProcessorError):
    """Raised when there's an error with PayPal"""
    def __init__(self, message="PayPal payment error", details=None):
        super().__init__("PayPal", message, details)


class FileUploadError(VendorServiceException):
    """Raised when there's an error with file uploads"""
    def __init__(self, message="File upload error", details=None):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class FileSizeExceededError(FileUploadError):
    """Raised when uploaded file exceeds size limit"""
    def __init__(self, file_size, max_size):
        message = f"File size {file_size} exceeds maximum allowed size {max_size}"
        details = {
            'file_size': file_size,
            'max_size': max_size
        }
        super().__init__(message, details=details)


class InvalidFileTypeError(FileUploadError):
    """Raised when uploaded file type is not allowed"""
    def __init__(self, file_type, allowed_types):
        message = f"File type {file_type} is not allowed. Allowed types: {', '.join(allowed_types)}"
        details = {
            'file_type': file_type,
            'allowed_types': allowed_types
        }
        super().__init__(message, details=details)


class BusinessValidationError(VendorServiceException):
    """Raised when business validation fails"""
    def __init__(self, message="Business validation failed", details=None):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class OnboardingStepError(VendorServiceException):
    """Raised when there's an error in onboarding process"""
    def __init__(self, step_name, message="Onboarding step error"):
        full_message = f"Onboarding step '{step_name}' error: {message}"
        super().__init__(full_message, status_code=status.HTTP_400_BAD_REQUEST)


class ServiceUnavailableError(VendorServiceException):
    """Raised when a required service is unavailable"""
    def __init__(self, service_name, message="Service temporarily unavailable"):
        full_message = f"{service_name} {message}"
        super().__init__(full_message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class RateLimitExceededError(VendorServiceException):
    """Raised when rate limit is exceeded"""
    def __init__(self, message="Rate limit exceeded", retry_after=None):
        details = {}
        if retry_after:
            details['retry_after'] = retry_after
        super().__init__(message, status_code=status.HTTP_429_TOO_MANY_REQUESTS, details=details)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF that provides consistent error responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # If response is None, it's an unhandled exception
    if response is None:
        if isinstance(exc, CustomException):
            # Handle our custom exceptions
            response_data = {
                'error': {
                    'code': 'custom_error',
                    'message': exc.message,
                    'details': exc.details,
                    'status_code': exc.status_code
                }
            }
            response = Response(response_data, status=exc.status_code)
        
        elif isinstance(exc, Http404):
            response_data = {
                'error': {
                    'code': 'not_found',
                    'message': 'Resource not found',
                    'details': {'resource': str(exc)},
                    'status_code': status.HTTP_404_NOT_FOUND
                }
            }
            response = Response(response_data, status=status.HTTP_404_NOT_FOUND)
        
        elif isinstance(exc, PermissionDenied):
            response_data = {
                'error': {
                    'code': 'permission_denied',
                    'message': 'You do not have permission to perform this action',
                    'details': {},
                    'status_code': status.HTTP_403_FORBIDDEN
                }
            }
            response = Response(response_data, status=status.HTTP_403_FORBIDDEN)
        
        elif isinstance(exc, ObjectDoesNotExist):
            response_data = {
                'error': {
                    'code': 'not_found',
                    'message': 'Requested object not found',
                    'details': {},
                    'status_code': status.HTTP_404_NOT_FOUND
                }
            }
            response = Response(response_data, status=status.HTTP_404_NOT_FOUND)
        
        elif isinstance(exc, IntegrityError):
            logger.error(f"Integrity error: {str(exc)}")
            response_data = {
                'error': {
                    'code': 'integrity_error',
                    'message': 'Database integrity error occurred',
                    'details': {},
                    'status_code': status.HTTP_400_BAD_REQUEST
                }
            }
            response = Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        
        elif isinstance(exc, DatabaseError):
            logger.error(f"Database error: {str(exc)}")
            response_data = {
                'error': {
                    'code': 'database_error',
                    'message': 'Database error occurred',
                    'details': {},
                    'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
                }
            }
            response = Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        elif isinstance(exc, requests.RequestException):
            logger.error(f"External service request error: {str(exc)}")
            response_data = {
                'error': {
                    'code': 'external_service_error',
                    'message': 'Error communicating with external service',
                    'details': {'service': 'unknown'},
                    'status_code': status.HTTP_502_BAD_GATEWAY
                }
            }
            response = Response(response_data, status=status.HTTP_502_BAD_GATEWAY)
        
        else:
            # Log unexpected exceptions
            logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
            response_data = {
                'error': {
                    'code': 'server_error',
                    'message': 'An unexpected error occurred',
                    'details': {},
                    'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
                }
            }
            response = Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    else:
        # Handle DRF exceptions and format response consistently
        if isinstance(exc, ValidationError):
            # Format validation errors consistently
            error_details = {}
            if hasattr(exc, 'detail'):
                if isinstance(exc.detail, dict):
                    error_details = exc.detail
                elif isinstance(exc.detail, list):
                    error_details = {'non_field_errors': exc.detail}
            
            response_data = {
                'error': {
                    'code': 'validation_error',
                    'message': 'Invalid input data',
                    'details': error_details,
                    'status_code': response.status_code
                }
            }
        else:
            # For other DRF exceptions
            error_message = str(exc.detail) if hasattr(exc, 'detail') else str(exc)
            response_data = {
                'error': {
                    'code': 'api_error',
                    'message': error_message,
                    'details': {},
                    'status_code': response.status_code
                }
            }
        
        response.data = response_data
    
    # Add request ID for tracing if available
    request = context.get('request')
    if request and hasattr(request, 'id'):
        response.data['request_id'] = request.id
    
    return response


def handle_service_exception(service_name, exception):
    """
    Helper function to handle exceptions from external services.
    """
    if isinstance(exception, requests.Timeout):
        raise ServiceUnavailableError(service_name, "Request timeout")
    elif isinstance(exception, requests.ConnectionError):
        raise ServiceUnavailableError(service_name, "Connection error")
    elif isinstance(exception, requests.HTTPError):
        if exception.response.status_code == 404:
            raise ExternalServiceError(service_name, "Resource not found", status.HTTP_404_NOT_FOUND)
        elif exception.response.status_code == 401:
            raise ExternalServiceError(service_name, "Authentication failed", status.HTTP_401_UNAUTHORIZED)
        elif exception.response.status_code == 403:
            raise ExternalServiceError(service_name, "Access forbidden", status.HTTP_403_FORBIDDEN)
        else:
            raise ExternalServiceError(service_name, f"HTTP error: {exception.response.status_code}")
    else:
        raise ExternalServiceError(service_name, str(exception))


class ErrorCodes:
    """
    Standard error codes for the application.
    """
    # Vendor related errors
    VENDOR_NOT_FOUND = "vendor_not_found"
    VENDOR_ALREADY_EXISTS = "vendor_already_exists"
    VENDOR_NOT_APPROVED = "vendor_not_approved"
    VENDOR_SUSPENDED = "vendor_suspended"
    
    # Document related errors
    DOCUMENT_NOT_FOUND = "document_not_found"
    DOCUMENT_VALIDATION_FAILED = "document_validation_failed"
    FILE_UPLOAD_ERROR = "file_upload_error"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"
    INVALID_FILE_TYPE = "invalid_file_type"
    
    # Payout related errors
    INSUFFICIENT_BALANCE = "insufficient_balance"
    PAYOUT_ACCOUNT_ERROR = "payout_account_error"
    PAYOUT_ACCOUNT_NOT_VERIFIED = "payout_account_not_verified"
    MINIMUM_PAYOUT_AMOUNT = "minimum_payout_amount"
    
    # External service errors
    AUTH_SERVICE_ERROR = "auth_service_error"
    PRODUCT_SERVICE_ERROR = "product_service_error"
    ORDER_SERVICE_ERROR = "order_service_error"
    
    # Payment processor errors
    STRIPE_ERROR = "stripe_error"
    PAYPAL_ERROR = "paypal_error"
    
    # Business logic errors
    BUSINESS_VALIDATION_ERROR = "business_validation_error"
    ONBOARDING_STEP_ERROR = "onboarding_step_error"
    
    # System errors
    SERVICE_UNAVAILABLE = "service_unavailable"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    DATABASE_ERROR = "database_error"
    INTEGRITY_ERROR = "integrity_error"
    
    # General errors
    VALIDATION_ERROR = "validation_error"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    SERVER_ERROR = "server_error"


def create_error_response(code, message, details=None, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Helper function to create consistent error responses.
    """
    return Response({
        'error': {
            'code': code,
            'message': message,
            'details': details or {},
            'status_code': status_code
        }
    }, status=status_code)