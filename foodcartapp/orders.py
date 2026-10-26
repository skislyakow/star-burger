"""Постановка заказа: всё, что должно произойти между «клиент нажал
оформить» и строкой в таблице `Order`.

Модуль держит правила, которые нельзя размазывать по сериализатору и
админке:

- количество в позиции — целое не меньше единицы;
- повторяющиеся товары схлопываются в одну позицию;
- заказать можно только товар, который сейчас доступен хотя бы в одном
  ресторане;
- цена фиксируется на момент заказа (снимок), а не берётся из запроса.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from django.db import transaction

from foodcartapp.models import Order, OrderItem, Product


class OrderError(ValueError):
    """Заказ нельзя создать: позиция некорректна или недоступна."""


@dataclass(frozen=True)
class OrderLine:
    """Позиция заказа до сохранения: товар и количество."""

    product_id: int
    quantity: int


def place_order(
    *,
    firstname: str,
    lastname: str,
    phonenumber: str,
    address: str,
    lines: Iterable[OrderLine],
) -> Order:
    """Создаёт заказ со снимком цен и возвращает его.

    Бросает `OrderError`, если позиции нельзя сохранить; частично
    записанного заказа при этом не остаётся.
    """
    normalized_lines = _normalize(lines)
    products = _load_available_products(normalized_lines)

    with transaction.atomic():
        order = Order.objects.create(
            firstname=firstname,
            lastname=lastname,
            phonenumber=phonenumber,
            address=address,
        )
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    product=products[line.product_id],
                    quantity=line.quantity,
                    price=products[line.product_id].price,
                )
                for line in normalized_lines
            ]
        )
    return order


def _normalize(lines: Iterable[OrderLine]) -> list[OrderLine]:
    totals: dict[int, int] = {}
    for line in lines:
        if line.quantity < 1:
            raise OrderError("Количество должно быть не меньше 1.")
        totals[line.product_id] = (
            totals.get(line.product_id, 0) + line.quantity
        )
    if not totals:
        raise OrderError("Заказ не содержит позиций.")
    return [
        OrderLine(product_id=product_id, quantity=quantity)
        for product_id, quantity in totals.items()
    ]


def _load_available_products(
    lines: Iterable[OrderLine],
) -> dict[int, Product]:
    product_ids = {line.product_id for line in lines}
    products = {
        product.id: product
        for product in Product.objects.available().filter(id__in=product_ids)
    }
    missing = product_ids - products.keys()
    if missing:
        unavailable = ", ".join(
            str(product_id) for product_id in sorted(missing)
        )
        raise OrderError(f"Товары недоступны для заказа: {unavailable}.")
    return products
