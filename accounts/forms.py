from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm

from .models import Role
from .modules import MODULES

User = get_user_model()


class StyledFormMixin:
    """Applies Velzon/Bootstrap classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                css = 'form-check-input'
            elif isinstance(widget, forms.Select):
                css = 'form-select'
            else:
                css = 'form-control'
            widget.attrs['class'] = f"{widget.attrs.get('class', '')} {css}".strip()
            if field.label and not isinstance(widget, (forms.CheckboxInput, forms.Select, forms.FileInput)):
                widget.attrs.setdefault('placeholder', f'Enter {field.label.lower()}')
            if isinstance(widget, forms.PasswordInput):
                widget.attrs['class'] += ' pe-5'

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs['class'] = f"{widget.attrs.get('class', '')} is-invalid"


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(label='Username or email', max_length=254,
                               widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username',
                                                             'class': 'form-control-icon'}))
    remember_me = forms.BooleanField(required=False, initial=True, label='Keep me signed in')

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Incorrect username/email or password.',
        'inactive': 'This account has been deactivated. Please contact an administrator.',
    }


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'job_title', 'avatar']
        widgets = {'avatar': forms.FileInput(attrs={'accept': 'image/*'})}

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Another account already uses this email.')
        return email

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and hasattr(avatar, 'size') and avatar.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Avatar must be smaller than 2 MB.')
        return avatar


class UserForm(StyledFormMixin, forms.ModelForm):
    """Create / edit a user from the administration area."""

    password1 = forms.CharField(label='Password', required=False, strip=False,
                                widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    password2 = forms.CharField(label='Confirm password', required=False, strip=False,
                                widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'job_title', 'role', 'is_active']
        labels = {'is_active': 'Account is active'}

    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user
        self.fields['role'].queryset = Role.objects.all()
        self.fields['role'].empty_label = '— Select a role —'
        self.fields['role'].required = True
        self.fields['email'].required = True
        creating = self.instance.pk is None
        self.fields['password1'].required = creating
        self.fields['password2'].required = creating
        if not creating:
            self.fields['password1'].help_text = 'Leave blank to keep the current password.'
        # Users cannot lock themselves out.
        if acting_user and self.instance.pk == acting_user.pk:
            self.fields['is_active'].disabled = True
            self.fields['role'].disabled = not acting_user.is_superuser

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Another account already uses this email.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 or p2:
            if p1 != p2:
                self.add_error('password2', 'The two passwords do not match.')
            else:
                try:
                    password_validation.validate_password(p1, self.instance)
                except forms.ValidationError as e:
                    self.add_error('password1', e)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get('password1'):
            user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class RoleForm(StyledFormMixin, forms.ModelForm):
    modules = forms.MultipleChoiceField(
        choices=[(m.key, m.label) for m in MODULES],
        widget=forms.CheckboxSelectMultiple, required=False,
    )

    class Meta:
        model = Role
        fields = ['name', 'description', 'color', 'modules',
                  'can_manage_users', 'can_manage_roles', 'can_view_activity']
        labels = {
            'can_manage_users': 'Manage users',
            'can_manage_roles': 'Manage roles & permissions',
            'can_view_activity': 'View activity log',
        }
