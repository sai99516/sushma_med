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
            'quantity_requested': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'value': '1',
                'placeholder': 'Number of units needed'
            }),
            'request_message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional note (e.g., urgency, when you plan to pick it up, specific brand requirement)'
            }),
        }

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
            ('UNAVAILABLE', 'Report Medicine Unavailable / Out of Stock'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Update Availability Status"
    )

    class Meta:
        model = AvailabilityRequest
        fields = ['status', 'pharmacy_response']
        widgets = {
            'pharmacy_response': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter message for customer (e.g., Held at front counter until 7 PM, or Expecting fresh delivery tomorrow)'
            }),
        }

    def clean_pharmacy_response(self):
        return _limit_length(self.cleaned_data.get('pharmacy_response', ''))
