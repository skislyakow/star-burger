"""Правила выполнения заказа: кто из ресторанов может его приготовить
и насколько далеко от ресторана до клиента.

Раньше это жило в `restaurateur/views.py` россыпью функций, и проверить
их можно было только глазами. Теперь у модуля один вход —
`FulfillmentService.fulfillments(orders)` — и он не ходит в сеть мимо
геокодера, который ему передали.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from geopy.distance import distance

from foodcartapp.models import Order, Restaurant, RestaurantMenuItem
from places.geocoder import get_coordinates_map

Coordinates = tuple[float, float]
GeocodeAddresses = Callable[[Iterable[str]], Mapping[str, Coordinates | None]]


@dataclass(frozen=True)
class RestaurantOffer:
    """Ресторан, который может приготовить заказ, и расстояние до него."""

    restaurant: Restaurant
    distance_km: float | None

    @property
    def distance_display(self) -> str:
        if self.distance_km is None:
            return "адрес не определён"
        return f"{self.distance_km:.1f}".replace(".", ",") + " км"


@dataclass(frozen=True)
class OrderFulfillment:
    """Всё, что менеджеру нужно знать о заказе на доске."""

    order: Order
    address_known: bool
    offers: tuple[RestaurantOffer, ...]


class FulfillmentService:
    """Считает предложения ресторанов для набора заказов.

    Геокодер передаётся снаружи: в тестах — детерминированная заглушка,
    в проде — `places.geocoder.get_coordinates_map` с кэшем в БД.
    """

    def __init__(self, geocode: GeocodeAddresses | None = None) -> None:
        self._geocode = geocode or get_coordinates_map

    def fulfillments(self, orders: Sequence[Order]) -> list[OrderFulfillment]:
        order_list = list(orders)
        if not order_list:
            return []

        restaurants = {r.id: r for r in Restaurant.objects.all()}
        availability = _availability(
            {
                item.product_id
                for order in order_list
                for item in order.items.all()
            }
        )
        coordinates = self._geocode(
            _addresses(order_list, restaurants.values())
        )
        return [
            _fulfillment(order, restaurants, availability, coordinates)
            for order in order_list
        ]


def _addresses(
    orders: Sequence[Order], restaurants: Iterable[Restaurant]
) -> set[str]:
    addresses = {order.address for order in orders}
    addresses.update(r.address for r in restaurants if r.address)
    return addresses


def _availability(product_ids: set[int]) -> dict[int, set[int]]:
    availability: dict[int, set[int]] = {}
    menu_items = RestaurantMenuItem.objects.filter(
        availability=True, product_id__in=product_ids
    ).values_list("product_id", "restaurant_id")
    for product_id, restaurant_id in menu_items:
        availability.setdefault(product_id, set()).add(restaurant_id)
    return availability


def _restaurant_ids(
    order: Order, availability: dict[int, set[int]]
) -> set[int]:
    """Рестораны, где есть все позиции заказа."""
    allowed: set[int] | None = None
    for item in order.items.all():
        in_restaurants = availability.get(item.product_id, set())
        allowed = (
            set(in_restaurants)
            if allowed is None
            else allowed & in_restaurants
        )
        if not allowed:
            break
    return allowed or set()


def _fulfillment(
    order: Order,
    restaurants: Mapping[int, Restaurant],
    availability: dict[int, set[int]],
    coordinates: Mapping[str, Coordinates | None],
) -> OrderFulfillment:
    order_coordinates = coordinates.get(order.address)
    offers = []
    for restaurant_id in _restaurant_ids(order, availability):
        restaurant = restaurants.get(restaurant_id)
        if restaurant is None:
            continue
        offers.append(
            RestaurantOffer(
                restaurant=restaurant,
                distance_km=_distance_km(
                    order_coordinates, coordinates.get(restaurant.address)
                ),
            )
        )
    offers.sort(
        key=lambda offer: (
            offer.distance_km is None,
            offer.distance_km or 0.0,
            offer.restaurant.name,
        )
    )
    return OrderFulfillment(
        order=order,
        address_known=order_coordinates is not None,
        offers=tuple(offers),
    )


def _distance_km(a: Coordinates | None, b: Coordinates | None) -> float | None:
    if a is None or b is None:
        return None
    return distance(a, b).km
