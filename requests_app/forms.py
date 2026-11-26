from django import forms
from .models import AvailabilityRequest

# Review P4: upper limits so a customer cannot send absurd quantities or 10,000-character notes.
MAX_REQUEST_QUANTITY = 1000
MAX_MESSAGE_LENGTH = 1000


def _limit_length(value):
    if value and len(value) > MAX_MESSAGE_LENGTH:
        raise forms.ValidationError(f"Please keep the message under {MAX_MESSAGE_LENGTH} characters.")
    return value

class AvailabilityRequestCreateForm(forms.ModelForm):
    class Meta:
        model = AvailabilityRequest
        fields = ['quantity_requested', 'request_message']
        widgets = {
            # min/max are set in __init__; the initial value 1 comes from the model default.
            'quantity_requested': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of units needed'
            }),
            'request_message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional note (e.g., urgency, when you plan to pick it up, specific brand requirement)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Review E2: PositiveIntegerField renders min="0"; let the browser enforce 1..MAX too.
        self.fields['quantity_requested'].widget.attrs.update({'min': '1', 'max': str(MAX_REQUEST_QUANTITY)})

    def clean_quantity_requested(self):
        qty = self.cleaned_data.get('quantity_requested')
        if qty is None or qty < 1:
            raise forms.ValidationError("You must request at least 1 unit.")
        if qty > MAX_REQUEST_QUANTITY:
            raise forms.ValidationError(f"You can request at most {MAX_REQUEST_QUANTITY} units at once.")
        return qty

    def clean_request_message(self):
        return _limit_length(self.cleaned_data.get('request_message', ''))


class PharmacyResponseForm(forms.ModelForm):
    status = forms.ChoiceField(
        choices=[
            ('CONFIRMED', 'Confirm Medicine Available for Pickup'),
            ('PARTIAL', 'Partially Available (only some units)'),
            ('UNAVAILABLE', 'Report Medicine Unavailable / Out of Stock'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Update Availability Status"
    )
    # Manual testing M3: required only when status is PARTIAL.
    available_quantity = forms.IntegerField(
        required=False,
        min_value=1,
        label="Units available",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
    )

    class Meta:
        model = AvailabilityRequest
        fields = ['status', 'available_quantity', 'pharmacy_response']
        widgets = {
            'pharmacy_response': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter message for customer (e.g., Held at front counter until 7 PM, or Expecting fresh delivery tomorrow)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        requested = self.instance.quantity_requested if self.instance and self.instance.pk else None
        if requested:
            self.fields['available_quantity'].widget.attrs['max'] = str(max(requested - 1, 1))
            self.fields['available_quantity'].help_text = f"Between 1 and {requested - 1} of the {requested} requested units."

    def clean_pharmacy_response(self):
        return _limit_length(self.cleaned_data.get('pharmacy_response', ''))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('status') != 'PARTIAL':
            cleaned['available_quantity'] = None
            return cleaned
        qty = cleaned.get('available_quantity')
        requested = self.instance.quantity_requested
        if requested < 2:
            self.add_error('status', "Partial availability is not possible for a request of 1 unit.")
        elif qty is None:
            self.add_error('available_quantity', "Enter how many units are available.")
        elif not (1 <= qty <= requested - 1):
            self.add_error('available_quantity', f"Must be between 1 and {requested - 1}.")
        return cleaned
