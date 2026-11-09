import re

from django import forms

from accounts.forms import StyledFormMixin

from . import rules
from .models import MARKETS, Hunt, StockSettings

# Ma'am's "Product selection" columns (Sr. No is given automatically) + the competitor rows.
HUNT_FIELDS = ['main_keyword', 'sales_trend', 'two_sellers_100', 'avg_price', 'market', 'total_sellers',
               'seller_listing_link', 'competitors']


class HuntForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Hunt
        fields = HUNT_FIELDS
        widgets = {
            'competitors': forms.HiddenInput(),
            'main_keyword': forms.TextInput(attrs={'placeholder': 'e.g. Soft TPR Toy'}),
            'seller_listing_link': forms.URLInput(attrs={'placeholder': 'https://www.ebay…/itm/…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['avg_price'].widget.attrs.update({'step': '0.01', 'min': '0'})
        self.fields['total_sellers'].widget.attrs.update({'min': '0', 'step': '1'})
        self.fields['market'].choices = [(k, f"{m['currency']} {m['code']}") for k, m in MARKETS.items()]
        self.fields['sales_trend'].choices = [('', '—')] + Hunt.TRENDS
        self.fields['two_sellers_100'].choices = [('', '—'), ('Yes', 'Yes'), ('No', 'No')]

    def clean_competitors(self):
        comps = rules.clean_competitors(self.cleaned_data.get('competitors'))
        problems = rules.link_problems(comps)
        if problems:
            raise forms.ValidationError(problems)
        return comps


class RulesForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = StockSettings
        fields = list(StockSettings.RULE_FIELDS)


class ConnectionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = StockSettings
        fields = ['sheet_webapp_url']
        widgets = {'sheet_webapp_url': forms.URLInput(attrs={'placeholder': 'https://script.google.com/macros/s/…/exec'})}

    def clean_sheet_webapp_url(self):
        url = self.cleaned_data['sheet_webapp_url'].strip()
        if url and not re.match(r'^https://script\.google\.com/macros/s/[\w-]+/exec/?$', url):
            raise forms.ValidationError('Paste the Web app URL from Apps Script – it starts with '
                                        'https://script.google.com/macros/s/ and ends with /exec.')
        return url
