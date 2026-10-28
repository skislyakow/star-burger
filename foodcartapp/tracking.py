"""Публичная ссылка на статус заказа.

Клиенту не нужно регистрироваться: в ссылке лежит id заказа, подписанный
`SECRET_KEY`. Подделать id или перебрать чужие заказы нельзя, а в базу
ничего не пишем — ссылка работает и для заказов, созданных до появления
страницы. Срок жизни ограничен, чтобы старая переписка не открывала
заказ вечно.
"""

from django.core import signing

from .models import Order

SALT = "foodcartapp.order-tracking"
TRACKING_LINK_MAX_AGE = 60 * 60 * 24 * 30  # 30 дней

CUSTOMER_STATUS_LABELS: dict[str, str] = {
    Order.Status.UNPROCESSED: "Принят",
    Order.Status.ASSEMBLED: "Собран",
    Order.Status.DELIVERED: "Доставлен",
    Order.Status.COMPLETED: "Выполнен",
}

CUSTOMER_STATUS_HINTS: dict[str, str] = {
    Order.Status.UNPROCESSED: (
        "Мы приняли заказ и скоро позвоним, чтобы подтвердить его."
    ),
    Order.Status.ASSEMBLED: "Заказ собран и ждёт курьера.",
    Order.Status.DELIVERED: "Курьер уже доставил заказ.",
    Order.Status.COMPLETED: (
        "Заказ выполнен. Спасибо, что выбрали Star Burger!"
    ),
}

STATUS_BADGES: dict[str, str] = {
    Order.Status.UNPROCESSED: "info",
    Order.Status.ASSEMBLED: "warning",
    Order.Status.DELIVERED: "success",
    Order.Status.COMPLETED: "success",
}

STATUS_STEPS: list[str] = [
    Order.Status.UNPROCESSED,
    Order.Status.ASSEMBLED,
    Order.Status.DELIVERED,
    Order.Status.COMPLETED,
]


def build_tracking_token(order_id: int) -> str:
    """Подписывает id заказа: без ключа подпись не подделать."""
    return signing.dumps(order_id, salt=SALT)


def read_tracking_token(
    token: str, *, max_age: int = TRACKING_LINK_MAX_AGE
) -> int | None:
    """Возвращает id заказа из ссылки или `None`, если ссылка не наша."""
    try:
        order_id = signing.loads(token, salt=SALT, max_age=max_age)
    except signing.BadSignature:
        return None
    return order_id if isinstance(order_id, int) else None


def status_steps(order: Order) -> list[dict[str, object]]:
    """Шаги доставки: пройденные, текущий и будущие."""
    current = (
        STATUS_STEPS.index(order.status) if order.status in STATUS_STEPS else 0
    )
    dates: dict[str, object] = {
        Order.Status.UNPROCESSED: order.created_at,
        Order.Status.DELIVERED: order.delivered_at,
    }
    return [
        {
            "status": step,
            "label": CUSTOMER_STATUS_LABELS[step],
            "state": (
                "done"
                if index < current
                else "current"
                if index == current
                else "pending"
            ),
            "at": dates.get(step),
        }
        for index, step in enumerate(STATUS_STEPS)
    ]


def mask_phone(phone: object) -> str:
    """Оставляет код страны, первые цифры и две последние.

    Ссылку могут переслать в мессенджере, поэтому номер на странице не
    показываем целиком — клиент и так знает свой телефон.
    """
    digits = "".join(char for char in str(phone) if char.isdigit())
    if len(digits) < 10:
        return "***"
    return f"+{digits[0]} {digits[1:4]} ***-**-{digits[-2:]}"
