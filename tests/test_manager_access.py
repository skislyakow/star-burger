"""Доступ к доске менеджера и её сборка из данных заказа."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from foodcartapp.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture
def no_network_geocoder(monkeypatch):
    monkeypatch.setattr(
        "foodcartapp.fulfillment.get_coordinates_map",
        lambda addresses: {address: None for address in addresses},
    )


@pytest.fixture
def staff_client(client, manager):
    client.force_login(manager)
    return client


def test_anonymous_is_redirected_to_login(client):
    response = client.get(reverse("restaurateur:view_orders"))

    assert response.status_code == 302
    assert reverse("restaurateur:login") in response["Location"]


def test_non_staff_user_is_redirected_to_login(client, db):
    user = User.objects.create_user(username="customer", password="secret")
    client.force_login(user)

    response = client.get(reverse("restaurateur:view_orders"))

    assert response.status_code == 302
    assert reverse("restaurateur:login") in response["Location"]


def test_staff_sees_orders_board(staff_client, no_network_geocoder):
    response = staff_client.get(reverse("restaurateur:view_orders"))

    assert response.status_code == 200
    assert "order_items.html" in [t.name for t in response.templates]


def test_board_lists_open_orders_only(
    staff_client, no_network_geocoder, order_factory
):
    open_order = order_factory()
    order_factory(status=Order.Status.COMPLETED)

    response = staff_client.get(reverse("restaurateur:view_orders"))
    order_ids = {
        fulfillment.order.id
        for fulfillment in response.context["fulfillments"]
    }

    assert order_ids == {open_order.id}


def test_board_says_when_no_restaurant_can_cook(
    staff_client, no_network_geocoder, order_factory, product_factory, add_item
):
    burger = product_factory()
    order = order_factory()
    add_item(order, burger)

    response = staff_client.get(reverse("restaurateur:view_orders"))

    assert "Ни один ресторан не может приготовить заказ." in (
        response.content.decode()
    )


def test_board_lists_restaurants_that_can_cook(
    staff_client,
    no_network_geocoder,
    order_factory,
    restaurant_factory,
    product_factory,
    add_item,
):
    restaurant = restaurant_factory(name="Тверская")
    burger = product_factory(available_in=(restaurant,))
    order = order_factory()
    add_item(order, burger)

    response = staff_client.get(reverse("restaurateur:view_orders"))

    content = response.content.decode()
    assert "Могут приготовить:" in content
    assert "Тверская" in content


def test_login_page_is_available(client):
    response = client.get(reverse("restaurateur:login"))

    assert response.status_code == 200


def test_manager_can_log_in(client, manager):
    response = client.post(
        reverse("restaurateur:login"),
        {"username": "manager", "password": "manager-secret"},
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("restaurateur:RestaurantView")


def test_wrong_password_keeps_user_on_login_page(client, manager):
    response = client.post(
        reverse("restaurateur:login"),
        {"username": "manager", "password": "wrong"},
    )

    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated


def test_staff_can_open_menu_and_restaurants(staff_client, restaurant_factory):
    restaurant_factory()

    assert (
        staff_client.get(reverse("restaurateur:ProductsView")).status_code
        == 200
    )
    assert (
        staff_client.get(reverse("restaurateur:RestaurantView")).status_code
        == 200
    )
