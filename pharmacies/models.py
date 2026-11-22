from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from accounts.validators import validate_phone_number

class Pharmacy(models.Model):
    # Review N18: explicit approval status. `is_approved` is kept in sync
    # (True only when APPROVED) so existing public filters keep working.
    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REVOKED = 'REVOKED'
    APPROVAL_STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REVOKED, 'Revoked'),
    )
    # Review known #5: changing any of these sends an approved pharmacy back to PENDING.
    SENSITIVE_FIELDS = ('pharmacy_name', 'address', 'city', 'pincode', 'latitude', 'longitude')

    # Review N11: one owner manages exactly one pharmacy.
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pharmacy'
    )
    pharmacy_name = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Pharmacy Name"
    )
    registration_number = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name="Registration / License Number"
    )
    address = models.TextField(verbose_name="Street Address")
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20, db_index=True)
    phone_number = models.CharField(max_length=20, validators=[validate_phone_number])
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text="Latitude coordinate for map display (-90 to 90)"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text="Longitude coordinate for map display (-180 to 180)"
    )
    is_approved = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Admin Approval Status"
    )
    approval_status = models.CharField(
        max_length=10,
        choices=APPROVAL_STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        verbose_name="Approval Workflow Status"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pharmacy"
        verbose_name_plural = "Pharmacies"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_approved', 'city'], name='pharm_appr_city_idx'),
            models.Index(fields=['is_approved', 'pincode'], name='pharm_appr_pincode_idx'),
            models.Index(fields=['is_approved', '-created_at'], name='pharm_appr_created_idx'),
        ]

    # Snapshot of the approval fields as last loaded/saved. New objects start
    # from the field defaults; from_db() records the stored values.
    _loaded_approval = (False, STATUS_PENDING)

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        # __dict__ lookup avoids an extra query if a field was deferred.
        instance._loaded_approval = (
            instance.__dict__.get('is_approved'), instance.__dict__.get('approval_status')
        )
        return instance

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self._loaded_approval = (self.__dict__.get('is_approved'), self.__dict__.get('approval_status'))

    def _sync_approval_fields(self):
        """Keeps is_approved and approval_status consistent whichever one was changed."""
        loaded_is_approved, loaded_status = self._loaded_approval
        if self.approval_status != loaded_status:
            self.is_approved = self.approval_status == self.STATUS_APPROVED
        elif self.is_approved != loaded_is_approved:
            if self.is_approved:
                self.approval_status = self.STATUS_APPROVED
            elif loaded_status == self.STATUS_APPROVED:
                self.approval_status = self.STATUS_REVOKED
            else:
                self.approval_status = self.STATUS_PENDING
        else:
            self.is_approved = self.approval_status == self.STATUS_APPROVED

    def save(self, *args, **kwargs):
        self._sync_approval_fields()
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and ({'is_approved', 'approval_status'} & set(update_fields)):
            kwargs['update_fields'] = set(update_fields) | {'is_approved', 'approval_status'}
        super().save(*args, **kwargs)
        self._loaded_approval = (self.is_approved, self.approval_status)

    @property
    def is_revoked(self):
        return self.approval_status == self.STATUS_REVOKED

    @property
    def is_pending(self):
        return self.approval_status == self.STATUS_PENDING

    def __str__(self):
        return f"{self.pharmacy_name} - {self.city} ({self.get_approval_status_display()})"
