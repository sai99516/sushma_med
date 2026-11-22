from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from medicines.models import Medicine
from pharmacies.models import Pharmacy

class Inventory(models.Model):
    STATUS_CHOICES = (
        ('IN_STOCK', 'In Stock'),
        ('LOW_STOCK', 'Low Stock (1–10 units)'),
        ('OUT_OF_STOCK', 'Out of Stock'),
    )

    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name='inventories'
    )
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name='pharmacy_inventories'
    )
    quantity = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0, message="Stock quantity cannot be negative.")]
    )
    availability_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='OUT_OF_STOCK',
        db_index=True
    )
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"
        unique_together = ('pharmacy', 'medicine')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['pharmacy', 'availability_status'], name='inv_pharm_status_idx'),
            models.Index(fields=['pharmacy', '-updated_at'], name='inv_pharm_updated_idx'),
            models.Index(fields=['availability_status', '-updated_at'], name='inv_status_updated_idx'),
        ]

    def clean(self):
        super().clean()
        if self.quantity is not None and self.quantity < 0:
            raise ValidationError({'quantity': "Stock quantity cannot be negative."})

    def save(self, *args, **kwargs):
        # Auto-compute status on save
        if self.quantity > 10:
            self.availability_status = 'IN_STOCK'
        elif self.quantity > 0:
            self.availability_status = 'LOW_STOCK'
        else:
            self.availability_status = 'OUT_OF_STOCK'
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicine.medicine_name} at {self.pharmacy.pharmacy_name}: {self.quantity} ({self.get_availability_status_display()})"

    # Review N20: ONE freshness rule used everywhere (public pages, pharmacy
    # pages, map pins). Up to 24h = FRESH; 24-48h = MODERATE; over 48h = STALE.
    # Anything older than 24h is "stale" in the sense that customers should
    # confirm with the pharmacy before visiting.
    FRESH_HOURS = 24
    STALE_HOURS = 48

    @property
    def freshness_tier(self):
        import datetime
        from django.utils import timezone
        if not self.updated_at:
            return 'STALE'
        elapsed = timezone.now() - self.updated_at
        if elapsed <= datetime.timedelta(hours=self.FRESH_HOURS):
            return 'FRESH'
        elif elapsed <= datetime.timedelta(hours=self.STALE_HOURS):
            return 'MODERATE'
        return 'STALE'

    @property
    def is_stale(self):
        """True when the last pharmacy report is older than 24 hours (same rule as freshness_tier)."""
        return self.freshness_tier != 'FRESH'

    @property
    def freshness_label(self):
        """Pharmacy-reported wording (review known #4): never claims live or verified stock."""
        tier = self.freshness_tier
        if tier == 'FRESH':
            return 'Pharmacy-reported · updated within 24h'
        elif tier == 'MODERATE':
            return 'Pharmacy-reported · updated 24–48h ago · confirm before visiting'
        return 'Pharmacy-reported · updated over 48h ago · confirm before visiting'
