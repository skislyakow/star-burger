import os

import dj_database_url
from environs import Env

env = Env()
env.read_env()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")


SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", ["127.0.0.1", "localhost"])

# nginx терминирует TLS и передаёт схему в X-Forwarded-Proto. Без этой строки
# Django считает запрос http и ломает secure-cookies, HSTS и редирект.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Прод-режим безопасности включается одной переменной в /opt/star-burger/.env.
# По умолчанию выключен: иначе runserver и pytest редиректили бы на https.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_SSL_REDIRECT
# Заголовок preload безвреден, пока домен не отправлен в hstspreload.org.
SECURE_HSTS_PRELOAD = SECURE_SSL_REDIRECT

INSTALLED_APPS = [
    "places.apps.PlacesConfig",
    "rest_framework",
    "phonenumber_field",
    "foodcartapp.apps.FoodcartappConfig",
    "restaurateur.apps.RestaurateurConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# debug_toolbar — dev-зависимость (группа dev в pyproject.toml). На проде он не
# установлен, поэтому подключаем его только в дебаг-режиме.
if DEBUG:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")

ROOT_URLCONF = "star_burger.urls"

DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.versions.VersionsPanel",
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    "debug_toolbar.panels.headers.HeadersPanel",
    "debug_toolbar.panels.request.RequestPanel",
    "debug_toolbar.panels.sql.SQLPanel",
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.signals.SignalsPanel",
    "debug_toolbar.panels.logging.LoggingPanel",
    "debug_toolbar.panels.redirects.RedirectsPanel",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "star_burger.wsgi.application"

MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{os.path.join(BASE_DIR, 'db.sqlite3')}"
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "ru-RU"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = "/static/"

INTERNAL_IPS = ["127.0.0.1"]


STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "assets"),
    os.path.join(BASE_DIR, "bundles"),
]


REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        # Browsable API — удобная песочница для разработки, но на проде она
        # показывает формы и тянет шаблоны DRF. Оставляем только в DEBUG.
        *(["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Публичное оформление заказа: ограничение по IP. Кэш — LocMem,
        # поэтому на проде лимит действует на каждый воркер gunicorn.
        "order": "30/hour",
    },
}

YANDEX_GEOCODER_API_KEY = env("YANDEX_GEOCODER_API_KEY", "")

ROLLBAR_TOKEN = env("ROLLBAR_TOKEN", "")
ROLLBAR = {
    "access_token": ROLLBAR_TOKEN,
    "environment": env("ROLLBAR_ENVIRONMENT", "development"),
    "branch": "main",
    "root": BASE_DIR,
}
if ROLLBAR_TOKEN:
    import rollbar

    rollbar.init(**ROLLBAR)
    MIDDLEWARE.append(
        "rollbar.contrib.django.middleware.RollbarNotifierMiddleware"
    )
