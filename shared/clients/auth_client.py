import requests
import logging
from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from typing import Optional, Dict, Any, List
import jwt
from jwt import PyJWTError
import time

from shared.exceptions import AuthServiceError, ExternalServiceError, handle_service_exception

logger = logging.getLogger(__name__)


class AuthClient:
    """
    Client for communicating with the Auth Service microservice.
    Handles user authentication, authorization, and profile management.
    """
    
    def __init__(self):
        self.base_url = settings.AUTH_SERVICE_URL.rstrip('/')
        self.service_token = getattr(settings, 'SERVICE_TOKENS', {}).get('auth_service')
        self.timeout = getattr(settings, 'EXTERNAL_SERVICE_TIMEOUT', 30)
        self.retry_attempts = getattr(settings, 'EXTERNAL_SERVICE_RETRIES', 3)
    
    def _get_headers(self, additional_headers: Dict[str, str] = None) -> Dict[str, str]:
        """
        Get default headers for auth service requests.
        """
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'VendorService/1.0',
        }
        
        # Add service token for internal service communication
        if self.service_token:
            headers['X-Service-Token'] = self.service_token
        
        # Add additional headers if provided
        if additional_headers:
            headers.update(additional_headers)
        
        return headers
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make HTTP request to auth service with error handling and retry logic.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Ensure headers are set
        if 'headers' not in kwargs:
            kwargs['headers'] = self._get_headers()
        else:
            kwargs['headers'] = self._get_headers(kwargs['headers'])
        
        # Set timeout
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        
        last_exception = None
        
        for attempt in range(self.retry_attempts):
            try:
                logger.debug(f"Auth service request: {method} {url} (attempt {attempt + 1})")
                
                response = requests.request(method, url, **kwargs)
                
                # If successful, return response
                if response.status_code < 400:
                    return response
                
                # Handle specific error cases
                if response.status_code == 401:
                    raise AuthServiceError("Authentication failed", status.HTTP_401_UNAUTHORIZED)
                elif response.status_code == 403:
                    raise AuthServiceError("Access forbidden", status.HTTP_403_FORBIDDEN)
                elif response.status_code == 404:
                    raise AuthServiceError("Resource not found", status.HTTP_404_NOT_FOUND)
                elif response.status_code == 429:
                    # Rate limiting - wait and retry
                    retry_after = int(response.headers.get('Retry-After', 5))
                    time.sleep(retry_after)
                    continue
                else:
                    # For other errors, try to extract error message
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                    except:
                        error_msg = response.text or 'Unknown error'
                    
                    raise AuthServiceError(f"HTTP {response.status_code}: {error_msg}", response.status_code)
            
            except requests.Timeout as e:
                last_exception = e
                logger.warning(f"Auth service timeout on attempt {attempt + 1}: {str(e)}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
            
            except requests.ConnectionError as e:
                last_exception = e
                logger.error(f"Auth service connection error on attempt {attempt + 1}: {str(e)}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
            
            except AuthServiceError as e:
                # Don't retry on business logic errors
                raise e
            
            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected error contacting auth service on attempt {attempt + 1}: {str(e)}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
        
        # If we've exhausted all retry attempts
        if last_exception:
            handle_service_exception("Auth", last_exception)
        else:
            raise AuthServiceError("Failed to connect to auth service after multiple attempts")
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token with auth service.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Dict containing user information if token is valid
            
        Raises:
            AuthServiceError: If token is invalid or validation fails
        """
        cache_key = f"auth_token_{token}"
        
        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            response = self._make_request(
                'POST',
                '/api/auth/validate-token/',
                json={'token': token}
            )
            
            user_data = response.json()
            
            # Cache successful validation for 5 minutes
            cache.set(cache_key, user_data, 300)
            
            return user_data
            
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            raise AuthServiceError(f"Token validation failed: {str(e)}")
    
    def get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """
        Get user profile from auth service.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dict containing user profile information
        """
        cache_key = f"user_profile_{user_id}"
        
        # Check cache first
        cached_profile = cache.get(cache_key)
        if cached_profile:
            return cached_profile
        
        try:
            response = self._make_request('GET', f'/api/users/{user_id}/')
            profile_data = response.json()
            
            # Cache user profile for 10 minutes
            cache.set(cache_key, profile_data, 600)
            
            return profile_data
            
        except Exception as e:
            logger.error(f"Failed to get user profile for user {user_id}: {str(e)}")
            raise AuthServiceError(f"Failed to get user profile: {str(e)}")
    
    def update_user_profile(self, user_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user profile in auth service.
        
        Args:
            user_id: ID of the user
            update_data: Data to update
            
        Returns:
            Dict containing updated user profile
        """
        try:
            response = self._make_request(
                'PATCH',
                f'/api/users/{user_id}/',
                json=update_data
            )
            
            updated_profile = response.json()
            
            # Invalidate cache
            cache.delete(f"user_profile_{user_id}")
            
            return updated_profile
            
        except Exception as e:
            logger.error(f"Failed to update user profile for user {user_id}: {str(e)}")
            raise AuthServiceError(f"Failed to update user profile: {str(e)}")
    
    def update_user_role(self, user_id: int, user_type: str) -> Dict[str, Any]:
        """
        Update user role/type in auth service.
        
        Args:
            user_id: ID of the user
            user_type: New user type (customer, vendor, admin)
            
        Returns:
            Dict containing updated user profile
        """
        try:
            response = self._make_request(
                'PATCH',
                f'/api/users/{user_id}/',
                json={'user_type': user_type}
            )
            
            updated_profile = response.json()
            
            # Invalidate cache
            cache.delete(f"user_profile_{user_id}")
            
            return updated_profile
            
        except Exception as e:
            logger.error(f"Failed to update user role for user {user_id}: {str(e)}")
            raise AuthServiceError(f"Failed to update user role: {str(e)}")
    
    def get_users_batch(self, user_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """
        Get multiple user profiles in batch.
        
        Args:
            user_ids: List of user IDs
            
        Returns:
            Dict mapping user_id to user profile
        """
        if not user_ids:
            return {}
        
        # Check cache first
        cached_users = {}
        missing_ids = []
        
        for user_id in user_ids:
            cache_key = f"user_profile_{user_id}"
            cached_profile = cache.get(cache_key)
            if cached_profile:
                cached_users[user_id] = cached_profile
            else:
                missing_ids.append(user_id)
        
        # If all users are cached, return them
        if not missing_ids:
            return cached_users
        
        try:
            response = self._make_request(
                'POST',
                '/api/users/batch/',
                json={'user_ids': missing_ids}
            )
            
            batch_users = response.json()
            
            # Cache the new users and combine with cached ones
            for user_id, user_data in batch_users.items():
                cache_key = f"user_profile_{user_id}"
                cache.set(cache_key, user_data, 600)
                cached_users[int(user_id)] = user_data
            
            return cached_users
            
        except Exception as e:
            logger.error(f"Failed to get batch users: {str(e)}")
            # Return whatever we have from cache
            return cached_users
    
    def verify_user_permission(self, user_id: int, permission: str, resource: str = None) -> bool:
        """
        Verify if user has specific permission.
        
        Args:
            user_id: ID of the user
            permission: Permission to check
            resource: Optional resource for context
            
        Returns:
            Boolean indicating if user has permission
        """
        try:
            payload = {
                'user_id': user_id,
                'permission': permission
            }
            if resource:
                payload['resource'] = resource
            
            response = self._make_request(
                'POST',
                '/api/auth/verify-permission/',
                json=payload
            )
            
            result = response.json()
            return result.get('has_permission', False)
            
        except Exception as e:
            logger.error(f"Failed to verify permission for user {user_id}: {str(e)}")
            return False
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new user in auth service.
        Used for creating vendor accounts that need auth service users.
        
        Args:
            user_data: User creation data
            
        Returns:
            Dict containing created user information
        """
        try:
            response = self._make_request(
                'POST',
                '/api/auth/register/',
                json=user_data
            )
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to create user: {str(e)}")
            raise AuthServiceError(f"Failed to create user: {str(e)}")
    
    def deactivate_user(self, user_id: int, reason: str = None) -> bool:
        """
        Deactivate a user account.
        
        Args:
            user_id: ID of the user to deactivate
            reason: Reason for deactivation
            
        Returns:
            Boolean indicating success
        """
        try:
            payload = {'is_active': False}
            if reason:
                payload['deactivation_reason'] = reason
            
            response = self._make_request(
                'PATCH',
                f'/api/users/{user_id}/',
                json=payload
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Failed to deactivate user {user_id}: {str(e)}")
            raise AuthServiceError(f"Failed to deactivate user: {str(e)}")
    
    def search_users(self, query: str, user_type: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search users by email, name, or other criteria.
        
        Args:
            query: Search query
            user_type: Filter by user type
            limit: Maximum number of results
            
        Returns:
            List of user profiles matching the search
        """
        try:
            params = {'search': query, 'limit': limit}
            if user_type:
                params['user_type'] = user_type
            
            response = self._make_request('GET', '/api/users/search/', params=params)
            
            return response.json().get('results', [])
            
        except Exception as e:
            logger.error(f"Failed to search users: {str(e)}")
            return []
    
    def get_user_stats(self) -> Dict[str, Any]:
        """
        Get user statistics from auth service.
        
        Returns:
            Dict containing user statistics
        """
        cache_key = "user_stats"
        
        # Check cache first
        cached_stats = cache.get(cache_key)
        if cached_stats:
            return cached_stats
        
        try:
            response = self._make_request('GET', '/api/auth/stats/')
            stats = response.json()
            
            # Cache stats for 15 minutes
            cache.set(cache_key, stats, 900)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get user stats: {str(e)}")
            return {}
    
    def validate_api_key(self, api_key: str) -> Dict[str, Any]:
        """
        Validate API key for service-to-service communication.
        
        Args:
            api_key: API key to validate
            
        Returns:
            Dict containing validation result and service information
        """
        try:
            response = self._make_request(
                'POST',
                '/api/auth/validate-api-key/',
                json={'api_key': api_key},
                headers=self._get_headers({'X-API-Key': api_key})
            )
            
            return response.json()
            
        except Exception as e:
            logger.error(f"API key validation failed: {str(e)}")
            raise AuthServiceError(f"API key validation failed: {str(e)}")


class CachedAuthClient(AuthClient):
    """
    Extended auth client with enhanced caching capabilities.
    """
    
    def __init__(self):
        super().__init__()
        self.cache_ttl = {
            'user_profile': 600,  # 10 minutes
            'token_validation': 300,  # 5 minutes
            'user_stats': 900,  # 15 minutes
            'permission_check': 300,  # 5 minutes
        }
    
    def get_user_profile_with_cache(self, user_id: int, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get user profile with cache control.
        
        Args:
            user_id: ID of the user
            force_refresh: Whether to force refresh from source
            
        Returns:
            Dict containing user profile information
        """
        cache_key = f"user_profile_{user_id}"
        
        if not force_refresh:
            cached_profile = cache.get(cache_key)
            if cached_profile:
                return cached_profile
        
        profile = super().get_user_profile(user_id)
        cache.set(cache_key, profile, self.cache_ttl['user_profile'])
        return profile
    
    def batch_get_user_profiles(self, user_ids: List[int], force_refresh: bool = False) -> Dict[int, Dict[str, Any]]:
        """
        Get multiple user profiles with efficient caching.
        
        Args:
            user_ids: List of user IDs
            force_refresh: Whether to force refresh from source
            
        Returns:
            Dict mapping user_id to user profile
        """
        if not user_ids:
            return {}
        
        result = {}
        missing_ids = []
        
        if not force_refresh:
            for user_id in user_ids:
                cache_key = f"user_profile_{user_id}"
                cached_profile = cache.get(cache_key)
                if cached_profile:
                    result[user_id] = cached_profile
                else:
                    missing_ids.append(user_id)
        else:
            missing_ids = user_ids
        
        if missing_ids:
            try:
                batch_profiles = self.get_users_batch(missing_ids)
                result.update(batch_profiles)
                
                # Cache the newly fetched profiles
                for user_id, profile in batch_profiles.items():
                    cache_key = f"user_profile_{user_id}"
                    cache.set(cache_key, profile, self.cache_ttl['user_profile'])
                    
            except Exception as e:
                logger.error(f"Failed to get batch user profiles: {str(e)}")
        
        return result


# Singleton instance for easy access
auth_client = CachedAuthClient()


# Utility functions for common auth operations
def get_current_user(request) -> Dict[str, Any]:
    """
    Get current user from request using auth client.
    
    Args:
        request: Django request object
        
    Returns:
        Dict containing user information
    """
    auth_header = request.headers.get('Authorization', '')
    
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        try:
            return auth_client.validate_token(token)
        except AuthServiceError:
            pass
    
    # Fallback to user in request if available (for testing/dev)
    if hasattr(request, 'user') and request.user.is_authenticated:
        return {
            'id': request.user.id,
            'email': request.user.email,
            'user_type': getattr(request.user, 'user_type', 'customer'),
            'is_active': request.user.is_active,
        }
    
    return None


def has_permission(user_id: int, permission: str, resource: str = None) -> bool:
    """
    Check if user has specific permission.
    
    Args:
        user_id: ID of the user
        permission: Permission to check
        resource: Optional resource for context
        
    Returns:
        Boolean indicating if user has permission
    """
    return auth_client.verify_user_permission(user_id, permission, resource)


def update_user_role(user_id: int, user_type: str) -> bool:
    """
    Update user role/type.
    
    Args:
        user_id: ID of the user
        user_type: New user type
        
    Returns:
        Boolean indicating success
    """
    try:
        auth_client.update_user_role(user_id, user_type)
        return True
    except AuthServiceError:
        return False