from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path

from foodcartapp.views import order_status

from . import settings
from .views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
    path("order/<str:token>/", order_status, name="order_status"),
    path(
        "", render, kwargs={"template_name": "index.html"}, name="start_page"
    ),
    path("api/", include("foodcartapp.urls")),
    path("manager/", include("restaurateur.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path(r"__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
