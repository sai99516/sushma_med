from django.contrib import admin
from .models import Pharmacy, PharmacyApprovalLog
from .services import set_pharmacy_approval


class PharmacyApprovalLogInline(admin.TabularInline):
    """F5: read-only approval history on the pharmacy page."""
    model = PharmacyApprovalLog
    fields = ('created_at', 'from_status', 'to_status', 'changed_by', 'reason')
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    inlines = [PharmacyApprovalLogInline]
    list_display = ('pharmacy_name', 'registration_number', 'city', 'state', 'phone_number', 'approval_status', 'created_at')
    list_filter = ('approval_status', 'city', 'state')
    search_fields = ('pharmacy_name', 'registration_number', 'city', 'pincode', 'phone_number')
    # Approval is changed only through the actions below (same service as the
    # portal, so owners get notifications and revoked requests are cancelled).
    readonly_fields = ('is_approved', 'approval_status')
    actions = ['approve_pharmacies', 'revoke_approval']

    def _apply(self, request, queryset, approve):
        changed = 0
        for pk in queryset.values_list('pk', flat=True):
            _, did_change, _ = set_pharmacy_approval(pk, approve, request.user)
            changed += int(did_change)
        return changed

    @admin.action(description="Approve selected pharmacies")
    def approve_pharmacies(self, request, queryset):
        count = self._apply(request, queryset, True)
        self.message_user(request, f"Approved {count} pharmacies (owners notified).")

    @admin.action(description="Revoke approval for selected pharmacies")
    def revoke_approval(self, request, queryset):
        count = self._apply(request, queryset, False)
        self.message_user(request, f"Revoked approval for {count} pharmacies (owners and affected customers notified).")
