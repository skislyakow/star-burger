"""Правила подбора ресторана: пересечение меню, расстояния, сортировка."""

import pytest
from geopy.distance import distance as geo_distance

from foodcartapp.fulfillment import (
    FulfillmentService,
    RestaurantOffer,
)
from foodcartapp.models import RestaurantMenuItem

pytestmark = pytest.mark.django_db

ORDER_ADDRESS = "Москва, Тверская, 1"
NEAR_ADDRESS = "Москва, Тверская, 5"
FAR_ADDRESS = "Москва, Ленинградский проспект, 1"

ORDER_POINT = (55.7570, 37.6050)
NEAR_POINT = (55.7600, 37.6100)
FAR_POINT = (55.7900, 37.5600)


def test_offers_only_restaurants_with_every_item(
    order_factory,
    restaurant_factory,
    product_factory,
    add_item,
    geocoder,
):
    both = restaurant_factory(name="Оба", address=NEAR_ADDRESS)
    only_burger = restaurant_factory(
        name="Только бургер", address=NEAR_ADDRESS
    )
    burger = product_factory(name="Бургер", available_in=(both, only_burger))
    cola = product_factory(name="Кола", available_in=(both,))
    order = order_factory()
    add_item(order, burger)
    add_item(order, cola)

    [fulfillment] = FulfillmentService(geocode=geocoder).fulfillments([order])

    assert [offer.restaurant for offer in fulfillment.offers] == [both]


def test_single_item_order_is_offered_by_all_restaurants_with_it(
    order_factory,
    restaurant_factory,
    product_factory,
    add_item,
    geocoder,
):
    first = restaurant_factory(name="Первый", address=NEAR_ADDRESS)
    second = restaurant_factory(name="Второй", address=FAR_ADDRESS)
    burger = product_factory(available_in=(first, second))
    order = order_factory()
    add_item(order, burger)

    [fulfillment] = FulfillmentService(geocode=geocoder).fulfillments([order])

    assert {offer.restaurant for offer in fulfillment.offers} == {
        first,
        second,
    }


def test_no_offers_when_no_restaurant_has_the_item(
    order_factory, product_factory, add_item, geocoder
):
    burger = product_factory()
    order = order_factory()
    add_item(order, burger)

    [fulfillment] = FulfillmentService(geocode=geocoder).fulfillments([order])

    assert fulfillment.offers == ()


def test_disabled_menu_item_does_not_count(
    order_factory, restaurant_factory, product_factory, add_item, geocoder
):
    restaurant = restaurant_factory()
    burger = product_factory()
    RestaurantMenuItem.objects.create(
        restaurant=restaurant, product=burger, availability=False
    )
    order = order_factory()
    add_item(order, burger)

    [fulfillment] = FulfillmentService(geocode=geocoder).fulfillments([order])

    assert fulfillment.offers == ()


def test_empty_order_has_no_offers(order_factory, geocoder):
    order = order_factory()

    [fulfillment] = FulfillmentService(geocode=geocoder).fulfillments([order])

    assert fulfillment.offers == ()


def test_unknown_order_address_keeps_offers_without_distance(
    order_factory, restaurant_factory, product_factory, add_item, geocoder
):
    restaurant = restaurant_factory(address=NEAR_ADDRESS)
    burger = product_factory(available_in=(restaurant,))
    order = order_factory()
    add_item(order, burger)
    geocoder.coordinates = {NEAR_ADDRESS: NEAR_POINT}

    [fulfillment] = FulfillmentService(geocode=geocoder).fulfillments([order])

    assert fulfillment.address_known is False
    assert len(fulfillment.offers) == 1
    assert fulfillment.offers[0].distance_km is None


def test_known_address_is_reflected_in_fulfillment(
    order_factory, restaurant_factory, product_factory, add_item, geocoder
):
    restaurant = restaurant_factory(address=NEAR_ADDRESS)
    burger = product_factory(available_in=(restaurant,))
    order = order_factory(address=ORDER_ADDRESS)
    add_item(order, burger)
    geocoder.coordinates = {
        ORDER_ADDRESS: ORDER_POINT,
        NEAR_ADDRESS: NEAR_POINT,
    }

    [fulfillment] = FulfillmentService(geocode=geocoder).fulfillments([order])

    assert fulfillment.address_known is True
    expected = geo_distance(ORDER_POINT, NEAR_POINT).km
    assert fulfillment.offers[0].distance_km == pytest.approx(expected)


def test_restaurant_without_address_goes_last(
    order_factory,
    restaurant_factory,
    product_factory,
    add_item,
    geocoder,
):
    near = restaurant_factory(name="Ближний", address=NEAR_ADDRESS)
    unknown = restaurant_factory(name="Без адреса", address="")
    burger = product_factory(available_in=(near, unknown))
    order = order_factory(address=ORDER_ADDRESS)
    add_item(order, burger)
    geocoder.coordinates = {
        ORDER_ADDRESS: ORDER_POINT,
        NEAR_ADDRESS: NEAR_POINT,
    }

    [fulfillment] = FulfillmentService(geocode=geocoder).fulfillments([order])

    assert [offer.restaurant for offer in fulfillment.offers] == [
        near,
        unknown,
    ]
    assert fulfillment.offers[1].distance_km is None


def test_offers_are_sorted_by_distance_then_name(
    order_factory,
    restaurant_factory,
    product_factory,
    add_item,
    geocoder,
):
    far = restaurant_factory(name="Дальний", address=FAR_ADDRESS)
    near = restaurant_factory(name="Ближний", address=NEAR_ADDRESS)
    burger = product_factory(available_in=(far, near))
    order = order_factory(address=ORDER_ADDRESS)
    add_item(order, burger)
    geocoder.coordinates = {
        ORDER_ADDRESS: ORDER_POINT,
        NEAR_ADDRESS: NEAR_POINT,
        FAR_ADDRESS: FAR_POINT,
    }

    [fulfillment] = FulfillmentService(geocode=geocoder).fulfillments([order])

    assert [offer.restaurant.name for offer in fulfillment.offers] == [
        "Ближний",
        "Дальний",
    ]


def test_geocodes_every_address_in_one_call(
    order_factory,
    restaurant_factory,
    product_factory,
    add_item,
    geocoder,
):
    restaurant = restaurant_factory(address=NEAR_ADDRESS)
    burger = product_factory(available_in=(restaurant,))
    order = order_factory(address=ORDER_ADDRESS)
    add_item(order, burger)

    FulfillmentService(geocode=geocoder).fulfillments([order])

    assert geocoder.calls == [{ORDER_ADDRESS, NEAR_ADDRESS}]


def test_without_orders_geocoder_is_not_called(geocoder):
    assert FulfillmentService(geocode=geocoder).fulfillments([]) == []
    assert geocoder.calls == []


def test_distance_display_is_human_readable(restaurant_factory):
    restaurant = restaurant_factory()

    assert (
        RestaurantOffer(
            restaurant=restaurant, distance_km=None
        ).distance_display
        == "адрес не определён"
    )
    assert (
        RestaurantOffer(
            restaurant=restaurant, distance_km=1.24
        ).distance_display
        == "1,2 км"
    )
    assert (
        RestaurantOffer(
            restaurant=restaurant, distance_km=2.0
        ).distance_display
        == "2,0 км"
    )
