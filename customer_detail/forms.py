from django import forms
from .models import Customer


class CustomerForm(forms.ModelForm):
    """Form for creating and updating customer records."""

    class Meta:
        model = Customer
        fields = ['full_name', 'phone_number', 'email', 'company_name', 'address', 'notes']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter full name',
                'id': 'id_full_name',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number',
                'id': 'id_phone_number',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address',
                'id': 'id_email',
            }),
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter company name',
                'id': 'id_company_name',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Enter address',
                'rows': 3,
                'id': 'id_address',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Enter notes',
                'rows': 3,
                'id': 'id_notes',
            }),
        }
