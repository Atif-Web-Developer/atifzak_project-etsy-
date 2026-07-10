from django import forms
from .models import Supplier, Category, Country, State


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'link', 'category', 'country', 'state']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter supplier name',
                'id': 'id_name',
            }),
            'link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://supplier-website.com',
                'id': 'id_link',
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_category',
            }),
            'country': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_country',
            }),
            'state': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_state',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.all()
        self.fields['category'].empty_label = '-- Select Category --'
        self.fields['country'].queryset = Country.objects.all()
        self.fields['country'].empty_label = '-- Select Country --'
        # State starts empty; AJAX will populate it
        self.fields['state'].queryset = State.objects.none()
        self.fields['state'].empty_label = '-- Select State --'
        self.fields['state'].required = False

        # On edit (instance exists), load states for the selected country
        if 'country' in self.data:
            try:
                country_id = int(self.data.get('country'))
                self.fields['state'].queryset = State.objects.filter(country_id=country_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.country:
            self.fields['state'].queryset = State.objects.filter(country=self.instance.country)
