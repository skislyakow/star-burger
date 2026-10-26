"""Оформление заказа через API: снимок цены, валидация, одна транзакция."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from foodcartapp.models import Order, OrderItem

pytestmark = pytest.mark.django_db

ORDER_URL = "/api/order/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def payload(products, **overrides):
    data = {
        "firstname": "Иван",
        "lastname": "Петров",
        "phonenumber": "+79161234567",
        "address": "Москва, Тверская, 1",
        "products": products,
    }
    data.update(overrides)
    return data


def test_creates_order_with_items(client, product_factory, restaurant_factory):
    restaurant = restaurant_factory()
    burger = product_factory(name="Бургер", available_in=(restaurant,))
    cola = product_factory(
        name="Кола", price="99.50", available_in=(restaurant,)
    )

    response = client.post(
        ORDER_URL,
        payload(
            [
                {"product": burger.id, "quantity": 2},
                {"product": cola.id, "quantity": 1},
            ]
        ),
        format="json",
    )

    assert response.status_code == 201
    order = Order.objects.get()
    assert order.firstname == "Иван"
    assert order.status == Order.Status.UNPROCESSED
    assert order.items.count() == 2


def test_snapshots_price_at_order_time(
    client, product_factory, restaurant_factory
):
    restaurant = restaurant_factory()
    burger = product_factory(price="199.00", available_in=(restaurant,))

    response = client.post(
        ORDER_URL,
        payload([{"product": burger.id, "quantity": 2}]),
        format="json",
    )

    assert response.status_code == 201
    item = OrderItem.objects.get()
    assert item.quantity == 2
    assert item.price == Decimal("199.00")


def test_ignores_price_from_request(
    client, product_factory, restaurant_factory
):
    restaurant = restaurant_factory()
    burger = product_factory(price="199.00", available_in=(restaurant,))

    response = client.post(
        ORDER_URL,
        payload([{"product": burger.id, "quantity": 1, "price": "1.00"}]),
        format="json",
    )

    assert response.status_code == 201
    assert OrderItem.objects.get().price == Decimal("199.00")


def test_merges_duplicate_products(
    client, product_factory, restaurant_factory
):
    restaurant = restaurant_factory()
    burger = product_factory(available_in=(restaurant,))

    response = client.post(
        ORDER_URL,
        payload(
            [
                {"product": burger.id, "quantity": 2},
                {"product": burger.id, "quantity": 1},
            ]
        ),
        format="json",
    )

    assert response.status_code == 201
    item = OrderItem.objects.get()
    assert item.product == burger
    assert item.quantity == 3


def test_rejects_product_unavailable_in_every_restaurant(
    client, product_factory
):
    burger = product_factory()

    response = client.post(
        ORDER_URL,
        payload([{"product": burger.id, "quantity": 1}]),
        format="json",
    )

    assert response.status_code == 400
    assert "products" in response.data
    assert Order.objects.count() == 0


def test_does_not_create_order_when_any_line_is_invalid(
    client, product_factory, restaurant_factory
):
    restaurant = restaurant_factory()
    available = product_factory(available_in=(restaurant,))
    unavailable = product_factory(name="Недоступный")

    response = client.post(
        ORDER_URL,
        payload(
            [
                {"product": available.id, "quantity": 1},
                {"product": unavailable.id, "quantity": 1},
            ]
        ),
        format="json",
    )

    assert response.status_code == 400
    assert Order.objects.count() == 0
    assert OrderItem.objects.count() == 0


def test_rejects_zero_quantity(client, product_factory, restaurant_factory):
    restaurant = restaurant_factory()
    burger = product_factory(available_in=(restaurant,))

    response = client.post(
        ORDER_URL,
        payload([{"product": burger.id, "quantity": 0}]),
        format="json",
    )

    assert response.status_code == 400
    assert Order.objects.count() == 0


def test_rejects_empty_product_list(client):
    response = client.post(ORDER_URL, payload([]), format="json")

    assert response.status_code == 400
    assert Order.objects.count() == 0


def test_rejects_unknown_product(client):
    response = client.post(
        ORDER_URL,
        payload([{"product": 999999, "quantity": 1}]),
        format="json",
    )

    assert response.status_code == 400
    assert Order.objects.count() == 0


def test_rejects_order_without_required_fields(client, product_factory):
    burger = product_factory()

    response = client.post(
        ORDER_URL,
        payload([{"product": burger.id, "quantity": 1}], firstname=""),
        format="json",
    )

    assert response.status_code == 400
    assert "firstname" in response.data
    assert Order.objects.count() == 0


def test_total_cost_counts_quantity_and_price(
    order_factory, product_factory, add_item
):
    burger = product_factory(name="Бургер", price="199.00")
    cola = product_factory(name="Кола", price="99.50")
    order = order_factory()
    add_item(order, burger, quantity=2)
    add_item(order, cola, quantity=1)

    total = (
        Order.objects.with_total_cost()  # type: ignore[attr-defined]
        .get(pk=order.pk)
        .total_cost
    )

    assert total == Decimal("497.50")


def test_order_endpoint_is_throttled(
    client, product_factory, restaurant_factory, monkeypatch
):
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {"order": "3/min"},
    )
    restaurant = restaurant_factory()
    burger = product_factory(available_in=(restaurant,))
    body = payload([{"product": burger.id, "quantity": 1}])

    statuses = [
        client.post(ORDER_URL, body, format="json").status_code
        for _ in range(3)
    ]
    response = client.post(ORDER_URL, body, format="json")

    assert statuses == [201, 201, 201]
    assert response.status_code == 429
