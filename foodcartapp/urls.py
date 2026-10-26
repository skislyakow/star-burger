from django.urls import path

from .views import RegisterOrderView, banners_list_api, product_list_api

app_name = "foodcartapp"

urlpatterns = [
    path("products/", product_list_api),
    path("banners/", banners_list_api),
    path("order/", RegisterOrderView.as_view()),
]
