from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Order, Product
from .serializers import OrderSerializer
from .tracking import (
    CUSTOMER_STATUS_HINTS,
    CUSTOMER_STATUS_LABELS,
    STATUS_BADGES,
    mask_phone,
    read_tracking_token,
    status_steps,
)


def banners_list_api(request):
    # FIXME move data to db?
    return JsonResponse(
        [
            {
                "title": "Burger",
                "src": static("burger.jpg"),
                "text": "Tasty Burger at your door step",
            },
            {
                "title": "Spices",
                "src": static("food.jpg"),
                "text": "All Cuisines",
            },
            {
                "title": "New York",
                "src": static("tasty.jpg"),
                "text": "Food is incomplete without a tasty dessert",
            },
        ],
        safe=False,
        json_dumps_params={
            "ensure_ascii": False,
            "indent": 4,
        },
    )


def product_list_api(request):
    products = Product.objects.select_related("category").available()

    dumped_products = []
    for product in products:
        dumped_product = {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "special_status": product.special_status,
            "description": product.description,
            "category": {
                "id": product.category.id,
                "name": product.category.name,
            }
            if product.category
            else None,
            "image": product.image.url,
        }
        dumped_products.append(dumped_product)
    return JsonResponse(
        dumped_products,
        safe=False,
        json_dumps_params={
            "ensure_ascii": False,
            "indent": 4,
        },
    )


class RegisterOrderView(APIView):
    """Приём заказа из витрины.

    Ограничение по IP защищает публичный эндпоинт от мусорных заказов;
    лимит настраивается ключом `order` в `DEFAULT_THROTTLE_RATES`.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "order"

    def post(self, request):
        serializer = OrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@never_cache
def order_status(request, token: str):
    """Публичная страница статуса по подписанной ссылке из заказа."""
    order_id = read_tracking_token(token)
    order = None
    if order_id is not None:
        order = (
            Order.objects.prefetch_related("items__product")
            .filter(pk=order_id)
            .first()
        )

    if order is None:
        # Ссылка битая, просроченная или заказ удалён — отдаём понятную
        # страницу вместо технической 404, но с кодом 404 для поисковиков.
        return render(
            request,
            "foodcartapp/order_status.html",
            {"order": None},
            status=404,
        )

    items = list(order.items.all())
    context = {
        "order": order,
        "status_label": CUSTOMER_STATUS_LABELS.get(
            order.status, order.get_status_display()
        ),
        "status_hint": CUSTOMER_STATUS_HINTS.get(order.status, ""),
        "status_badge": STATUS_BADGES.get(order.status, "default"),
        "steps": status_steps(order),
        "total": sum(item.total_price for item in items),
        "masked_phone": mask_phone(order.phonenumber),
    }
    return render(request, "foodcartapp/order_status.html", context)
