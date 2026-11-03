import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
# Persist a local development key without copying any course credentials.
keyfile = BASE_DIR / '.local-secret'
if not keyfile.exists():
    try:
        with keyfile.open('x', encoding='utf-8') as stream:
            stream.write(secrets.token_urlsafe(48))
    except FileExistsError:
        pass
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or keyfile.read_text().strip()
DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'coach']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth']}}]
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'zh-hant'
TIME_ZONE = 'Asia/Taipei'
USE_TZ = True
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
HINT_MODE = os.environ.get('HINT_MODE', 'demo')
MODEL_URL = os.environ.get('Model_URL', 'http://127.0.0.1:11436').rstrip('/')
from model_backend import active_deployment
MODEL_NAME = os.environ.get('Model_Name') or active_deployment()['name']
OLLAMA_GATEWAY_API_KEY = os.environ.get('OLLAMA_GATEWAY_API_KEY', '')
CONTEXT_TOKENS = int(os.environ.get('CONTEXT_TOKENS', '4096'))
STATIC_URL = '/assets/'
