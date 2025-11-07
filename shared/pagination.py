from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param
from collections import OrderedDict
from django.conf import settings
from django.core.paginator import InvalidPage
from rest_framework.exceptions import NotFound
import math


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination class with customizable page sizes.
    Provides consistent pagination response format across the API.
    """
    page_size = getattr(settings, 'DEFAULT_PAGE_SIZE', 20)
    page_size_query_param = 'page_size'
    max_page_size = getattr(settings, 'MAX_PAGE_SIZE', 100)
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """
        Override to provide consistent pagination response format.
        """
        return Response(OrderedDict([
            ('pagination', OrderedDict([
                ('count', self.page.paginator.count),
                ('next', self.get_next_link()),
                ('previous', self.get_previous_link()),
                ('current_page', self.page.number),
                ('total_pages', self.page.paginator.num_pages),
                ('page_size', self.get_page_size(self.request)),
                ('has_next', self.page.has_next()),
                ('has_previous', self.page.has_previous()),
            ])),
            ('results', data)
        ]))
    
    def get_paginated_response_schema(self, schema):
        """
        Override to provide OpenAPI schema for paginated responses.
        """
        return {
            'type': 'object',
            'properties': {
                'pagination': {
                    'type': 'object',
                    'properties': {
                        'count': {
                            'type': 'integer',
                            'example': 123,
                            'description': 'Total number of items across all pages'
                        },
                        'next': {
                            'type': 'string',
                            'nullable': True,
                            'format': 'uri',
                            'example': 'http://api.example.org/vendors/?page=4',
                            'description': 'URL to the next page of results'
                        },
                        'previous': {
                            'type': 'string',
                            'nullable': True,
                            'format': 'uri',
                            'example': 'http://api.example.org/vendors/?page=2',
                            'description': 'URL to the previous page of results'
                        },
                        'current_page': {
                            'type': 'integer',
                            'example': 3,
                            'description': 'Current page number'
                        },
                        'total_pages': {
                            'type': 'integer',
                            'example': 5,
                            'description': 'Total number of pages'
                        },
                        'page_size': {
                            'type': 'integer',
                            'example': 25,
                            'description': 'Number of items per page'
                        },
                        'has_next': {
                            'type': 'boolean',
                            'example': True,
                            'description': 'Whether there is a next page'
                        },
                        'has_previous': {
                            'type': 'boolean',
                            'example': True,
                            'description': 'Whether there is a previous page'
                        },
                    },
                    'required': ['count', 'next', 'previous', 'current_page', 'total_pages', 'page_size']
                },
                'results': schema,
            },
            'required': ['pagination', 'results']
        }


class LargeResultsSetPagination(PageNumberPagination):
    """
    Pagination class for large result sets.
    Useful for admin interfaces or data exports.
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('pagination', OrderedDict([
                ('count', self.page.paginator.count),
                ('next', self.get_next_link()),
                ('previous', self.get_previous_link()),
                ('current_page', self.page.number),
                ('total_pages', self.page.paginator.num_pages),
                ('page_size', self.get_page_size(self.request)),
                ('has_next', self.page.has_next()),
                ('has_previous', self.page.has_previous()),
            ])),
            ('results', data)
        ]))


class SmallResultsSetPagination(PageNumberPagination):
    """
    Pagination class for small result sets.
    Ideal for mobile applications or dense UI components.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('pagination', OrderedDict([
                ('count', self.page.paginator.count),
                ('next', self.get_next_link()),
                ('previous', self.get_previous_link()),
                ('current_page', self.page.number),
                ('total_pages', self.page.paginator.num_pages),
                ('page_size', self.get_page_size(self.request)),
                ('has_next', self.page.has_next()),
                ('has_previous', self.page.has_previous()),
            ])),
            ('results', data)
        ]))


class VendorPagination(StandardResultsSetPagination):
    """
    Custom pagination optimized for vendor listings.
    Includes vendor-specific metadata in pagination response.
    """
    page_size = 24  # Good for grid layouts (4x6, 3x8, etc.)
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        
        # Add vendor-specific metadata
        if hasattr(self, 'vendor_stats'):
            response.data['pagination']['vendor_stats'] = self.vendor_stats
        
        # Add range information for better UX
        if self.page.paginator.count > 0:
            start_index = self.page.start_index()
            end_index = self.page.end_index()
            response.data['pagination']['range'] = f"{start_index}-{end_index}"
            response.data['pagination']['start_index'] = start_index
            response.data['pagination']['end_index'] = end_index
        
        return response
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Override to capture vendor-specific statistics.
        """
        self.request = request
        
        # Get vendor statistics before pagination
        if hasattr(view, 'get_vendor_statistics'):
            self.vendor_stats = view.get_vendor_statistics(queryset)
        
        return super().paginate_queryset(queryset, request, view)


class AdminVendorPagination(StandardResultsSetPagination):
    """
    Pagination for admin vendor management with additional stats and larger page sizes.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        
        # Add admin-specific metadata
        if hasattr(self, 'summary_stats'):
            response.data['summary'] = self.summary_stats
        
        # Add performance metrics for admin
        if hasattr(self, 'performance_metrics'):
            response.data['pagination']['performance_metrics'] = self.performance_metrics
        
        return response
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Override to capture admin-specific statistics.
        """
        self.request = request
        
        # Calculate summary statistics for admin dashboard
        if hasattr(view, 'get_admin_summary_stats'):
            self.summary_stats = view.get_admin_summary_stats(queryset)
        
        # Calculate performance metrics
        if hasattr(view, 'get_performance_metrics'):
            self.performance_metrics = view.get_performance_metrics(queryset)
        
        return super().paginate_queryset(queryset, request, view)


class CursorPaginationWithCount(CursorPagination):
    """
    Cursor-based pagination that includes total count.
    Use with caution for large datasets as count can be expensive.
    """
    page_size = 20
    ordering = '-created_at'
    cursor_query_param = 'cursor'
    
    def get_paginated_response(self, data):
        """
        Include total count in cursor pagination (use carefully for large datasets).
        """
        return Response(OrderedDict([
            ('pagination', OrderedDict([
                ('next', self.get_next_link()),
                ('previous', self.get_previous_link()),
                ('page_size', self.page_size),
                ('count', getattr(self, 'count', None)),
                ('has_next', bool(self.get_next_link())),
                ('has_previous', bool(self.get_previous_link())),
            ])),
            ('results', data)
        ]))
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Override to calculate total count.
        """
        # Calculate total count (expensive for large datasets)
        self.count = queryset.count()
        return super().paginate_queryset(queryset, request, view)
    
    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'pagination': {
                    'type': 'object',
                    'properties': {
                        'next': {
                            'type': 'string',
                            'nullable': True,
                            'format': 'uri',
                            'example': 'http://api.example.org/vendors/?cursor=cD0yMDIzLTA5LTE0',
                        },
                        'previous': {
                            'type': 'string',
                            'nullable': True,
                            'format': 'uri',
                            'example': 'http://api.example.org/vendors/?cursor=cj0xJnA9MjAyMy0wOS0xMw',
                        },
                        'page_size': {
                            'type': 'integer',
                            'example': 20,
                        },
                        'count': {
                            'type': 'integer',
                            'nullable': True,
                            'example': 123,
                        },
                        'has_next': {
                            'type': 'boolean',
                            'example': True,
                        },
                        'has_previous': {
                            'type': 'boolean',
                            'example': False,
                        },
                    },
                },
                'results': schema,
            },
        }


class DynamicPagination(PageNumberPagination):
    """
    Dynamic pagination that adjusts based on request parameters, user role, and endpoint type.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200
    page_query_param = 'page'
    
    def get_page_size(self, request):
        """
        Override to provide dynamic page sizes based on various factors.
        """
        # Store original max page size
        original_max_page_size = self.max_page_size
        
        try:
            # Adjust based on user role
            if hasattr(request, 'user') and request.user.is_authenticated:
                if request.user.is_admin:
                    self.max_page_size = 500  # Allow larger pages for admins
                elif request.user.is_vendor:
                    self.max_page_size = 100  # Reasonable limit for vendors
            
            # Adjust based on endpoint type
            path = request.path.lower()
            
            if any(keyword in path for keyword in ['export', 'report', 'download']):
                self.max_page_size = 1000  # Larger pages for data exports
            elif any(keyword in path for keyword in ['dashboard', 'analytics']):
                self.max_page_size = 50  # Smaller pages for dashboard data
            elif any(keyword in path for keyword in ['search', 'filter']):
                self.max_page_size = 100  # Moderate pages for search results
            
            # Check for explicit page size in query params
            if self.page_size_query_param in request.query_params:
                try:
                    page_size = int(request.query_params[self.page_size_query_param])
                    if page_size > 0:
                        return min(page_size, self.max_page_size)
                except (ValueError, TypeError):
                    pass
            
            return self.page_size
            
        finally:
            # Restore original max page size to avoid side effects
            self.max_page_size = original_max_page_size
    
    def get_paginated_response(self, data):
        """
        Include additional pagination metadata and range information.
        """
        pagination_data = OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('current_page', self.page.number),
            ('total_pages', self.page.paginator.num_pages),
            ('page_size', self.get_page_size(self.request)),
            ('has_next', self.page.has_next()),
            ('has_previous', self.page.has_previous()),
        ])
        
        # Add range information for better UX
        if self.page.paginator.count > 0:
            start_index = self.page.start_index()
            end_index = self.page.end_index()
            pagination_data['range'] = f"{start_index}-{end_index}"
            pagination_data['start_index'] = start_index
            pagination_data['end_index'] = end_index
        
        # Add page number links for navigation
        pagination_data['page_links'] = self.get_page_links()
        
        return Response(OrderedDict([
            ('pagination', pagination_data),
            ('results', data)
        ]))
    
    def get_page_links(self):
        """
        Generate page number links for better navigation.
        """
        current_page = self.page.number
        total_pages = self.page.paginator.num_pages
        
        if total_pages <= 1:
            return []
        
        # Define the range of pages to show around current page
        delta = 2
        left_bound = max(1, current_page - delta)
        right_bound = min(total_pages, current_page + delta)
        
        page_links = []
        
        # Add first page and ellipsis if needed
        if left_bound > 1:
            page_links.append({'page': 1, 'url': self.get_page_url(1), 'type': 'number'})
            if left_bound > 2:
                page_links.append({'page': '...', 'url': None, 'type': 'ellipsis'})
        
        # Add page numbers in range
        for page in range(left_bound, right_bound + 1):
            page_links.append({
                'page': page,
                'url': self.get_page_url(page),
                'type': 'number',
                'current': page == current_page
            })
        
        # Add last page and ellipsis if needed
        if right_bound < total_pages:
            if right_bound < total_pages - 1:
                page_links.append({'page': '...', 'url': None, 'type': 'ellipsis'})
            page_links.append({
                'page': total_pages,
                'url': self.get_page_url(total_pages),
                'type': 'number'
            })
        
        return page_links
    
    def get_page_url(self, page_number):
        """
        Generate URL for a specific page number.
        """
        if not self.request:
            return None
        
        url = self.request.build_absolute_uri()
        return replace_query_param(url, self.page_query_param, page_number)


class NoPagination(PageNumberPagination):
    """
    Disable pagination for endpoints that require all data.
    Use with caution and only for small datasets.
    """
    page_size = None
    page_size_query_param = None
    max_page_size = None
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Return all results without pagination.
        """
        self.request = request
        self.count = queryset.count()
        return list(queryset)
    
    def get_paginated_response(self, data):
        """
        Return response without pagination metadata.
        """
        return Response({
            'results': data,
            'pagination': {
                'count': self.count,
                'page_size': 'all',
                'warning': 'This endpoint returns all records without pagination. Use with caution for large datasets.'
            }
        })
    
    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'results': schema,
                'pagination': {
                    'type': 'object',
                    'properties': {
                        'count': {
                            'type': 'integer',
                            'example': 45
                        },
                        'page_size': {
                            'type': 'string',
                            'example': 'all'
                        },
                        'warning': {
                            'type': 'string',
                            'example': 'This endpoint returns all records without pagination. Use with caution for large datasets.'
                        }
                    }
                }
            }
        }


class OptimizedVendorPagination(PageNumberPagination):
    """
    Optimized pagination for vendor listings with performance considerations.
    Prefetches related data and provides optimized queries.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    def paginate_queryset(self, queryset, request, view=None):
        """
        Override to optimize queryset with select_related and prefetch_related.
        """
        # Optimize the queryset for vendor listings
        if hasattr(queryset.model, 'vendor_optimized_queryset'):
            queryset = queryset.model.vendor_optimized_queryset()
        else:
            # Default optimizations for vendor models
            queryset = queryset.select_related('analytics').prefetch_related('documents')
        
        return super().paginate_queryset(queryset, request, view)
    
    def get_paginated_response(self, data):
        """
        Include performance metrics in response.
        """
        response = super().get_paginated_response(data)
        
        # Add performance information
        import time
        if hasattr(self, 'start_time'):
            response.data['pagination']['response_time'] = time.time() - self.start_time
        
        return response


class PaginationMixin:
    """
    Mixin to easily configure pagination per view.
    Provides flexible pagination configuration and utilities.
    """
    pagination_class = StandardResultsSetPagination
    pagination_config = {}
    
    @classmethod
    def get_pagination_class(cls):
        """
        Get the appropriate pagination class based on view configuration.
        """
        return cls.pagination_class
    
    def get_paginator(self):
        """
        Get paginator instance with request context.
        """
        pagination_class = self.get_pagination_class()
        paginator = pagination_class()
        
        # Apply pagination configuration
        for key, value in self.pagination_config.items():
            if hasattr(paginator, key):
                setattr(paginator, key, value)
        
        paginator.request = self.request
        return paginator
    
    def get_pagination_config(self):
        """
        Override to provide dynamic pagination configuration.
        """
        return self.pagination_config.copy()
    
    def paginate_queryset(self, queryset):
        """
        Paginate a queryset using the view's paginator.
        """
        paginator = self.get_paginator()
        page = paginator.paginate_queryset(queryset, self.request, view=self)
        return page, paginator


def paginate_queryset(queryset, request, pagination_class=StandardResultsSetPagination, **kwargs):
    """
    Utility function to paginate a queryset outside of view context.
    
    Args:
        queryset: Django queryset to paginate
        request: HTTP request object
        pagination_class: Pagination class to use
        **kwargs: Additional arguments to pass to paginator
    
    Returns:
        tuple: (paginated_queryset, paginator_instance)
    """
    paginator = pagination_class()
    
    # Apply any additional configuration
    for key, value in kwargs.items():
        if hasattr(paginator, key):
            setattr(paginator, key, value)
    
    paginator.request = request
    page = paginator.paginate_queryset(queryset, request)
    return page, paginator


def get_paginated_response(data, paginator, **additional_data):
    """
    Utility function to get paginated response with additional data.
    
    Args:
        data: Serialized data
        paginator: Paginator instance
        **additional_data: Additional data to include in response
    
    Returns:
        Response: DRF Response object with pagination
    """
    response = paginator.get_paginated_response(data)
    
    # Add additional data to response
    if additional_data:
        for key, value in additional_data.items():
            response.data[key] = value
    
    return response


class PaginationConfig:
    """
    Configuration class for pagination settings across the application.
    Provides centralized configuration management for pagination.
    """
    # Default pagination classes for different use cases
    STANDARD = StandardResultsSetPagination
    LARGE = LargeResultsSetPagination
    SMALL = SmallResultsSetPagination
    VENDOR = VendorPagination
    ADMIN_VENDOR = AdminVendorPagination
    CURSOR = CursorPaginationWithCount
    DYNAMIC = DynamicPagination
    OPTIMIZED = OptimizedVendorPagination
    NONE = NoPagination
    
    # Page size mappings
    PAGE_SIZES = {
        'xs': 5,      # Extra small - for dense mobile UIs
        'small': 10,   # Small - for mobile applications
        'standard': 20, # Standard - default for most endpoints
        'large': 50,   # Large - for desktop applications
        'xl': 100,     # Extra large - for admin interfaces
        'xxl': 200,    # Double extra large - for data exports
    }
    
    # Endpoint to pagination class mapping
    ENDPOINT_PAGINATION = {
        'vendor_list': VENDOR,
        'vendor_search': DYNAMIC,
        'admin_vendors': ADMIN_VENDOR,
        'vendor_products': STANDARD,
        'vendor_orders': STANDARD,
        'vendor_analytics': SMALL,
        'vendor_payouts': STANDARD,
        'public_vendors': VENDOR,
    }
    
    @classmethod
    def get_pagination_class(cls, pagination_type='standard', endpoint=None):
        """
        Get pagination class by type name or endpoint.
        
        Args:
            pagination_type: Type of pagination ('standard', 'large', 'small', 'vendor', 'admin', 'cursor', 'dynamic', 'none')
            endpoint: Specific endpoint name to get configured pagination
        
        Returns:
            Pagination class
        """
        if endpoint and endpoint in cls.ENDPOINT_PAGINATION:
            return cls.ENDPOINT_PAGINATION[endpoint]
        
        pagination_map = {
            'standard': cls.STANDARD,
            'large': cls.LARGE,
            'small': cls.SMALL,
            'vendor': cls.VENDOR,
            'admin': cls.ADMIN_VENDOR,
            'cursor': cls.CURSOR,
            'dynamic': cls.DYNAMIC,
            'optimized': cls.OPTIMIZED,
            'none': cls.NONE,
        }
        return pagination_map.get(pagination_type, cls.STANDARD)
    
    @classmethod
    def get_page_size(cls, size_name='standard'):
        """
        Get page size by name.
        
        Args:
            size_name: Name of page size ('xs', 'small', 'standard', 'large', 'xl', 'xxl')
        
        Returns:
            int: Page size
        """
        return cls.PAGE_SIZES.get(size_name, cls.PAGE_SIZES['standard'])
    
    @classmethod
    def configure_paginator(cls, paginator, **config):
        """
        Configure a paginator instance with given configuration.
        
        Args:
            paginator: Paginator instance
            **config: Configuration parameters
        
        Returns:
            Configured paginator instance
        """
        for key, value in config.items():
            if hasattr(paginator, key):
                setattr(paginator, key, value)
        return paginator


# Example usage in settings.py:
"""
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'shared.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    
    # Or use dynamic configuration:
    'DEFAULT_PAGINATION_CLASS': 'shared.pagination.DynamicPagination',
    
    # Configure maximum page size
    'MAX_PAGE_SIZE': 100,
}
"""

# Example usage in views:
"""
from shared.pagination import PaginationConfig, PaginationMixin

class VendorListView(PaginationMixin, generics.ListAPIView):
    pagination_class = PaginationConfig.VENDOR
    # or
    pagination_class = PaginationConfig.get_pagination_class('vendor')
    # or by endpoint
    pagination_class = PaginationConfig.get_pagination_class(endpoint='vendor_list')
    
    def get_pagination_config(self):
        config = super().get_pagination_config()
        # Dynamically adjust based on request
        if self.request.user.is_admin:
            config['page_size'] = 50
        return config

class AdminVendorListView(PaginationMixin, generics.ListAPIView):
    pagination_class = PaginationConfig.ADMIN_VENDOR

class ExportVendorView(PaginationMixin, generics.ListAPIView):
    pagination_class = PaginationConfig.NONE  # No pagination for exports
"""

# Utility function examples:
"""
from shared.pagination import paginate_queryset, get_paginated_response

def custom_vendor_list(request):
    queryset = Vendor.objects.filter(status='approved')
    
    # Paginate the queryset
    paginated_queryset, paginator = paginate_queryset(
        queryset, 
        request, 
        PaginationConfig.VENDOR,
        page_size=24
    )
    
    serializer = VendorSerializer(paginated_queryset, many=True)
    
    # Get paginated response with additional data
    return get_paginated_response(
        serializer.data,
        paginator,
        summary_stats=get_summary_stats(queryset)
    )
"""

# Context processor for template views (if needed):
"""
def pagination_context(request):
    return {
        'default_page_size': PaginationConfig.get_page_size('standard'),
        'max_page_size': getattr(settings, 'MAX_PAGE_SIZE', 100),
    }
"""