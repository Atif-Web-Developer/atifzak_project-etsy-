import re

from django import forms
from django.core.validators import MaxLengthValidator

from accounts.forms import StyledFormMixin

from . import lists
from .columns import STORED_COLUMNS
from .models import DropshipSettings, Product

NEW_TAB = '__new__'
TABLE_FIELDS = lists.TABLE_SOURCE_FIELDS  # single fields filled from the competitor / supplier tables
RESERVED_TABS = {'ebay settings'}


class ProductForm(StyledFormMixin, forms.ModelForm):
    tab_choice = forms.CharField(label='Save into tab', required=False)
    new_tab = forms.CharField(label='New tab name', required=False, max_length=100)

    class Meta:
        model = Product
        fields = [c.key for c in STORED_COLUMNS]
        widgets = {
            'competitor_links': forms.Textarea(attrs={'rows': 3, 'placeholder': 'One link per line'}),
            'supplier_link': forms.URLInput(attrs={'placeholder': 'https://'}),
            'competitors': forms.HiddenInput(),
            'suppliers': forms.HiddenInput(),
            'image_url': forms.URLInput(attrs={'placeholder': 'https://… picture link (the one-click button fills it)'}),
        }

    def __init__(self, *args, tabs=(), blocked_tabs=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.tabs = list(tabs)
        self.blocked_tabs = {t.lower() for t in blocked_tabs}
        for col in STORED_COLUMNS:  # labels come from the column list, so they match the sheet headers
            self.fields[col.key].label = col.header
        for name in ('supplier_cost', 'supplier_shipping', 'other_cost', 'listed_price', 'my_shipping',
                     'seller_price', 'buyer_shipping'):
            self.fields[name].widget.attrs.update({'step': '0.01', 'min': '0', 'inputmode': 'decimal'})
        # The ID box also accepts a whole eBay link (clean_item_id keeps only the ID), so no 20-character limit here.
        item_field = self.fields['item_id']
        item_field.max_length = None
        item_field.validators = [v for v in item_field.validators if not isinstance(v, MaxLengthValidator)]
        item_field.widget.attrs.pop('maxlength', None)
        item_field.widget.attrs.update({'placeholder': 'e.g. 147123049946 or paste the eBay link'})
        self.fields['other_cost'].initial = 0
        self.fields['my_shipping'].initial = 0
        self.fields['my_shipping'].help_text = 'Shipping YOU charge your buyer (0 = free). Used for the fee and profit.'
        self.fields['buyer_shipping'].help_text = 'From the eBay page – for comparison only, not used in the profit.'
        # A product saved before the tables existed: start its tables from the single fields.
        if self.instance.pk and not self.instance.competitors and not self.instance.suppliers:
            comps, sups = lists.lists_from_flat({f: getattr(self.instance, f) for f in TABLE_FIELDS})
            self.initial.update(competitors=comps, suppliers=sups)

    def clean_item_id(self):
        raw = self.cleaned_data['item_id']
        # A full eBay link is accepted too: ".../itm/147123049946?..." → 147123049946
        from_url = re.search(r'(?:/itm/(?:[^\s/?#]+/)?|[?&]item=)(\d{9,15})', raw)
        item_id = from_url.group(1) if from_url else re.sub(r'\s+', '', raw)
        if not item_id.isdigit():
            raise forms.ValidationError('The eBay item ID should contain digits only (or paste the eBay listing link).')
        if len(item_id) > 20:
            raise forms.ValidationError('This is too long for an eBay item ID.')
        return item_id

    def clean_other_cost(self):
        value = self.cleaned_data.get('other_cost')
        return 0 if value is None else value

    def clean_my_shipping(self):
        value = self.cleaned_data.get('my_shipping')
        return 0 if value is None else value

    def clean(self):
        cleaned = super().clean()
        choice = (cleaned.get('tab_choice') or '').strip()
        if choice == NEW_TAB:
            name = (cleaned.get('new_tab') or '').strip()
            if not name:
                self.add_error('new_tab', 'Type a name for the new tab.')
            elif name.lower() in RESERVED_TABS or re.search(r"[\[\]*?/\\:']", name):
                self.add_error('new_tab', "Choose another name (avoid [ ] * ? / \\ : ' and “eBay Settings”).")
            cleaned['tab'] = name
        elif choice:
            cleaned['tab'] = choice
        else:
            self.add_error('tab_choice', 'Choose a tab.')
        # Competitor / supplier tables → the single fields used by the formulas and the sheet.
        if 'competitors' in self.data or 'suppliers' in self.data:
            comps = lists.clean_competitors(cleaned.get('competitors'))
            sups = lists.clean_suppliers(cleaned.get('suppliers'))
            for problem in lists.link_problems(comps, sups):
                self.add_error(None, problem)
        else:  # posted without the tables (older form / API): build them from the single fields
            comps, sups = lists.lists_from_flat({f: cleaned.get(f) for f in TABLE_FIELDS})
        cleaned.update(competitors=comps, suppliers=sups, **lists.flat_fields(comps, sups))
        # Never write into a sheet tab that holds the user's own, different data.
        tab = cleaned.get('tab', '')
        if tab and tab.lower() in self.blocked_tabs:
            field = 'new_tab' if choice == NEW_TAB else 'tab_choice'
            self.add_error(field, f'The “{tab}” tab in your Google Sheet already has other data. '
                                  f'Choose an empty tab or create a new one.')
        return cleaned

    def save(self, commit=True):
        self.instance.tab = self.cleaned_data['tab']
        return super().save(commit)


class FeeSettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DropshipSettings
        fields = list(DropshipSettings.FEE_FIELDS)
        labels = {
            'ebay_fee_pct': 'eBay Fee %',
            'ebay_fixed_fee': 'Fixed Fee (order ≤ threshold)',
            'ebay_fixed_fee_high': 'Fixed Fee (order > threshold)',
            'fixed_fee_threshold': 'Fixed Fee threshold ($)',
            'ad_rate_pct': 'Ad Rate %',
            'sales_tax_pct': 'Sales Tax buffer %',
        }
        help_texts = {
            'ebay_fee_pct': 'Final value fee for most categories (13.6% since Feb 2025).',
            'sales_tax_pct': 'eBay charges its fee on the sales tax too. 0 = ignore, ~7 = safe side (US).',
        }


class ConnectionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DropshipSettings
        fields = ['sheet_webapp_url']
        widgets = {'sheet_webapp_url': forms.URLInput(attrs={'placeholder': 'https://script.google.com/macros/s/…/exec'})}

    def clean_sheet_webapp_url(self):
        url = self.cleaned_data['sheet_webapp_url'].strip()
        if url and not re.match(r'^https://script\.google\.com/macros/s/[\w-]+/exec/?$', url):
            raise forms.ValidationError('Paste the web app URL that starts with https://script.google.com/macros/s/ and ends with /exec')
        return url
