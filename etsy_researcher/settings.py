import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env (project root)
load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-your-secret-key-here')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'accounts.apps.AccountsConfig',
    'keywords',
    'mockups.apps.MockupsConfig',
    'keyword_bank.apps.KeywordBankConfig',
    'profit_pulse',
    'django_bootstrap5',
    'rank_optimizer.apps.RankOptimizerConfig',
    'pinterest_seo',
    'customer_detail.apps.CustomerDetailConfig',
    'forecaster.apps.ForecasterConfig',

    'django_extensions',
    'competitor_shop_analysis.apps.CompetitorShopAnalysisConfig',
    'supplier_management.apps.SupplierManagementConfig',
    'ebay_dropshipping.apps.EbayDropshippingConfig',
    'stock_hunting.apps.StockHuntingConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.AccessControlMiddleware',
]

ROOT_URLCONF = 'etsy_researcher.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.navigation',
            ],
        },
    },
]

WSGI_APPLICATION = 'etsy_researcher.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Project-wide assets (Velzon theme, app.css/app.js). App folders like keywords/static are found automatically.
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'keywords.User'
AUTHENTICATION_BACKENDS = ['accounts.backends.EmailOrUsernameBackend']

LOGIN_REDIRECT_URL = 'overview'
LOGOUT_REDIRECT_URL = 'login'
LOGIN_URL = 'login'

# Sessions: "Keep me signed in" keeps the session for two weeks, otherwise it ends with the browser.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # templates read the token from the cookie for AJAX calls

# Bootstrap alert classes for Django messages.
from django.contrib.messages import constants as message_constants
MESSAGE_TAGS = {message_constants.ERROR: 'danger'}

# Email (password reset). Prints emails to the console unless SMTP is configured in .env.
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('1', 'true', 'yes')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Atif-Zak Analytics <no-reply@atifzak.local>')

# AI & Image Processing Limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 20971520  # 20MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20971520  # 20MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000




GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
