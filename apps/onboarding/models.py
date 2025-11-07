from django.db import models
from django.utils.translation import gettext_lazy as _
from datetime import timedelta, timezone

class OnboardingStep(models.Model):
    class StepType(models.TextChoices):
        FORM = 'form', _('Form')
        DOCUMENT_UPLOAD = 'document_upload', _('Document Upload')
        VERIFICATION = 'verification', _('Verification')
        AGREEMENT = 'agreement', _('Agreement')
    
    name = models.CharField(max_length=255)
    step_type = models.CharField(max_length=50, choices=StepType.choices)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    # Configuration for different step types
    form_config = models.JSONField(default=dict, blank=True)  # For form steps
    document_types = models.JSONField(default=list, blank=True)  # For document upload steps
    agreement_text = models.TextField(blank=True, null=True)  # For agreement steps
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'onboarding_steps'
        verbose_name = 'Onboarding Step'
        verbose_name_plural = 'Onboarding Steps'
        ordering = ['order']
    
    def __str__(self):
        return f"{self.order}. {self.name}"


class VendorOnboarding(models.Model):
    class OnboardingStatus(models.TextChoices):
        NOT_STARTED = 'not_started', _('Not Started')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
    
    vendor = models.OneToOneField(
        'vendors.Vendor',
        on_delete=models.CASCADE,
        related_name='onboarding'
    )
    status = models.CharField(
        max_length=20,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.NOT_STARTED
    )
    current_step = models.ForeignKey(
        OnboardingStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    completed_steps = models.ManyToManyField(
        OnboardingStep,
        related_name='completed_onboardings',
        blank=True
    )
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vendor_onboardings'
        verbose_name = 'Vendor Onboarding'
        verbose_name_plural = 'Vendor Onboardings'
    
    def __str__(self):
        return f"Onboarding - {self.vendor.business_name}"
    
    def update_progress(self):
        total_steps = OnboardingStep.objects.filter(is_active=True, is_required=True).count()
        completed_steps = self.completed_steps.filter(is_required=True).count()
        
        if total_steps > 0:
            self.progress_percentage = (completed_steps / total_steps) * 100
        
        # Update status
        if completed_steps == total_steps:
            self.status = self.OnboardingStatus.COMPLETED
            self.completed_at = timezone.now()
        elif completed_steps > 0:
            self.status = self.OnboardingStatus.IN_PROGRESS
        else:
            self.status = self.OnboardingStatus.NOT_STARTED
        
        self.save()


class OnboardingStepCompletion(models.Model):
    onboarding = models.ForeignKey(
        VendorOnboarding,
        on_delete=models.CASCADE,
        related_name='step_completions'
    )
    step = models.ForeignKey(OnboardingStep, on_delete=models.CASCADE)
    completed_data = models.JSONField(default=dict, blank=True)  # Store step-specific data
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'onboarding_step_completions'
        verbose_name = 'Onboarding Step Completion'
        verbose_name_plural = 'Onboarding Step Completions'
        unique_together = ['onboarding', 'step']
    
    def __str__(self):
        status = "Completed" if self.is_completed else "Pending"
        return f"{self.onboarding.vendor.business_name} - {self.step.name} ({status})"