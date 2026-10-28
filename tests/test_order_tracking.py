"""Публичная страница статуса заказа: подписанная ссылка и приватность."""

from decimal import Decimal

import pytest
from django.core import signing
from django.urls import reverse
from rest_framework.test import APIClient

from foodcartapp.models import Order
from foodcartapp.tracking import (
    SALT,
    build_tracking_token,
    mask_phone,
    read_tracking_token,
    status_steps,
)

pytestmark = pytest.mark.django_db


def tracking_url(order: Order) -> str:
    token = build_tracking_token(order.id)
    return reverse("order_status", kwargs={"token": token})


# --- Токен ---------------------------------------------------------------


def test_token_round_trip():
    token = build_tracking_token(42)

    assert read_tracking_token(token) == 42


def test_token_is_not_a_plain_id():
    assert build_tracking_token(42) != "42"


def test_rejects_foreign_and_broken_tokens():
    assert read_tracking_token("42") is None
    assert read_tracking_token("not-a-token") is None


def test_rejects_tampered_token():
    token = build_tracking_token(42)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    assert read_tracking_token(tampered) is None


def test_rejects_signed_but_non_integer_payload():
    forged = signing.dumps("42", salt=SALT)

    assert read_tracking_token(forged) is None


def test_token_expires():
    token = build_tracking_token(42)

    assert read_tracking_token(token, max_age=-1) is None


# --- Страница -----------------------------------------------------------


def test_page_shows_order_status_and_items(
    client, order_factory, product_factory, add_item
):
    order = order_factory(status=Order.Status.ASSEMBLED)
    burger = product_factory(name="Чизбургер", price="199.00")
    add_item(order, burger, quantity=2)

    response = client.get(tracking_url(order))

    assert response.status_code == 200
    content = response.content.decode()
    assert f"Заказ №{order.id}" in content
    assert "Собран" in content
    assert "Заказ собран и ждёт курьера." in content
    assert "Чизбургер" in content
    assert "398" in content
    # Страницу не должны индексировать поисковики, а токен — утекать
    # через Referer при переходе по внешним ссылкам.
    assert "noindex" in content
    assert "no-referrer" in content
    assert "no-store" in response["Cache-Control"]


def test_page_masks_phone(client, order_factory):
    order = order_factory()

    content = client.get(tracking_url(order)).content.decode()

    assert "+7 916 ***-**-67" in content
    assert "123-45-67" not in content
    assert "9161234567" not in content


def test_status_changes_are_visible(client, order_factory):
    order = order_factory()
    url = tracking_url(order)

    assert "Принят" in client.get(url).content.decode()

    order.transition_to(Order.Status.DELIVERED)
    order.save()

    content = client.get(url).content.decode()
    assert "Доставлен" in content
    assert "Курьер уже доставил заказ." in content


def test_invalid_token_shows_friendly_404(client):
    response = client.get("/order/not-a-token/")

    assert response.status_code == 404
    assert "Ссылка не работает" in response.content.decode()


def test_deleted_order_shows_404(client):
    token = build_tracking_token(999999)

    response = client.get(reverse("order_status", kwargs={"token": token}))

    assert response.status_code == 404
    assert "Ссылка не работает" in response.content.decode()


# --- Вспомогательные функции -------------------------------------------


def test_status_steps_mark_progress(order_factory):
    order = order_factory(status=Order.Status.ASSEMBLED)

    states = [step["state"] for step in status_steps(order)]

    assert states == ["done", "current", "pending", "pending"]


def test_mask_phone_keeps_country_and_last_digits():
    assert mask_phone("+7 916 123-45-67") == "+7 916 ***-**-67"
    assert mask_phone("") == "***"


def test_order_item_total_price(order_factory, product_factory, add_item):
    order = order_factory()
    burger = product_factory(price="199.00")
    item = add_item(order, burger, quantity=2)

    assert item.total_price == Decimal("398.00")


# --- API ----------------------------------------------------------------


def test_order_api_returns_working_tracking_link(
    product_factory, restaurant_factory
):
    client = APIClient()
    restaurant = restaurant_factory()
    burger = product_factory(name="Чизбургер", available_in=(restaurant,))

    response = client.post(
        "/api/order/",
        {
            "firstname": "Иван",
            "lastname": "Петров",
            "phonenumber": "+79161234567",
            "address": "Москва, Тверская, 1",
            "products": [{"product": burger.id, "quantity": 1}],
        },
        format="json",
    )

    assert response.status_code == 201
    tracking_url_value = response.data["tracking_url"]
    assert tracking_url_value.startswith("/order/")

    page = client.get(tracking_url_value)
    assert page.status_code == 200
    assert "Чизбургер" in page.content.decode()
