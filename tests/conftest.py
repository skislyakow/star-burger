"""Общие фикстуры: минимум данных, чтобы тест читался как сценарий."""

from collections.abc import Iterable, Mapping
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from foodcartapp.models import (
    Order,
    OrderItem,
    Product,
    ProductCategory,
    Restaurant,
    RestaurantMenuItem,
)

Coordinates = tuple[float, float]


class FakeGeocoder:
    """Геокодер, который не ходит в Яндекс.

    Адреса без координат возвращаются как `None` — ровно так ведёт себя
    настоящий геокодер, когда не смог разобрать адрес.
    """

    def __init__(self) -> None:
        self.coordinates: dict[str, Coordinates | None] = {}
        self.calls: list[set[str]] = []

    def __call__(
        self, addresses: Iterable[str]
    ) -> Mapping[str, Coordinates | None]:
        requested = set(addresses)
        self.calls.append(requested)
        return {
            address: self.coordinates.get(address) for address in requested
        }


@pytest.fixture
def geocoder() -> FakeGeocoder:
    return FakeGeocoder()


@pytest.fixture
def category(db) -> ProductCategory:
    return ProductCategory.objects.create(name="Бургеры")


@pytest.fixture
def restaurant_factory(db):
    def make(
        name: str = "Первый",
        address: str = "Москва, Тверская, 1",
    ) -> Restaurant:
        return Restaurant.objects.create(name=name, address=address)

    return make


@pytest.fixture
def product_factory(db, category):
    def make(
        name: str = "Бургер",
        price: str = "199.00",
        available_in: tuple[Restaurant, ...] = (),
    ) -> Product:
        product = Product.objects.create(
            name=name,
            category=category,
            price=Decimal(price),
            image="products/burger.jpg",
        )
        for restaurant in available_in:
            RestaurantMenuItem.objects.create(
                restaurant=restaurant,
                product=product,
                availability=True,
            )
        return product

    return make


@pytest.fixture
def order_factory(db):
    def make(
        address: str = "Москва, Тверская, 1",
        status: str = Order.Status.UNPROCESSED,
    ) -> Order:
        return Order.objects.create(
            firstname="Иван",
            lastname="Петров",
            phonenumber="+79161234567",
            address=address,
            status=status,
        )

    return make


@pytest.fixture
def add_item(db):
    def add(order: Order, product: Product, quantity: int = 1) -> OrderItem:
        return OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price=product.price,
        )

    return add


@pytest.fixture
def manager(db) -> User:
    return User.objects.create_user(
        username="manager",
        password="manager-secret",
        is_staff=True,
    )
