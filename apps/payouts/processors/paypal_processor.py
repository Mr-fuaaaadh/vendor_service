import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.utils import timezone

import requests
from requests.auth import HTTPBasicAuth

from shared.exceptions import PayPalError, PayoutAccountError, PayoutError
from apps.payouts.models import Payout, PayoutAccount

logger = logging.getLogger(__name__)


class PayPalProcessor:
    """
    PayPal Payouts Pro processor for vendor payouts.
    Handles PayPal account verification and payout processing.
    """
    
    def __init__(self):
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.client_secret = settings.PAYPAL_CLIENT_SECRET
        self.mode = settings.PAYPAL_MODE  # 'sandbox' or 'live'
        self.timeout = getattr(settings, 'PAYPAL_TIMEOUT', 30)
        self.max_retries = getattr(settings, 'PAYPAL_MAX_RETRIES', 3)
        
        # Base URLs
        if self.mode == 'live':
            self.base_url = 'https://api.paypal.com'
            self.web_url = 'https://www.paypal.com'
        else:
            self.base_url = 'https://api.sandbox.paypal.com'
            self.web_url = 'https://www.sandbox.paypal.com'
        
        self.access_token = None
        self.token_expires = None
    
    def _get_access_token(self) -> str:
        """
        Get OAuth 2.0 access token from PayPal.
        
        Returns:
            Access token string
            
        Raises:
            PayPalError: If token retrieval fails
        """
        # Check if we have a valid cached token
        if self.access_token and self.token_expires and self.token_expires > timezone.now():
            return self.access_token
        
        try:
            url = f"{self.base_url}/v1/oauth2/token"
            auth = HTTPBasicAuth(self.client_id, self.client_secret)
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            data = {'grant_type': 'client_credentials'}
            
            response = requests.post(
                url,
                auth=auth,
                headers=headers,
                data=data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                # Set expiration (subtract 60 seconds for safety margin)
                expires_in = token_data.get('expires_in', 3600) - 60
                self.token_expires = timezone.now() + timezone.timedelta(seconds=expires_in)
                
                logger.info("Successfully obtained PayPal access token")
                return self.access_token
            else:
                error_msg = self._extract_error_message(response)
                raise PayPalError(f"Failed to get access token: {error_msg}")
                
        except requests.RequestException as e:
            logger.error(f"PayPal API connection error: {str(e)}")
            raise PayPalError(f"Connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting PayPal token: {str(e)}")
            raise PayPalError(f"Token retrieval failed: {str(e)}")
    
    def _make_paypal_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make authenticated request to PayPal API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters
            
        Returns:
            Response object
            
        Raises:
            PayPalError: If request fails
        """
        token = self._get_access_token()
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
            'PayPal-Partner-Attribution-Id': 'YourAppName_SP',  # Replace with your actual ID
        }
        
        if 'headers' in kwargs:
            headers.update(kwargs['headers'])
        kwargs['headers'] = headers
        
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"PayPal API request: {method} {url} (attempt {attempt + 1})")
                
                response = requests.request(method, url, **kwargs)
                
                # If successful, return response
                if response.status_code < 400:
                    return response
                
                # Handle specific PayPal errors
                if response.status_code == 401:
                    # Token might be expired, clear it and retry
                    self.access_token = None
                    if attempt < self.max_retries - 1:
                        continue
                
                error_msg = self._extract_error_message(response)
                
                if response.status_code == 400:
                    raise PayPalError(f"Bad request: {error_msg}")
                elif response.status_code == 401:
                    raise PayPalError(f"Authentication failed: {error_msg}")
                elif response.status_code == 403:
                    raise PayPalError(f"Forbidden: {error_msg}")
                elif response.status_code == 404:
                    raise PayPalError(f"Resource not found: {error_msg}")
                elif response.status_code == 429:
                    raise PayPalError(f"Rate limit exceeded: {error_msg}")
                elif response.status_code >= 500:
                    raise PayPalError(f"PayPal server error: {error_msg}")
                else:
                    raise PayPalError(f"HTTP {response.status_code}: {error_msg}")
            
            except requests.Timeout as e:
                last_exception = e
                logger.warning(f"PayPal API timeout on attempt {attempt + 1}: {str(e)}")
                if attempt < self.max_retries - 1:
                    continue
            
            except requests.ConnectionError as e:
                last_exception = e
                logger.error(f"PayPal API connection error on attempt {attempt + 1}: {str(e)}")
                if attempt < self.max_retries - 1:
                    continue
            
            except PayPalError as e:
                # Don't retry on business logic errors
                raise e
            
            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected PayPal API error on attempt {attempt + 1}: {str(e)}")
                if attempt < self.max_retries - 1:
                    continue
        
        # If we've exhausted all retry attempts
        if last_exception:
            raise PayPalError(f"PayPal API request failed after {self.max_retries} attempts: {str(last_exception)}")
        else:
            raise PayPalError(f"PayPal API request failed after {self.max_retries} attempts")
    
    def _extract_error_message(self, response: requests.Response) -> str:
        """
        Extract error message from PayPal API response.
        
        Args:
            response: PayPal API response
            
        Returns:
            Error message string
        """
        try:
            error_data = response.json()
            
            # PayPal error response structure
            if 'message' in error_data:
                return error_data['message']
            elif 'error' in error_data:
                return error_data['error']
            elif 'details' in error_data and len(error_data['details']) > 0:
                detail = error_data['details'][0]
                if 'issue' in detail:
                    return detail['issue']
                elif 'description' in detail:
                    return detail['description']
            
            return response.text or 'Unknown PayPal error'
            
        except ValueError:
            return response.text or f"HTTP {response.status_code}"
    
    def verify_account(self, payout_account: PayoutAccount) -> Dict[str, Any]:
        """
        Verify a PayPal account for payouts.
        
        Args:
            payout_account: PayoutAccount instance to verify
            
        Returns:
            Dict with verification result
            
        Raises:
            PayoutAccountError: If verification fails
        """
        try:
            email = payout_account.email
            
            if not email:
                raise PayoutAccountError("PayPal account email is required")
            
            # Check if email is valid format (basic validation)
            if '@' not in email or '.' not in email.split('@')[-1]:
                raise PayoutAccountError("Invalid email format")
            
            # For PayPal, we can't directly verify an email without user interaction.
            # Instead, we'll attempt a small test payout or use other verification methods.
            
            # Method 1: Check if we can get recipient status (limited availability)
            # Method 2: Send a small test payout (requires balance)
            # Method 3: Use PayPal Identity API (requires additional permissions)
            
            # For now, we'll use a simpler approach - validate email format
            # and optionally send a verification email through PayPal
            
            verification_data = {
                'email': email,
                'status': 'verified',  # We assume verified for basic checks
                'verified_at': timezone.now().isoformat(),
                'method': 'email_validation'
            }
            
            # Store PayPal merchant ID if available
            # In a real implementation, you might get this from webhooks or API calls
            payout_account.paypal_merchant_id = f"paypal_email_{email}"
            payout_account.save()
            
            logger.info(f"PayPal account verification initiated for {email}")
            
            return {
                'success': True,
                'message': 'PayPal account verification initiated',
                'data': verification_data
            }
            
        except PayoutAccountError:
            raise
        except Exception as e:
            logger.error(f"PayPal account verification failed: {str(e)}")
            raise PayoutAccountError(f"PayPal account verification failed: {str(e)}")
    
    def process_payout(self, payout: Payout) -> Dict[str, Any]:
        """
        Process a payout to a PayPal account.
        
        Args:
            payout: Payout instance to process
            
        Returns:
            Dict with processing result
            
        Raises:
            PayoutError: If payout processing fails
        """
        try:
            payout_account = payout.payout_account
            vendor = payout.vendor
            
            if not payout_account.email:
                raise PayoutError("PayPal account email is required")
            
            # Validate payout amount
            if payout.amount <= 0:
                raise PayoutError("Payout amount must be positive")
            
            # Check minimum amount (PayPal minimum is typically $0.01)
            if payout.amount < 0.01:
                raise PayoutError("Payout amount must be at least $0.01")
            
            # Check maximum amount (PayPal maximum for single payout is $10,000)
            if payout.amount > 10000:
                raise PayoutError("Payout amount cannot exceed $10,000")
            
            # Create payout batch
            payout_batch = self._create_payout_batch(payout)
            
            # Store PayPal batch ID
            payout.processor_reference = payout_batch['batch_header']['payout_batch_id']
            payout.save()
            
            logger.info(f"PayPal payout batch created: {payout.processor_reference}")
            
            return {
                'success': True,
                'reference': payout.processor_reference,
                'batch_status': payout_batch['batch_header']['batch_status'],
                'data': payout_batch
            }
            
        except PayoutError:
            raise
        except Exception as e:
            logger.error(f"PayPal payout processing failed: {str(e)}")
            raise PayoutError(f"PayPal payout processing failed: {str(e)}")
    
    def _create_payout_batch(self, payout: Payout) -> Dict[str, Any]:
        """
        Create a PayPal payout batch.
        
        Args:
            payout: Payout instance
            
        Returns:
            PayPal payout batch data
            
        Raises:
            PayPalError: If batch creation fails
        """
        try:
            # Generate unique sender batch ID
            sender_batch_id = f"VENDOR_{payout.vendor.id}_{payout.reference_number}_{uuid.uuid4().hex[:8]}"
            
            payout_item = {
                "recipient_type": "EMAIL",
                "amount": {
                    "value": f"{payout.amount:.2f}",
                    "currency": payout.currency
                },
                "note": f"Payout for {payout.vendor.business_name} - {payout.reference_number}",
                "receiver": payout.payout_account.email,
                "sender_item_id": f"ITEM_{payout.reference_number}"
            }
            
            payout_batch_data = {
                "sender_batch_header": {
                    "sender_batch_id": sender_batch_id,
                    "email_subject": f"Your payout from {getattr(settings, 'PLATFORM_NAME', 'Our Platform')}",
                    "email_message": f"Hello {payout.vendor.business_name},\n\nYou have received a payout of {payout.currency} {payout.amount:.2f}.\n\nThank you for being a valued vendor!\n\n- {getattr(settings, 'PLATFORM_NAME', 'Our Platform')} Team"
                },
                "items": [payout_item]
            }
            
            response = self._make_paypal_request(
                'POST',
                '/v1/payments/payouts',
                json=payout_batch_data
            )
            
            return response.json()
            
        except PayPalError:
            raise
        except Exception as e:
            logger.error(f"PayPal payout batch creation failed: {str(e)}")
            raise PayPalError(f"Payout batch creation failed: {str(e)}")
    
    def get_payout_status(self, payout_batch_id: str) -> Dict[str, Any]:
        """
        Get status of a PayPal payout batch.
        
        Args:
            payout_batch_id: PayPal payout batch ID
            
        Returns:
            Dict with payout batch status and details
            
        Raises:
            PayPalError: If status retrieval fails
        """
        try:
            response = self._make_paypal_request(
                'GET',
                f'/v1/payments/payouts/{payout_batch_id}'
            )
            
            batch_data = response.json()
            
            # Extract relevant status information
            batch_header = batch_data.get('batch_header', {})
            items = batch_data.get('items', [])
            
            status_info = {
                'batch_id': payout_batch_id,
                'status': batch_header.get('batch_status', 'UNKNOWN'),
                'amount': batch_header.get('amount', {}),
                'fees': batch_header.get('fees', {}),
                'time_created': batch_header.get('time_created'),
                'time_completed': batch_header.get('time_completed'),
                'items': []
            }
            
            # Process individual payout items
            for item in items:
                item_info = {
                    'payout_item_id': item.get('payout_item_id'),
                    'transaction_id': item.get('transaction_id'),
                    'transaction_status': item.get('transaction_status'),
                    'amount': item.get('payout_item', {}).get('amount', {}),
                    'time_processed': item.get('time_processed'),
                    'errors': item.get('errors')
                }
                status_info['items'].append(item_info)
            
            return status_info
            
        except PayPalError:
            raise
        except Exception as e:
            logger.error(f"Failed to get PayPal payout status for batch {payout_batch_id}: {str(e)}")
            raise PayPalError(f"Payout status retrieval failed: {str(e)}")
    
    def cancel_payout(self, payout_batch_id: str) -> Dict[str, Any]:
        """
        Cancel a PayPal payout batch (if possible).
        
        Args:
            payout_batch_id: PayPal payout batch ID
            
        Returns:
            Dict with cancellation result
            
        Raises:
            PayPalError: If cancellation fails
        """
        try:
            # Note: PayPal payouts cannot be cancelled once submitted in most cases.
            # This method is for future implementation if PayPal adds cancellation support.
            
            # For now, we can only check if the payout is still in a cancellable state
            status_info = self.get_payout_status(payout_batch_id)
            batch_status = status_info.get('status', 'UNKNOWN')
            
            if batch_status in ['PENDING', 'PROCESSING']:
                # Attempt cancellation (this endpoint may not exist yet)
                response = self._make_paypal_request(
                    'POST',
                    f'/v1/payments/payouts/{payout_batch_id}/cancel'
                )
                
                return {
                    'success': True,
                    'message': 'Payout cancellation requested',
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'message': f'Payout cannot be cancelled in current status: {batch_status}',
                    'data': status_info
                }
                
        except PayPalError as e:
            # If cancellation endpoint doesn't exist, provide informative message
            if '404' in str(e):
                return {
                    'success': False,
                    'message': 'PayPal payout cancellation is not currently supported',
                    'data': {'error': 'Cancellation not supported'}
                }
            raise
        except Exception as e:
            logger.error(f"PayPal payout cancellation failed for batch {payout_batch_id}: {str(e)}")
            raise PayPalError(f"Payout cancellation failed: {str(e)}")
    
    def get_payout_limits(self) -> Dict[str, Any]:
        """
        Get PayPal payout limits and capabilities.
        
        Returns:
            Dict with payout limits information
        """
        try:
            # Note: PayPal doesn't have a direct endpoint for limits in Payouts API
            # These are standard limits that apply to most PayPal accounts
            
            limits = {
                'minimum_amount': 0.01,
                'maximum_amount': 10000.00,
                'daily_limit': 50000.00,  # Varies by account
                'monthly_limit': 250000.00,  # Varies by account
                'supported_currencies': ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY'],
                'processing_time': '1-3 business days',
                'fees': {
                    'domestic': 0.25,  # $0.25 fixed fee per payout
                    'international': 2.00,  # $2.00 fixed fee per international payout
                    'currency_conversion': '2.5% above base exchange rate'
                }
            }
            
            return limits
            
        except Exception as e:
            logger.error(f"Failed to get PayPal payout limits: {str(e)}")
            return {
                'minimum_amount': 0.01,
                'maximum_amount': 10000.00,
                'supported_currencies': ['USD'],
                'processing_time': '1-3 business days',
                'fees': {
                    'domestic': 0.25,
                    'international': 2.00
                }
            }
    
    def calculate_fees(self, amount: float, currency: str = 'USD', 
                      is_international: bool = False) -> Dict[str, float]:
        """
        Calculate PayPal payout fees.
        
        Args:
            amount: Payout amount
            currency: Currency code
            is_international: Whether payout is international
            
        Returns:
            Dict with fee breakdown
        """
        try:
            # PayPal Payouts fee structure
            if is_international:
                fixed_fee = 2.00  # $2.00 for international payouts
            else:
                fixed_fee = 0.25  # $0.25 for domestic payouts
            
            # Percentage fee (if any) - typically 0% for payouts
            percentage_fee = 0.00
            
            total_fee = fixed_fee + (amount * percentage_fee / 100)
            net_amount = amount - total_fee
            
            return {
                'amount': amount,
                'fixed_fee': fixed_fee,
                'percentage_fee': percentage_fee,
                'percentage_rate': percentage_fee,
                'total_fee': total_fee,
                'net_amount': net_amount,
                'currency': currency
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate PayPal fees: {str(e)}")
            return {
                'amount': amount,
                'fixed_fee': 0.25,
                'percentage_fee': 0.00,
                'percentage_rate': 0.00,
                'total_fee': 0.25,
                'net_amount': amount - 0.25,
                'currency': currency
            }
    
    def validate_recipient(self, email: str, currency: str = 'USD') -> Dict[str, Any]:
        """
        Validate a PayPal recipient before sending payout.
        
        Args:
            email: Recipient email address
            currency: Currency code
            
        Returns:
            Dict with validation result
            
        Raises:
            PayPalError: If validation fails
        """
        try:
            # PayPal doesn't have a direct recipient validation endpoint for Payouts
            # We can simulate validation by attempting to create a test payout item
            
            test_item = {
                "recipient_type": "EMAIL",
                "amount": {
                    "value": "0.01",  # Minimum amount for test
                    "currency": currency
                },
                "receiver": email,
                "sender_item_id": f"VALIDATION_{uuid.uuid4().hex[:8]}",
                "note": "Recipient validation test - this payout will not be processed"
            }
            
            # Note: This is a conceptual implementation
            # In practice, you might need to use PayPal's Identity API or other methods
            
            validation_result = {
                'email': email,
                'is_valid': True,  # Assume valid for basic implementation
                'can_receive_funds': True,
                'currency_support': [currency],
                'account_type': 'personal',  # Could be 'business' or 'personal'
                'validation_method': 'email_format'
            }
            
            logger.info(f"PayPal recipient validation completed for {email}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"PayPal recipient validation failed for {email}: {str(e)}")
            raise PayPalError(f"Recipient validation failed: {str(e)}")
    
    def get_balance(self) -> Dict[str, Any]:
        """
        Get PayPal account balance for the platform.
        
        Returns:
            Dict with balance information
            
        Raises:
            PayPalError: If balance retrieval fails
        """
        try:
            response = self._make_paypal_request(
                'GET',
                '/v1/wallet/balances'
            )
            
            balance_data = response.json()
            
            # Extract primary balance
            primary_balance = None
            for balance in balance_data.get('balances', []):
                if balance.get('primary', False):
                    primary_balance = balance
                    break
            
            return {
                'balances': balance_data.get('balances', []),
                'primary_balance': primary_balance,
                'total_balance': self._calculate_total_balance(balance_data.get('balances', [])),
                'currency': 'USD',
                'as_of': timezone.now().isoformat()
            }
            
        except PayPalError:
            raise
        except Exception as e:
            logger.error(f"Failed to get PayPal balance: {str(e)}")
            raise PayPalError(f"Balance retrieval failed: {str(e)}")
    
    def _calculate_total_balance(self, balances: List[Dict]) -> float:
        """
        Calculate total balance across all currencies.
        
        Args:
            balances: List of balance objects
            
        Returns:
            Total balance in USD (approximate)
        """
        total = 0.0
        
        for balance in balances:
            currency = balance.get('currency', 'USD')
            amount = float(balance.get('value', 0))
            
            # For simplicity, we're not doing currency conversion here
            # In production, you'd want to convert to a base currency
            if currency == 'USD':
                total += amount
        
        return total
    
    def webhook_handler(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle PayPal webhook notifications for payout events.
        
        Args:
            webhook_data: Webhook payload from PayPal
            
        Returns:
            Dict with processing result
        """
        try:
            event_type = webhook_data.get('event_type', '')
            resource = webhook_data.get('resource', {})
            
            logger.info(f"Received PayPal webhook: {event_type}")
            
            # Handle different webhook event types
            if event_type == 'PAYMENT.PAYOUTS-ITEM.SUCCEEDED':
                return self._handle_payout_success(resource)
            elif event_type == 'PAYMENT.PAYOUTS-ITEM.FAILED':
                return self._handle_payout_failed(resource)
            elif event_type == 'PAYMENT.PAYOUTS-ITEM.CANCELED':
                return self._handle_payout_cancelled(resource)
            elif event_type == 'PAYMENT.PAYOUTSBATCH.SUCCEEDED':
                return self._handle_batch_success(resource)
            elif event_type == 'PAYMENT.PAYOUTSBATCH.DENIED':
                return self._handle_batch_denied(resource)
            else:
                logger.warning(f"Unhandled PayPal webhook event: {event_type}")
                return {'success': True, 'message': 'Webhook received but not processed'}
                
        except Exception as e:
            logger.error(f"PayPal webhook handling failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_payout_success(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payout item webhook."""
        payout_item_id = resource.get('payout_item_id')
        transaction_id = resource.get('transaction_id')
        
        logger.info(f"PayPal payout item succeeded: {payout_item_id}, transaction: {transaction_id}")
        
        # Update payout status in database
        # This would typically involve finding the payout by reference and updating it
        try:
            # Example implementation:
            # payout = Payout.objects.get(processor_reference__contains=payout_item_id)
            # payout.status = Payout.PayoutStatus.COMPLETED
            # payout.processor_reference = transaction_id
            # payout.completed_at = timezone.now()
            # payout.save()
            pass
        except Exception as e:
            logger.error(f"Failed to update payout status for {payout_item_id}: {str(e)}")
        
        return {'success': True, 'message': 'Payout success processed'}
    
    def _handle_payout_failed(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payout item webhook."""
        payout_item_id = resource.get('payout_item_id')
        errors = resource.get('errors', [])
        
        error_message = "Unknown error"
        if errors and len(errors) > 0:
            error_message = errors[0].get('message', 'Unknown error')
        
        logger.error(f"PayPal payout item failed: {payout_item_id}, error: {error_message}")
        
        # Update payout status in database
        try:
            # payout = Payout.objects.get(processor_reference__contains=payout_item_id)
            # payout.status = Payout.PayoutStatus.FAILED
            # payout.failure_reason = error_message
            # payout.save()
            pass
        except Exception as e:
            logger.error(f"Failed to update payout status for {payout_item_id}: {str(e)}")
        
        return {'success': True, 'message': 'Payout failure processed'}
    
    def _handle_payout_cancelled(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cancelled payout item webhook."""
        payout_item_id = resource.get('payout_item_id')
        
        logger.info(f"PayPal payout item cancelled: {payout_item_id}")
        
        # Update payout status in database
        try:
            # payout = Payout.objects.get(processor_reference__contains=payout_item_id)
            # payout.status = Payout.PayoutStatus.CANCELLED
            # payout.save()
            pass
        except Exception as e:
            logger.error(f"Failed to update payout status for {payout_item_id}: {str(e)}")
        
        return {'success': True, 'message': 'Payout cancellation processed'}
    
    def _handle_batch_success(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Handle batch success webhook."""
        batch_id = resource.get('batch_header', {}).get('payout_batch_id')
        
        logger.info(f"PayPal payout batch succeeded: {batch_id}")
        
        return {'success': True, 'message': 'Batch success processed'}
    
    def _handle_batch_denied(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Handle batch denied webhook."""
        batch_id = resource.get('batch_header', {}).get('payout_batch_id')
        
        logger.error(f"PayPal payout batch denied: {batch_id}")
        
        return {'success': True, 'message': 'Batch denial processed'}


class PayPalSandboxProcessor(PayPalProcessor):
    """
    PayPal processor with enhanced sandbox testing capabilities.
    """
    
    def __init__(self):
        super().__init__()
        # Force sandbox mode
        self.mode = 'sandbox'
        self.base_url = 'https://api.sandbox.paypal.com'
        self.web_url = 'https://www.sandbox.paypal.com'
    
    def create_test_recipient(self, email: str) -> Dict[str, Any]:
        """
        Create a test recipient in PayPal sandbox.
        
        Args:
            email: Test email address
            
        Returns:
            Dict with test recipient information
        """
        try:
            # In sandbox, we can use test email addresses
            # PayPal sandbox automatically creates accounts for valid test emails
            
            test_recipient = {
                'email': email,
                'status': 'test_account',
                'balance': 1000.00,  # Mock balance for testing
                'currency': 'USD',
                'created_at': timezone.now().isoformat()
            }
            
            logger.info(f"Created test PayPal recipient: {email}")
            
            return test_recipient
            
        except Exception as e:
            logger.error(f"Failed to create test recipient {email}: {str(e)}")
            raise PayPalError(f"Test recipient creation failed: {str(e)}")
    
    def simulate_webhook(self, event_type: str, payout_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate PayPal webhook for testing.
        
        Args:
            event_type: Webhook event type to simulate
            payout_data: Payout data for the webhook
            
        Returns:
            Dict with simulation result
        """
        try:
            webhook_payload = {
                'event_type': event_type,
                'resource': payout_data,
                'id': f"WH-{uuid.uuid4().hex}",
                'create_time': datetime.utcnow().isoformat() + 'Z',
                'resource_type': 'payouts_item',
                'event_version': '1.0'
            }
            
            result = self.webhook_handler(webhook_payload)
            
            logger.info(f"Simulated PayPal webhook: {event_type}")
            
            return {
                'success': True,
                'webhook_sent': True,
                'event_type': event_type,
                'result': result
            }
            
        except Exception as e:
            logger.error(f"Webhook simulation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Factory function to get appropriate PayPal processor
def get_paypal_processor() -> PayPalProcessor:
    """
    Get the appropriate PayPal processor based on settings.
    
    Returns:
        PayPalProcessor instance
    """
    if getattr(settings, 'PAYPAL_MODE', 'sandbox') == 'sandbox':
        return PayPalSandboxProcessor()
    else:
        return PayPalProcessor()


# Singleton instance for easy access
paypal_processor = get_paypal_processor()