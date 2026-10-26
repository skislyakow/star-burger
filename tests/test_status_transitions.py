"""Статусы заказа: даты событий и правило «назначили ресторан — собрали»."""

from datetime import timedelta

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.utils import timezone

from foodcartapp.admin import OrderAdmin
from foodcartapp.models import Order

pytestmark = pytest.mark.django_db


def save_through_admin(order: Order, *, change: bool = True) -> None:
    request = RequestFactory().post("/admin/foodcartapp/order/")
    model_admin = OrderAdmin(Order, admin.site)
    model_admin.save_model(
        request,
        order,
        form=None,  # type: ignore[arg-type]
        change=change,
    )


def test_leaving_unprocessed_stamps_call_date(order_factory):
    order = order_factory()

    order.transition_to(Order.Status.ASSEMBLED)
    order.save()

    order.refresh_from_db()
    assert order.status == Order.Status.ASSEMBLED
    assert order.called_at == timezone.localdate()
    assert order.delivered_at is None


def test_delivery_stamps_datetime(order_factory):
    order = order_factory(status=Order.Status.ASSEMBLED)

    order.transition_to(Order.Status.DELIVERED)
    order.save()

    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED
    assert order.delivered_at is not None


def test_delivered_at_is_not_overwritten(order_factory):
    order = order_factory(status=Order.Status.DELIVERED)
    moment = timezone.now() - timedelta(days=1)
    order.delivered_at = moment
    order.save()

    order.transition_to(Order.Status.COMPLETED)
    order.save()

    order.refresh_from_db()
    assert order.status == Order.Status.COMPLETED
    assert order.delivered_at == moment


def test_same_status_does_not_stamp_call_date(order_factory):
    order = order_factory()

    order.transition_to(Order.Status.UNPROCESSED)

    assert order.called_at is None


def test_transition_assigns_restaurant(order_factory, restaurant_factory):
    order = order_factory()
    restaurant = restaurant_factory()

    order.transition_to(Order.Status.ASSEMBLED, restaurant=restaurant)

    assert order.restaurant == restaurant
    assert order.status == Order.Status.ASSEMBLED


def test_unknown_status_is_rejected(order_factory):
    order = order_factory()

    with pytest.raises(ValueError):
        order.transition_to("teleported")


def test_admin_assembles_order_when_restaurant_is_assigned(
    order_factory, restaurant_factory
):
    order = order_factory()
    order.restaurant = restaurant_factory()

    save_through_admin(order)

    order.refresh_from_db()
    assert order.status == Order.Status.ASSEMBLED
    assert order.called_at == timezone.localdate()


def test_admin_keeps_order_unprocessed_without_restaurant(order_factory):
    order = order_factory()

    save_through_admin(order)

    order.refresh_from_db()
    assert order.status == Order.Status.UNPROCESSED
    assert order.called_at is None


def test_admin_stamps_delivery_date(order_factory):
    order = order_factory(status=Order.Status.ASSEMBLED)
    order.status = Order.Status.DELIVERED

    save_through_admin(order)

    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED
    assert order.delivered_at is not None
