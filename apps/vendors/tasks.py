import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
import requests

from .models import Vendor, VendorDocument, VendorAnalytics, VendorSettings
from apps.payouts.models import Payout, PayoutSchedule, VendorBalance
from shared.clients.auth_client import AuthClient
from shared.clients.product_client import ProductClient
from shared.exceptions import CustomException

logger = logging.getLogger(__name__)


# Email Notification Tasks
@shared_task(bind=True, max_retries=3)
def send_vendor_welcome_email(self, vendor_id):
    """
    Send welcome email to new vendor after registration.
    """
    try:
        vendor = Vendor.objects.get(id=vendor_id)
        
        subject = f"Welcome to {settings.PLATFORM_NAME} Vendor Program!"
        context = {
            'vendor': vendor,
            'platform_name': settings.PLATFORM_NAME,
            'support_email': settings.SUPPORT_EMAIL,
        }
        
        html_message = render_to_string('emails/vendor_welcome.html', context)
        plain_message = render_to_string('emails/vendor_welcome.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[vendor.contact_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Welcome email sent to vendor {vendor.business_name}")
        
    except Vendor.DoesNotExist:
        logger.error(f"Vendor with id {vendor_id} not found for welcome email")
        raise self.retry(countdown=60, exc=CustomException("Vendor not found"))
    except Exception as e:
        logger.error(f"Failed to send welcome email to vendor {vendor_id}: {str(e)}")
        raise self.retry(countdown=60 * self.request.retries)


@shared_task(bind=True, max_retries=3)
def send_vendor_approval_email(self, vendor_id):
    """
    Send approval notification email to vendor.
    """
    try:
        vendor = Vendor.objects.get(id=vendor_id)
        
        subject = f"Your {settings.PLATFORM_NAME} Vendor Account Has Been Approved!"
        context = {
            'vendor': vendor,
            'platform_name': settings.PLATFORM_NAME,
            'dashboard_url': f"{settings.FRONTEND_URL}/vendor/dashboard",
        }
        
        html_message = render_to_string('emails/vendor_approval.html', context)
        plain_message = render_to_string('emails/vendor_approval.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[vendor.contact_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Approval email sent to vendor {vendor.business_name}")
        
    except Vendor.DoesNotExist:
        logger.error(f"Vendor with id {vendor_id} not found for approval email")
        raise self.retry(countdown=60)
    except Exception as e:
        logger.error(f"Failed to send approval email to vendor {vendor_id}: {str(e)}")
        raise self.retry(countdown=60 * self.request.retries)


@shared_task(bind=True, max_retries=3)
def send_vendor_rejection_email(self, vendor_id):
    """
    Send rejection notification email to vendor with reason.
    """
    try:
        vendor = Vendor.objects.get(id=vendor_id)
        
        subject = f"Update on Your {settings.PLATFORM_NAME} Vendor Application"
        context = {
            'vendor': vendor,
            'platform_name': settings.PLATFORM_NAME,
            'rejection_reason': vendor.rejection_reason,
            'support_email': settings.SUPPORT_EMAIL,
        }
        
        html_message = render_to_string('emails/vendor_rejection.html', context)
        plain_message = render_to_string('emails/vendor_rejection.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[vendor.contact_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Rejection email sent to vendor {vendor.business_name}")
        
    except Vendor.DoesNotExist:
        logger.error(f"Vendor with id {vendor_id} not found for rejection email")
        raise self.retry(countdown=60)
    except Exception as e:
        logger.error(f"Failed to send rejection email to vendor {vendor_id}: {str(e)}")
        raise self.retry(countdown=60 * self.request.retries)


@shared_task(bind=True, max_retries=3)
def send_vendor_suspension_email(self, vendor_id, suspension_reason):
    """
    Send suspension notification email to vendor.
    """
    try:
        vendor = Vendor.objects.get(id=vendor_id)
        
        subject = f"Important: Your {settings.PLATFORM_NAME} Vendor Account Has Been Suspended"
        context = {
            'vendor': vendor,
            'platform_name': settings.PLATFORM_NAME,
            'suspension_reason': suspension_reason,
            'support_email': settings.SUPPORT_EMAIL,
        }
        
        html_message = render_to_string('emails/vendor_suspension.html', context)
        plain_message = render_to_string('emails/vendor_suspension.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[vendor.contact_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Suspension email sent to vendor {vendor.business_name}")
        
    except Vendor.DoesNotExist:
        logger.error(f"Vendor with id {vendor_id} not found for suspension email")
        raise self.retry(countdown=60)
    except Exception as e:
        logger.error(f"Failed to send suspension email to vendor {vendor_id}: {str(e)}")
        raise self.retry(countdown=60 * self.request.retries)


@shared_task(bind=True, max_retries=3)
def send_payout_processed_email(self, payout_id):
    """
    Send notification email when payout is processed.
    """
    try:
        payout = Payout.objects.select_related('vendor').get(id=payout_id)
        
        subject = f"Your Payout Has Been Processed - {payout.reference_number}"
        context = {
            'payout': payout,
            'vendor': payout.vendor,
            'platform_name': settings.PLATFORM_NAME,
        }
        
        html_message = render_to_string('emails/payout_processed.html', context)
        plain_message = render_to_string('emails/payout_processed.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payout.vendor.contact_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Payout processed email sent for payout {payout.reference_number}")
        
    except Payout.DoesNotExist:
        logger.error(f"Payout with id {payout_id} not found")
        raise self.retry(countdown=60)
    except Exception as e:
        logger.error(f"Failed to send payout processed email for payout {payout_id}: {str(e)}")
        raise self.retry(countdown=60 * self.request.retries)


@shared_task(bind=True, max_retries=3)
def send_payout_failed_email(self, payout_id, failure_reason):
    """
    Send notification email when payout fails.
    """
    try:
        payout = Payout.objects.select_related('vendor').get(id=payout_id)
        
        subject = f"Payout Failed - {payout.reference_number}"
        context = {
            'payout': payout,
            'vendor': payout.vendor,
            'failure_reason': failure_reason,
            'platform_name': settings.PLATFORM_NAME,
            'support_email': settings.SUPPORT_EMAIL,
        }
        
        html_message = render_to_string('emails/payout_failed.html', context)
        plain_message = render_to_string('emails/payout_failed.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payout.vendor.contact_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Payout failed email sent for payout {payout.reference_number}")
        
    except Payout.DoesNotExist:
        logger.error(f"Payout with id {payout_id} not found")
        raise self.retry(countdown=60)
    except Exception as e:
        logger.error(f"Failed to send payout failed email for payout {payout_id}: {str(e)}")
        raise self.retry(countdown=60 * self.request.retries)


# Document Processing Tasks
@shared_task(bind=True, max_retries=3)
def process_vendor_document(self, document_id):
    """
    Process uploaded vendor document (virus scan, validation, etc.).
    """
    try:
        document = VendorDocument.objects.select_related('vendor').get(id=document_id)
        
        # Simulate document processing
        logger.info(f"Processing document {document.document_name} for vendor {document.vendor.business_name}")
        
        # TODO: Implement actual document processing logic:
        # 1. Virus scanning
        # 2. File type validation
        # 3. Content extraction
        # 4. Automated verification checks
        
        # For now, mark as processed (in real implementation, this would be conditional)
        document.is_verified = True
        document.verified_at = timezone.now()
        document.save()
        
        logger.info(f"Document {document_id} processed successfully")
        
        # Notify admin for manual review if needed
        if document.document_type in ['business_license', 'tax_certificate']:
            notify_admin_document_review.delay(document_id)
        
    except VendorDocument.DoesNotExist:
        logger.error(f"Document with id {document_id} not found")
        raise self.retry(countdown=60)
    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {str(e)}")
        raise self.retry(countdown=60 * self.request.retries)


@shared_task
def notify_admin_document_review(document_id):
    """
    Notify admin team about document that needs manual review.
    """
    try:
        document = VendorDocument.objects.select_related('vendor').get(id=document_id)
        
        subject = f"Document Requires Review - {document.vendor.business_name}"
        context = {
            'document': document,
            'vendor': document.vendor,
            'admin_url': f"{settings.ADMIN_URL}/admin/vendors/vendordocument/{document_id}/change/",
        }
        
        html_message = render_to_string('emails/admin_document_review.html', context)
        plain_message = render_to_string('emails/admin_document_review.txt', context)
        
        # Send to admin team
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_TEAM_EMAIL],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Admin notification sent for document review {document_id}")
        
    except Exception as e:
        logger.error(f"Failed to send admin notification for document {document_id}: {str(e)}")


# Vendor Management Tasks
@shared_task
def auto_approve_vendors():
    """
    Automatically approve vendors that meet certain criteria.
    Runs daily to check for vendors that can be auto-approved.
    """
    try:
        # Criteria for auto-approval
        eligible_vendors = Vendor.objects.filter(
            status=Vendor.VendorStatus.UNDER_REVIEW,
            documents__is_verified=True,
            documents__document_type__in=['id_proof', 'address_proof', 'business_license']
        ).distinct()
        
        auto_approved_count = 0
        
        for vendor in eligible_vendors:
            # Check if vendor has all required documents verified
            required_docs = vendor.documents.filter(
                document_type__in=['id_proof', 'address_proof', 'business_license'],
                is_verified=True
            )
            
            if required_docs.count() >= 3:  # All required documents verified
                vendor.status = Vendor.VendorStatus.APPROVED
                vendor.approved_at = timezone.now()
                vendor.reviewed_by = None  # System auto-approval
                vendor.save()
                
                auto_approved_count += 1
                logger.info(f"Auto-approved vendor: {vendor.business_name}")
                
                # Send approval email
                send_vendor_approval_email.delay(vendor.id)
        
        logger.info(f"Auto-approval process completed. Approved {auto_approved_count} vendors.")
        
    except Exception as e:
        logger.error(f"Error in auto-approve vendors task: {str(e)}")
        raise


@shared_task
def check_incomplete_vendor_applications():
    """
    Check for vendor applications that are incomplete and send reminders.
    Runs weekly.
    """
    try:
        # Find vendors that have been in pending status for more than 7 days
        cutoff_date = timezone.now() - timedelta(days=7)
        incomplete_vendors = Vendor.objects.filter(
            status=Vendor.VendorStatus.PENDING,
            created_at__lte=cutoff_date
        )
        
        for vendor in incomplete_vendors:
            # Check what's missing
            missing_docs = []
            required_doc_types = ['id_proof', 'address_proof', 'business_license']
            
            for doc_type in required_doc_types:
                if not vendor.documents.filter(document_type=doc_type, is_verified=True).exists():
                    missing_docs.append(doc_type)
            
            if missing_docs:
                send_vendor_application_reminder.delay(vendor.id, missing_docs)
        
        logger.info(f"Checked {incomplete_vendors.count()} incomplete vendor applications")
        
    except Exception as e:
        logger.error(f"Error checking incomplete vendor applications: {str(e)}")
        raise


@shared_task(bind=True, max_retries=3)
def send_vendor_application_reminder(self, vendor_id, missing_documents):
    """
    Send reminder email to vendor about incomplete application.
    """
    try:
        vendor = Vendor.objects.get(id=vendor_id)
        
        subject = f"Reminder: Complete Your {settings.PLATFORM_NAME} Vendor Application"
        context = {
            'vendor': vendor,
            'platform_name': settings.PLATFORM_NAME,
            'missing_documents': missing_documents,
            'application_url': f"{settings.FRONTEND_URL}/vendor/onboarding",
        }
        
        html_message = render_to_string('emails/vendor_application_reminder.html', context)
        plain_message = render_to_string('emails/vendor_application_reminder.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[vendor.contact_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Application reminder sent to vendor {vendor.business_name}")
        
    except Vendor.DoesNotExist:
        logger.error(f"Vendor with id {vendor_id} not found for reminder email")
        raise self.retry(countdown=60)
    except Exception as e:
        logger.error(f"Failed to send reminder email to vendor {vendor_id}: {str(e)}")
        raise self.retry(countdown=60 * self.request.retries)


# Analytics and Reporting Tasks
@shared_task
def update_vendor_analytics():
    """
    Update vendor analytics data from various services.
    Runs hourly.
    """
    try:
        vendors = Vendor.objects.filter(status=Vendor.VendorStatus.APPROVED)
        
        for vendor in vendors:
            try:
                # Get product count from product service
                product_count = get_vendor_product_count(vendor.id)
                
                # Get sales data from order service (mock implementation)
                sales_data = get_vendor_sales_data(vendor.id)
                
                # Update vendor analytics
                analytics, created = VendorAnalytics.objects.get_or_create(vendor=vendor)
                
                if product_count is not None:
                    vendor.total_products = product_count
                
                if sales_data:
                    vendor.total_sales = sales_data.get('total_sales', vendor.total_sales)
                    vendor.total_orders = sales_data.get('total_orders', vendor.total_orders)
                    
                    # Update monthly analytics
                    current_month = timezone.now().strftime('%Y-%m')
                    analytics.monthly_sales[current_month] = sales_data.get('monthly_sales', 0)
                    analytics.monthly_orders[current_month] = sales_data.get('monthly_orders', 0)
                
                vendor.save()
                analytics.save()
                
                logger.debug(f"Updated analytics for vendor {vendor.business_name}")
                
            except Exception as e:
                logger.error(f"Error updating analytics for vendor {vendor.id}: {str(e)}")
                continue
        
        logger.info(f"Updated analytics for {vendors.count()} vendors")
        
    except Exception as e:
        logger.error(f"Error in update_vendor_analytics task: {str(e)}")
        raise


@shared_task
def generate_vendor_performance_report():
    """
    Generate weekly performance reports for vendors.
    Runs every Monday.
    """
    try:
        vendors = Vendor.objects.filter(status=Vendor.VendorStatus.APPROVED)
        
        for vendor in vendors:
            try:
                # Generate performance data
                performance_data = calculate_vendor_performance(vendor.id)
                
                # Send report if vendor has email notifications enabled
                settings = getattr(vendor, 'settings', None)
                if settings and settings.email_notifications:
                    send_vendor_performance_report.delay(vendor.id, performance_data)
                
            except Exception as e:
                logger.error(f"Error generating report for vendor {vendor.id}: {str(e)}")
                continue
        
        logger.info(f"Generated performance reports for {vendors.count()} vendors")
        
    except Exception as e:
        logger.error(f"Error in generate_vendor_performance_report task: {str(e)}")
        raise


@shared_task(bind=True, max_retries=3)
def send_vendor_performance_report(self, vendor_id, performance_data):
    """
    Send weekly performance report to vendor.
    """
    try:
        vendor = Vendor.objects.get(id=vendor_id)
        
        subject = f"Weekly Performance Report - {vendor.business_name}"
        context = {
            'vendor': vendor,
            'performance_data': performance_data,
            'platform_name': settings.PLATFORM_NAME,
            'report_period': timezone.now().strftime('%B %d, %Y'),
        }
        
        html_message = render_to_string('emails/vendor_performance_report.html', context)
        plain_message = render_to_string('emails/vendor_performance_report.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[vendor.contact_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Performance report sent to vendor {vendor.business_name}")
        
    except Vendor.DoesNotExist:
        logger.error(f"Vendor with id {vendor_id} not found for performance report")
        raise self.retry(countdown=60)
    except Exception as e:
        logger.error(f"Failed to send performance report to vendor {vendor_id}: {str(e)}")
        raise self.retry(countdown=60 * self.request.retries)


# Payout Processing Tasks
@shared_task
def process_scheduled_payouts():
    """
    Process scheduled payouts for vendors with auto-payout enabled.
    Runs daily.
    """
    try:
        today = timezone.now().date()
        schedules = PayoutSchedule.objects.filter(
            is_active=True,
            auto_process=True,
            next_payout_date__lte=today
        ).select_related('vendor', 'vendor__balance')
        
        processed_count = 0
        
        for schedule in schedules:
            try:
                vendor = schedule.vendor
                balance = vendor.balance
                
                # Check if vendor has sufficient balance
                if balance.available_balance >= schedule.minimum_payout_amount:
                    # Create payout
                    payout = Payout.objects.create(
                        vendor=vendor,
                        payout_account=vendor.payout_accounts.filter(is_primary=True).first(),
                        amount=balance.available_balance,
                        payout_method='bank_transfer',  # Default method
                        currency='USD'
                    )
                    
                    # Process payout (this would integrate with payment processor)
                    process_payout.delay(payout.id)
                    
                    processed_count += 1
                    logger.info(f"Scheduled payout created for vendor {vendor.business_name}")
                
                # Update next payout date based on schedule type
                update_next_payout_date(schedule)
                
            except Exception as e:
                logger.error(f"Error processing scheduled payout for vendor {schedule.vendor.id}: {str(e)}")
                continue
        
        logger.info(f"Processed {processed_count} scheduled payouts")
        
    except Exception as e:
        logger.error(f"Error in process_scheduled_payouts task: {str(e)}")
        raise


@shared_task(bind=True, max_retries=3)
def process_payout(self, payout_id):
    """
    Process individual payout through payment processor.
    """
    try:
        payout = Payout.objects.select_related('vendor', 'payout_account').get(id=payout_id)
        
        # TODO: Integrate with actual payment processor (Stripe, PayPal, etc.)
        # This is a mock implementation
        
        logger.info(f"Processing payout {payout.reference_number} for {payout.vendor.business_name}")
        
        # Simulate processing delay
        import time
        time.sleep(2)
        
        # Mock successful processing
        payout.status = Payout.PayoutStatus.COMPLETED
        payout.processed_at = timezone.now()
        payout.completed_at = timezone.now()
        payout.processor_reference = f"PROC-{payout.reference_number}"
        payout.save()
        
        # Update vendor balance
        balance = payout.vendor.balance
        balance.available_balance -= payout.amount
        balance.total_payouts += payout.amount
        balance.save()
        
        # Send notification
        send_payout_processed_email.delay(payout.id)
        
        logger.info(f"Payout {payout.reference_number} processed successfully")
        
    except Payout.DoesNotExist:
        logger.error(f"Payout with id {payout_id} not found")
        raise self.retry(countdown=60)
    except Exception as e:
        logger.error(f"Failed to process payout {payout_id}: {str(e)}")
        
        # Update payout status to failed
        try:
            payout = Payout.objects.get(id=payout_id)
            payout.status = Payout.PayoutStatus.FAILED
            payout.failure_reason = str(e)
            payout.save()
            
            send_payout_failed_email.delay(payout.id, str(e))
        except Payout.DoesNotExist:
            pass
        
        raise self.retry(countdown=60 * self.request.retries)


@shared_task
def retry_failed_payouts():
    """
    Retry payouts that failed previously.
    Runs hourly.
    """
    try:
        failed_payouts = Payout.objects.filter(
            status=Payout.PayoutStatus.FAILED,
            retry_count__lt=3  # Maximum 3 retries
        )
        
        for payout in failed_payouts:
            payout.retry_count += 1
            payout.status = Payout.PayoutStatus.PENDING
            payout.save()
            
            process_payout.delay(payout.id)
            logger.info(f"Retrying payout {payout.reference_number} (attempt {payout.retry_count})")
        
        logger.info(f"Retried {failed_payouts.count()} failed payouts")
        
    except Exception as e:
        logger.error(f"Error in retry_failed_payouts task: {str(e)}")
        raise


# System Maintenance Tasks
@shared_task
def cleanup_old_documents():
    """
    Clean up old document files that are no longer needed.
    Runs monthly.
    """
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        # Find documents from rejected vendors or older than 1 year
        cutoff_date = timezone.now() - timedelta(days=365)
        
        old_documents = VendorDocument.objects.filter(
            created_at__lte=cutoff_date
        ).exclude(
            vendor__status=Vendor.VendorStatus.APPROVED
        )
        
        deleted_count = 0
        
        for document in old_documents:
            try:
                # Delete file from storage
                if document.document_file:
                    document.document_file.delete(save=False)
                
                # Delete database record
                document.delete()
                deleted_count += 1
                
            except Exception as e:
                logger.error(f"Error deleting document {document.id}: {str(e)}")
                continue
        
        logger.info(f"Cleaned up {deleted_count} old documents")
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_documents task: {str(e)}")
        raise


@shared_task
def sync_vendor_data_with_auth_service():
    """
    Sync vendor data with auth service to ensure consistency.
    Runs daily.
    """
    try:
        auth_client = AuthClient()
        vendors = Vendor.objects.all()
        
        synced_count = 0
        
        for vendor in vendors:
            try:
                # Update vendor profile in auth service
                user_data = {
                    'first_name': vendor.business_name.split()[0] if vendor.business_name else '',
                    'last_name': ' '.join(vendor.business_name.split()[1:]) if vendor.business_name else '',
                    'phone_number': str(vendor.contact_phone),
                    'user_type': 'vendor',
                }
                
                # Call auth service API to update user
                success = auth_client.update_user(vendor.user_id, user_data)
                
                if success:
                    synced_count += 1
                    logger.debug(f"Synced vendor {vendor.business_name} with auth service")
                else:
                    logger.warning(f"Failed to sync vendor {vendor.business_name} with auth service")
                    
            except Exception as e:
                logger.error(f"Error syncing vendor {vendor.id} with auth service: {str(e)}")
                continue
        
        logger.info(f"Synced {synced_count} vendors with auth service")
        
    except Exception as e:
        logger.error(f"Error in sync_vendor_data_with_auth_service task: {str(e)}")
        raise


# Helper Functions
def get_vendor_product_count(vendor_id):
    """
    Get product count for vendor from product service.
    """
    try:
        product_client = ProductClient()
        return product_client.get_vendor_product_count(vendor_id)
    except Exception as e:
        logger.error(f"Error getting product count for vendor {vendor_id}: {str(e)}")
        return None


def get_vendor_sales_data(vendor_id):
    """
    Get sales data for vendor from order service.
    Mock implementation - replace with actual service call.
    """
    try:
        # TODO: Integrate with actual order service
        # This is a mock implementation
        return {
            'total_sales': 0,
            'total_orders': 0,
            'monthly_sales': 0,
            'monthly_orders': 0,
        }
    except Exception as e:
        logger.error(f"Error getting sales data for vendor {vendor_id}: {str(e)}")
        return {}


def calculate_vendor_performance(vendor_id):
    """
    Calculate vendor performance metrics.
    """
    try:
        vendor = Vendor.objects.get(id=vendor_id)
        analytics = getattr(vendor, 'analytics', None)
        
        performance_data = {
            'total_sales': vendor.total_sales,
            'total_orders': vendor.total_orders,
            'total_products': vendor.total_products,
            'rating': vendor.rating,
            'conversion_rate': analytics.conversion_rate if analytics else 0,
            'total_views': analytics.total_views if analytics else 0,
            'total_clicks': analytics.total_clicks if analytics else 0,
        }
        
        return performance_data
        
    except Exception as e:
        logger.error(f"Error calculating performance for vendor {vendor_id}: {str(e)}")
        return {}


def update_next_payout_date(schedule):
    """
    Update next payout date based on schedule type.
    """
    try:
        today = timezone.now().date()
        
        if schedule.schedule_type == PayoutSchedule.ScheduleType.WEEKLY:
            next_date = today + timedelta(days=7)
        elif schedule.schedule_type == PayoutSchedule.ScheduleType.BI_WEEKLY:
            next_date = today + timedelta(days=14)
        elif schedule.schedule_type == PayoutSchedule.ScheduleType.MONTHLY:
            next_date = today + timedelta(days=30)
        else:  # MANUAL
            next_date = None
        
        schedule.next_payout_date = next_date
        schedule.last_processed_at = timezone.now()
        schedule.save()
        
    except Exception as e:
        logger.error(f"Error updating next payout date for schedule {schedule.id}: {str(e)}")
        raise


# Task Schedules (to be added to Celery Beat)
"""
Add this to your Celery Beat schedule in settings.py:

CELERY_BEAT_SCHEDULE = {
    'auto-approve-vendors-daily': {
        'task': 'apps.vendors.tasks.auto_approve_vendors',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'update-vendor-analytics-hourly': {
        'task': 'apps.vendors.tasks.update_vendor_analytics',
        'schedule': crontab(minute=0),  # Hourly
    },
    'process-scheduled-payouts-daily': {
        'task': 'apps.vendors.tasks.process_scheduled_payouts',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
    },
    'retry-failed-payouts-hourly': {
        'task': 'apps.vendors.tasks.retry_failed_payouts',
        'schedule': crontab(minute=30),  # Every hour at 30 minutes
    },
    'check-incomplete-applications-weekly': {
        'task': 'apps.vendors.tasks.check_incomplete_vendor_applications',
        'schedule': crontab(day_of_week=1, hour=9, minute=0),  # Monday at 9 AM
    },
    'generate-performance-reports-weekly': {
        'task': 'apps.vendors.tasks.generate_vendor_performance_report',
        'schedule': crontab(day_of_week=1, hour=8, minute=0),  # Monday at 8 AM
    },
    'sync-vendor-data-daily': {
        'task': 'apps.vendors.tasks.sync_vendor_data_with_auth_service',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'cleanup-old-documents-monthly': {
        'task': 'apps.vendors.tasks.cleanup_old_documents',
        'schedule': crontab(day_of_month=1, hour=4, minute=0),  # 1st of month at 4 AM
    },
}
"""