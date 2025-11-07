import requests
import logging
from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from typing import Optional, Dict, Any, List
import time

from shared.exceptions import ProductServiceError, ExternalServiceError, handle_service_exception

logger = logging.getLogger(__name__)


class ProductClient:
    """
    Client for communicating with the Product Service microservice.
    Handles product-related operations for vendors.
    """
    
    def __init__(self):
        self.base_url = settings.PRODUCT_SERVICE_URL.rstrip('/')
        self.service_token = getattr(settings, 'SERVICE_TOKENS', {}).get('product_service')
        self.timeout = getattr(settings, 'EXTERNAL_SERVICE_TIMEOUT', 30)
        self.retry_attempts = getattr(settings, 'EXTERNAL_SERVICE_RETRIES', 3)
    
    def _get_headers(self, additional_headers: Dict[str, str] = None) -> Dict[str, str]:
        """
        Get default headers for product service requests.
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
        Make HTTP request to product service with error handling and retry logic.
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
                logger.debug(f"Product service request: {method} {url} (attempt {attempt + 1})")
                
                response = requests.request(method, url, **kwargs)
                
                # If successful, return response
                if response.status_code < 400:
                    return response
                
                # Handle specific error cases
                if response.status_code == 401:
                    raise ProductServiceError("Authentication failed", status.HTTP_401_UNAUTHORIZED)
                elif response.status_code == 403:
                    raise ProductServiceError("Access forbidden", status.HTTP_403_FORBIDDEN)
                elif response.status_code == 404:
                    raise ProductServiceError("Resource not found", status.HTTP_404_NOT_FOUND)
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
                    
                    raise ProductServiceError(f"HTTP {response.status_code}: {error_msg}", response.status_code)
            
            except requests.Timeout as e:
                last_exception = e
                logger.warning(f"Product service timeout on attempt {attempt + 1}: {str(e)}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
            
            except requests.ConnectionError as e:
                last_exception = e
                logger.error(f"Product service connection error on attempt {attempt + 1}: {str(e)}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
            
            except ProductServiceError as e:
                # Don't retry on business logic errors
                raise e
            
            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected error contacting product service on attempt {attempt + 1}: {str(e)}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
        
        # If we've exhausted all retry attempts
        if last_exception:
            handle_service_exception("Product", last_exception)
        else:
            raise ProductServiceError("Failed to connect to product service after multiple attempts")
    
    def get_vendor_product_count(self, vendor_id: int) -> int:
        """
        Get total number of products for a vendor.
        
        Args:
            vendor_id: ID of the vendor
            
        Returns:
            Number of products
        """
        cache_key = f"vendor_product_count_{vendor_id}"
        
        # Check cache first
        cached_count = cache.get(cache_key)
        if cached_count is not None:
            return cached_count
        
        try:
            response = self._make_request(
                'GET',
                f'/api/vendors/{vendor_id}/products/count/'
            )
            
            data = response.json()
            count = data.get('count', 0)
            
            # Cache for 5 minutes
            cache.set(cache_key, count, 300)
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to get product count for vendor {vendor_id}: {str(e)}")
            # Return 0 as fallback
            return 0
    
    def get_vendor_products(self, vendor_id: int, page: int = 1, page_size: int = 20, 
                           status: str = None) -> Dict[str, Any]:
        """
        Get paginated list of products for a vendor.
        
        Args:
            vendor_id: ID of the vendor
            page: Page number
            page_size: Number of products per page
            status: Filter by product status
            
        Returns:
            Dict containing products and pagination info
        """
        cache_key = f"vendor_products_{vendor_id}_page{page}_size{page_size}_status{status}"
        
        # Check cache first
        cached_products = cache.get(cache_key)
        if cached_products:
            return cached_products
        
        try:
            params = {
                'page': page,
                'page_size': page_size
            }
            if status:
                params['status'] = status
            
            response = self._make_request(
                'GET',
                f'/api/vendors/{vendor_id}/products/',
                params=params
            )
            
            products_data = response.json()
            
            # Cache for 2 minutes (products can change frequently)
            cache.set(cache_key, products_data, 120)
            
            return products_data
            
        except Exception as e:
            logger.error(f"Failed to get products for vendor {vendor_id}: {str(e)}")
            return {
                'results': [],
                'pagination': {
                    'count': 0,
                    'total_pages': 0,
                    'current_page': page
                }
            }
    
    def get_vendor_product_stats(self, vendor_id: int) -> Dict[str, Any]:
        """
        Get product statistics for a vendor.
        
        Args:
            vendor_id: ID of the vendor
            
        Returns:
            Dict containing product statistics
        """
        cache_key = f"vendor_product_stats_{vendor_id}"
        
        # Check cache first
        cached_stats = cache.get(cache_key)
        if cached_stats:
            return cached_stats
        
        try:
            response = self._make_request(
                'GET',
                f'/api/vendors/{vendor_id}/products/stats/'
            )
            
            stats = response.json()
            
            # Cache for 10 minutes
            cache.set(cache_key, stats, 600)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get product stats for vendor {vendor_id}: {str(e)}")
            return {
                'total_products': 0,
                'active_products': 0,
                'inactive_products': 0,
                'out_of_stock': 0,
                'low_stock': 0,
                'total_categories': 0,
                'average_rating': 0.0
            }
    
    def update_vendor_product_count(self, vendor_id: int, delta: int = 1) -> bool:
        """
        Update vendor product count (increment/decrement).
        
        Args:
            vendor_id: ID of the vendor
            delta: Change in product count (positive or negative)
            
        Returns:
            Boolean indicating success
        """
        try:
            response = self._make_request(
                'PATCH',
                f'/api/vendors/{vendor_id}/stats/',
                json={'product_count_delta': delta}
            )
            
            # Invalidate relevant caches
            cache.delete_many([
                f"vendor_product_count_{vendor_id}",
                f"vendor_product_stats_{vendor_id}",
                f"vendor_products_{vendor_id}_page1_size20_statusactive",
                f"vendor_products_{vendor_id}_page1_size20_statusinactive"
            ])
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Failed to update product count for vendor {vendor_id}: {str(e)}")
            return False
    
    def get_product_categories(self, vendor_id: int = None) -> List[Dict[str, Any]]:
        """
        Get product categories, optionally filtered by vendor.
        
        Args:
            vendor_id: Optional vendor ID to filter categories
            
        Returns:
            List of category objects
        """
        cache_key = f"product_categories_{vendor_id if vendor_id else 'all'}"
        
        # Check cache first
        cached_categories = cache.get(cache_key)
        if cached_categories:
            return cached_categories
        
        try:
            params = {}
            if vendor_id:
                params['vendor_id'] = vendor_id
            
            response = self._make_request('GET', '/api/categories/', params=params)
            
            categories = response.json().get('results', [])
            
            # Cache for 1 hour (categories don't change often)
            cache.set(cache_key, categories, 3600)
            
            return categories
            
        except Exception as e:
            logger.error(f"Failed to get product categories: {str(e)}")
            return []
    
    def create_product(self, vendor_id: int, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new product for a vendor.
        
        Args:
            vendor_id: ID of the vendor
            product_data: Product creation data
            
        Returns:
            Dict containing created product information
        """
        try:
            response = self._make_request(
                'POST',
                f'/api/vendors/{vendor_id}/products/',
                json=product_data
            )
            
            created_product = response.json()
            
            # Invalidate relevant caches
            self._invalidate_vendor_caches(vendor_id)
            
            return created_product
            
        except Exception as e:
            logger.error(f"Failed to create product for vendor {vendor_id}: {str(e)}")
            raise ProductServiceError(f"Failed to create product: {str(e)}")
    
    def update_product(self, vendor_id: int, product_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing product.
        
        Args:
            vendor_id: ID of the vendor
            product_id: ID of the product
            update_data: Data to update
            
        Returns:
            Dict containing updated product information
        """
        try:
            response = self._make_request(
                'PATCH',
                f'/api/vendors/{vendor_id}/products/{product_id}/',
                json=update_data
            )
            
            updated_product = response.json()
            
            # Invalidate relevant caches
            self._invalidate_vendor_caches(vendor_id)
            
            return updated_product
            
        except Exception as e:
            logger.error(f"Failed to update product {product_id} for vendor {vendor_id}: {str(e)}")
            raise ProductServiceError(f"Failed to update product: {str(e)}")
    
    def delete_product(self, vendor_id: int, product_id: int) -> bool:
        """
        Delete a product.
        
        Args:
            vendor_id: ID of the vendor
            product_id: ID of the product to delete
            
        Returns:
            Boolean indicating success
        """
        try:
            response = self._make_request(
                'DELETE',
                f'/api/vendors/{vendor_id}/products/{product_id}/'
            )
            
            if response.status_code in [200, 204]:
                # Invalidate relevant caches
                self._invalidate_vendor_caches(vendor_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete product {product_id} for vendor {vendor_id}: {str(e)}")
            raise ProductServiceError(f"Failed to delete product: {str(e)}")
    
    def bulk_update_products(self, vendor_id: int, product_ids: List[int], 
                           update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bulk update multiple products.
        
        Args:
            vendor_id: ID of the vendor
            product_ids: List of product IDs to update
            update_data: Data to update for all products
            
        Returns:
            Dict containing bulk update results
        """
        try:
            response = self._make_request(
                'POST',
                f'/api/vendors/{vendor_id}/products/bulk-update/',
                json={
                    'product_ids': product_ids,
                    'update_data': update_data
                }
            )
            
            result = response.json()
            
            # Invalidate relevant caches
            self._invalidate_vendor_caches(vendor_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to bulk update products for vendor {vendor_id}: {str(e)}")
            raise ProductServiceError(f"Failed to bulk update products: {str(e)}")
    
    def get_low_stock_products(self, vendor_id: int, threshold: int = 10) -> List[Dict[str, Any]]:
        """
        Get products with low stock for a vendor.
        
        Args:
            vendor_id: ID of the vendor
            threshold: Low stock threshold
            
        Returns:
            List of low stock products
        """
        try:
            response = self._make_request(
                'GET',
                f'/api/vendors/{vendor_id}/products/low-stock/',
                params={'threshold': threshold}
            )
            
            return response.json().get('results', [])
            
        except Exception as e:
            logger.error(f"Failed to get low stock products for vendor {vendor_id}: {str(e)}")
            return []
    
    def get_product_analytics(self, vendor_id: int, period: str = '30d') -> Dict[str, Any]:
        """
        Get product analytics for a vendor.
        
        Args:
            vendor_id: ID of the vendor
            period: Analytics period (7d, 30d, 90d, 1y)
            
        Returns:
            Dict containing product analytics
        """
        cache_key = f"product_analytics_{vendor_id}_{period}"
        
        # Check cache first
        cached_analytics = cache.get(cache_key)
        if cached_analytics:
            return cached_analytics
        
        try:
            response = self._make_request(
                'GET',
                f'/api/vendors/{vendor_id}/analytics/products/',
                params={'period': period}
            )
            
            analytics = response.json()
            
            # Cache for 15 minutes
            cache.set(cache_key, analytics, 900)
            
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to get product analytics for vendor {vendor_id}: {str(e)}")
            return {}
    
    def sync_vendor_products(self, vendor_id: int) -> bool:
        """
        Sync vendor products (e.g., after vendor approval or profile update).
        
        Args:
            vendor_id: ID of the vendor
            
        Returns:
            Boolean indicating success
        """
        try:
            response = self._make_request(
                'POST',
                f'/api/vendors/{vendor_id}/sync/'
            )
            
            # Invalidate all vendor-related caches
            self._invalidate_vendor_caches(vendor_id)
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Failed to sync vendor products for vendor {vendor_id}: {str(e)}")
            return False
    
    def _invalidate_vendor_caches(self, vendor_id: int):
        """
        Invalidate all cached data for a vendor.
        
        Args:
            vendor_id: ID of the vendor
        """
        cache_patterns = [
            f"vendor_product_count_{vendor_id}",
            f"vendor_product_stats_{vendor_id}",
            f"vendor_products_{vendor_id}_*",
            f"product_analytics_{vendor_id}_*",
        ]
        
        # Invalidate matching cache keys
        for pattern in cache_patterns:
            cache.delete_pattern(pattern)


class CachedProductClient(ProductClient):
    """
    Extended product client with enhanced caching capabilities.
    """
    
    def __init__(self):
        super().__init__()
        self.cache_ttl = {
            'product_count': 300,  # 5 minutes
            'product_stats': 600,  # 10 minutes
            'vendor_products': 120,  # 2 minutes
            'categories': 3600,  # 1 hour
            'analytics': 900,  # 15 minutes
        }
    
    def get_vendor_product_count_cached(self, vendor_id: int, force_refresh: bool = False) -> int:
        """
        Get vendor product count with cache control.
        
        Args:
            vendor_id: ID of the vendor
            force_refresh: Whether to force refresh from source
            
        Returns:
            Number of products
        """
        cache_key = f"vendor_product_count_{vendor_id}"
        
        if not force_refresh:
            cached_count = cache.get(cache_key)
            if cached_count is not None:
                return cached_count
        
        count = self.get_vendor_product_count(vendor_id)
        cache.set(cache_key, count, self.cache_ttl['product_count'])
        return count
    
    def batch_get_vendor_product_counts(self, vendor_ids: List[int]) -> Dict[int, int]:
        """
        Get product counts for multiple vendors in batch.
        
        Args:
            vendor_ids: List of vendor IDs
            
        Returns:
            Dict mapping vendor_id to product count
        """
        if not vendor_ids:
            return {}
        
        result = {}
        missing_ids = []
        
        # Check cache first
        for vendor_id in vendor_ids:
            cache_key = f"vendor_product_count_{vendor_id}"
            cached_count = cache.get(cache_key)
            if cached_count is not None:
                result[vendor_id] = cached_count
            else:
                missing_ids.append(vendor_id)
        
        # Fetch missing counts individually (product service might not have batch endpoint)
        for vendor_id in missing_ids:
            try:
                count = self.get_vendor_product_count(vendor_id)
                result[vendor_id] = count
            except Exception as e:
                logger.error(f"Failed to get product count for vendor {vendor_id}: {str(e)}")
                result[vendor_id] = 0
        
        return result


# Singleton instance for easy access
product_client = CachedProductClient()


# Utility functions for common product operations
def update_vendor_product_metrics(vendor_id: int) -> bool:
    """
    Update all product-related metrics for a vendor.
    
    Args:
        vendor_id: ID of the vendor
        
    Returns:
        Boolean indicating success
    """
    try:
        # Get current product count
        product_count = product_client.get_vendor_product_count(vendor_id)
        
        # Update vendor model (this would be called from vendor service)
        from apps.vendors.models import Vendor
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            vendor.total_products = product_count
            vendor.save()
            return True
        except Vendor.DoesNotExist:
            logger.error(f"Vendor {vendor_id} not found when updating product metrics")
            return False
            
    except Exception as e:
        logger.error(f"Failed to update product metrics for vendor {vendor_id}: {str(e)}")
        return False


def get_vendor_product_summary(vendor_id: int) -> Dict[str, Any]:
    """
    Get comprehensive product summary for a vendor.
    
    Args:
        vendor_id: ID of the vendor
        
    Returns:
        Dict containing product summary
    """
    try:
        stats = product_client.get_vendor_product_stats(vendor_id)
        analytics = product_client.get_product_analytics(vendor_id, '30d')
        low_stock = product_client.get_low_stock_products(vendor_id)
        
        return {
            'stats': stats,
            'analytics': analytics,
            'low_stock_products': low_stock,
            'total_products': stats.get('total_products', 0),
            'active_products': stats.get('active_products', 0),
            'needs_attention': len(low_stock) > 0
        }
    except Exception as e:
        logger.error(f"Failed to get product summary for vendor {vendor_id}: {str(e)}")
        return {
            'stats': {},
            'analytics': {},
            'low_stock_products': [],
            'total_products': 0,
            'active_products': 0,
            'needs_attention': False
        }