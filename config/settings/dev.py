"""
Development settings for MedConsult.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', 'testserver']

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'medconsult'),
        'USER': os.environ.get('DB_USER', 'medconsult_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'medconsult_pass'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Cache (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
    }
}

# Development-specific settings
INTERNAL_IPS = [
    '127.0.0.1',
]

# Email Configuration (console for development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
