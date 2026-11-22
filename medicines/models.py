from django.db import models
from django.db.models.functions import Lower

class Medicine(models.Model):
    CATEGORY_CHOICES = (
        ('Antibiotics', 'Antibiotics'),
        ('Analgesics & Pain Relief', 'Analgesics & Pain Relief'),
        ('Antipyretic', 'Antipyretic (Fever)'),
        ('Antidiabetic', 'Antidiabetic'),
        ('Cardiovascular', 'Cardiovascular (Heart & BP)'),
        ('Respiratory & Anti-Allergic', 'Respiratory & Anti-Allergic'),
        ('Gastrointestinal', 'Gastrointestinal & Antacids'),
        ('Dermatology', 'Dermatology & Skin Care'),
        ('Vitamins & Supplements', 'Vitamins & Supplements'),
        ('Neurology & Psychiatry', 'Neurology & Psychiatry'),
        ('Other', 'Other Healthcare Products'),
    )

    DOSAGE_FORM_CHOICES = (
        ('Tablet', 'Tablet'),
        ('Capsule', 'Capsule'),
        ('Syrup', 'Syrup / Liquid Suspension'),
        ('Injection', 'Injection / Vial'),
        ('Ointment', 'Ointment / Cream / Gel'),
        ('Drops', 'Eye / Ear / Nasal Drops'),
        ('Inhaler', 'Inhaler / Respirator Solution'),
        ('Powder', 'Powder / Granules'),
    )

    medicine_name = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Brand / Medicine Name"
    )
    generic_name = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Generic / Chemical Name"
    )
    strength = models.CharField(
        max_length=100,
        help_text="e.g. 500mg, 10ml, 250mcg, 1g"
    )
    dosage_form = models.CharField(
        max_length=100,
        choices=DOSAGE_FORM_CHOICES,
        default='Tablet',
        db_index=True
    )
    category = models.CharField(
        max_length=100,
        choices=CATEGORY_CHOICES,
        db_index=True,
        default='Other'
    )
    description = models.TextField(blank=True, help_text="Therapeutic purpose or instructions")
    # Archive flag: inactive medicines are hidden from public search and the add-stock form.
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Active (visible in search)",
        help_text="Untick to archive this medicine instead of deleting it."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Medicine"
        verbose_name_plural = "Medicines"
        ordering = ['medicine_name']
        indexes = [
            models.Index(fields=['category', 'medicine_name'], name='med_cat_name_idx'),
            models.Index(fields=['dosage_form', 'category'], name='med_dosage_cat_idx'),
        ]
        # Review N28: no duplicate catalogue entries (case-insensitive name + strength, same form).
        constraints = [
            models.UniqueConstraint(
                Lower('medicine_name'), Lower('strength'), 'dosage_form',
                name='unique_medicine_name_strength_form',
                violation_error_message="A medicine with this name, strength and dosage form already exists.",
            ),
        ]

    def __str__(self):
        return f"{self.medicine_name} ({self.strength}) - {self.dosage_form}"
