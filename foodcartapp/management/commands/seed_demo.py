"""Наполняет базу демонстрационными данными.

Команда идемпотентна: повторный запуск не создаёт дубликатов, а существующие
объекты (например, товары с настоящими фотографиями) не трогает. Её можно
запускать и на чистой базе после `migrate`, и на боевой — чтобы завести
демо-аккаунт менеджера.

Примеры:

    uv run python manage.py seed_demo
    uv run python manage.py seed_demo --orders 6
    uv run python manage.py seed_demo --username demo --password secret
"""

import os
from decimal import Decimal
from io import BytesIO
from typing import TypedDict

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont

from foodcartapp.models import (
    Order,
    OrderItem,
    Product,
    ProductCategory,
    Restaurant,
    RestaurantMenuItem,
)
from places.models import Place


class RestaurantData(TypedDict):
    name: str
    address: str
    contact_phone: str
    coordinates: tuple[float, float]


class ProductData(TypedDict):
    name: str
    category: str
    price: str
    description: str
    special_status: bool
    available_in: tuple[int, ...]


class OrderData(TypedDict):
    firstname: str
    lastname: str
    phonenumber: str
    address: str
    status: str
    payment_method: str | None
    comment: str
    items: tuple[tuple[int, int], ...]


DEMO_PASSWORD_ENV = "DEMO_MANAGER_PASSWORD"
DEFAULT_PASSWORD = "demo-star-burger"

RESTAURANTS: tuple[RestaurantData, ...] = (
    {
        "name": "Star Burger Арбат",
        "address": "Москва, ул. Новый Арбат, 15",
        "contact_phone": "+7 495 120-45-67",
        "coordinates": (55.7520, 37.5870),
    },
    {
        "name": "Star Burger Цветной",
        "address": "Москва, Цветной бульвар, 11с2",
        "contact_phone": "+7 495 230-45-67",
        "coordinates": (55.7717, 37.6206),
    },
    {
        "name": "Star Burger Европейский",
        "address": "Москва, пл. Киевского Вокзала, 2",
        "contact_phone": "+7 495 340-45-67",
        "coordinates": (55.7444, 37.5658),
    },
)

# available_in — индексы ресторанов из RESTAURANTS, где блюдо в продаже.
PRODUCTS: tuple[ProductData, ...] = (
    {
        "name": "Стейкхаус",
        "category": "Бургер",
        "price": "400.00",
        "description": "Большой бургер с говядиной, томатами и соусом барбекю.",
        "special_status": True,
        "available_in": (0, 1, 2),
    },
    {
        "name": "Лонг Чизбургер",
        "category": "Бургер",
        "price": "219.00",
        "description": "Длинный бургер с двумя котлетами и сырным соусом.",
        "special_status": True,
        "available_in": (0, 1, 2),
    },
    {
        "name": "Тройной Воппер",
        "category": "Бургер",
        "price": "369.00",
        "description": "Три котлеты на гриле, свежие овощи и фирменный соус.",
        "special_status": False,
        "available_in": (0, 2),
    },
    {
        "name": "Беконайзер",
        "category": "Бургер",
        "price": "319.00",
        "description": "Бургер с беконом, чеддером и хрустящим луком.",
        "special_status": False,
        "available_in": (1, 2),
    },
    {
        "name": "Фиш Ролл",
        "category": "Ролл",
        "price": "199.00",
        "description": "Ролл с белой рыбой, салатом и соусом тар-тар.",
        "special_status": False,
        "available_in": (0, 1, 2),
    },
    {
        "name": "Шримп Ролл",
        "category": "Ролл",
        "price": "209.00",
        "description": "Ролл с креветками и сливочным соусом.",
        "special_status": True,
        "available_in": (0, 1),
    },
)

# Адреса доставки демо-заказов. Координаты кладём в кэш геокодера, чтобы
# страница менеджера показывала расстояния без обращения к Яндексу.
DEMO_ADDRESSES = {
    "Москва, ул. Тверская, 7": (55.7577, 37.6096),
    "Москва, ул. Арбат, 24": (55.7500, 37.5939),
    "Москва, Ленинский проспект, 30": (55.7100, 37.5900),
    "Москва, ул. Красная Пресня, 24": (55.7600, 37.5600),
    "Москва, Кутузовский проспект, 12": (55.7500, 37.5500),
    "Москва, ул. Покровка, 12": (55.7590, 37.6450),
}

DEMO_ORDERS: tuple[OrderData, ...] = (
    {
        "firstname": "Анна",
        "lastname": "Смирнова",
        "phonenumber": "+79161234567",
        "address": "Москва, ул. Тверская, 7",
        "status": Order.Status.UNPROCESSED,
        "payment_method": Order.PaymentMethod.ELECTRONIC,
        "comment": "Без лука, пожалуйста",
        "items": ((0, 1), (4, 2)),
    },
    {
        "firstname": "Илья",
        "lastname": "Петров",
        "phonenumber": "+79162345678",
        "address": "Москва, ул. Арбат, 24",
        "status": Order.Status.UNPROCESSED,
        "payment_method": Order.PaymentMethod.CASH,
        "comment": "",
        "items": ((1, 1), (5, 1)),
    },
    {
        "firstname": "Мария",
        "lastname": "Кузнецова",
        "phonenumber": "+79163456789",
        "address": "Москва, Ленинский проспект, 30",
        "status": Order.Status.UNPROCESSED,
        "payment_method": None,
        "comment": "Позвонить за 10 минут",
        "items": ((2, 1),),
    },
    {
        "firstname": "Дмитрий",
        "lastname": "Волков",
        "phonenumber": "+79164567890",
        "address": "Москва, ул. Красная Пресня, 24",
        "status": Order.Status.ASSEMBLED,
        "payment_method": Order.PaymentMethod.CASH,
        "comment": "",
        "items": ((3, 2), (4, 1)),
    },
    {
        "firstname": "Ольга",
        "lastname": "Морозова",
        "phonenumber": "+79165678901",
        "address": "Москва, Кутузовский проспект, 12",
        "status": Order.Status.ASSEMBLED,
        "payment_method": Order.PaymentMethod.ELECTRONIC,
        "comment": "Приборы на два человека",
        "items": ((0, 2), (5, 1)),
    },
    {
        "firstname": "Сергей",
        "lastname": "Лебедев",
        "phonenumber": "+79166789012",
        "address": "Москва, ул. Покровка, 12",
        "status": Order.Status.DELIVERED,
        "payment_method": Order.PaymentMethod.ELECTRONIC,
        "comment": "",
        "items": ((1, 3),),
    },
)


class Command(BaseCommand):
    help = "Создаёт демонстрационные рестораны, меню, заказы и демо-менеджера."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="demo",
            help="Логин демо-менеджера (по умолчанию: demo).",
        )
        parser.add_argument(
            "--password",
            default=None,
            help=(
                "Пароль демо-менеджера. По умолчанию берётся из "
                f"{DEMO_PASSWORD_ENV} или {DEFAULT_PASSWORD!r}."
            ),
        )
        parser.add_argument(
            "--orders",
            type=int,
            default=0,
            help=(
                "Сколько демо-заказов создать. Работает, только если заказов "
                "в базе ещё нет."
            ),
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            restaurants = self._seed_restaurants()
            categories = self._seed_categories()
            products = self._seed_products(categories)
            self._seed_menu(restaurants, products)
            self._seed_places()
            self._seed_manager(options)
            created_orders = self._seed_orders(products, options["orders"])

        self.stdout.write(
            self.style.SUCCESS(
                "Демо-данные готовы: "
                f"ресторанов {len(restaurants)}, "
                f"категорий {len(categories)}, "
                f"товаров {len(products)}, "
                f"заказов создано {created_orders}."
            )
        )

    def _seed_restaurants(self) -> list[Restaurant]:
        restaurants = []
        for data in RESTAURANTS:
            restaurant, _ = Restaurant.objects.update_or_create(
                name=data["name"],
                defaults={
                    "address": data["address"],
                    "contact_phone": data["contact_phone"],
                },
            )
            restaurants.append(restaurant)
        return restaurants

    def _seed_categories(self) -> dict[str, ProductCategory]:
        categories = {}
        for title in dict.fromkeys(p["category"] for p in PRODUCTS):
            category, _ = ProductCategory.objects.get_or_create(name=title)
            categories[title] = category
        return categories

    def _seed_products(
        self, categories: dict[str, ProductCategory]
    ) -> list[Product]:
        products = []
        for index, data in enumerate(PRODUCTS):
            product = Product.objects.filter(name=data["name"]).first()
            if product is None:
                product = Product(
                    name=data["name"],
                    category=categories[data["category"]],
                    price=Decimal(data["price"]),
                    description=data["description"],
                    special_status=data["special_status"],
                )
                product.image.save(
                    f"demo-{index + 1}.jpg",
                    self._placeholder_image(data["name"]),
                    save=False,
                )
                product.save()
                self.stdout.write(f"  + товар «{data['name']}»")
            products.append(product)
        return products

    def _seed_menu(self, restaurants, products) -> None:
        for data, product in zip(PRODUCTS, products, strict=True):
            for restaurant_index, restaurant in enumerate(restaurants):
                RestaurantMenuItem.objects.update_or_create(
                    restaurant=restaurant,
                    product=product,
                    defaults={
                        "availability": restaurant_index
                        in data["available_in"]
                    },
                )

    def _seed_places(self) -> None:
        for data in RESTAURANTS:
            lat, lon = data["coordinates"]
            Place.objects.update_or_create(
                address=data["address"],
                defaults={"lat": lat, "lon": lon},
            )
        for address, (lat, lon) in DEMO_ADDRESSES.items():
            Place.objects.update_or_create(
                address=address,
                defaults={"lat": lat, "lon": lon},
            )

    def _seed_manager(self, options) -> None:
        username = options["username"]
        explicit_password = options["password"]
        password = (
            explicit_password
            or os.environ.get(DEMO_PASSWORD_ENV)
            or DEFAULT_PASSWORD
        )
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        if created or explicit_password:
            user.set_password(password)
        # Демо-аккаунт открывает панель менеджера (нужен is_staff), но не
        # должен иметь доступ к админке: она умеет менять и удалять данные.
        user.is_staff = True
        user.is_superuser = False
        user.save()

        self.stdout.write(
            f"  демо-менеджер «{username}»: "
            f"{'создан' if created else 'уже существует'}"
        )
        if created or explicit_password:
            self.stdout.write(f"  пароль: {password}")

    def _seed_orders(self, products, count: int) -> int:
        if count <= 0:
            return 0
        if Order.objects.exists():
            self.stdout.write(
                "  заказы уже есть — демо-заказы не создаю (нужна пустая база)"
            )
            return 0

        created = 0
        for data in DEMO_ORDERS[:count]:
            order = Order.objects.create(
                firstname=data["firstname"],
                lastname=data["lastname"],
                phonenumber=data["phonenumber"],
                address=data["address"],
                status=data["status"],
                payment_method=data["payment_method"],
                comment=data["comment"],
            )
            for product_index, quantity in data["items"]:
                product = products[product_index]
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=product.price,
                )
            created += 1
        return created

    @staticmethod
    def _placeholder_image(name: str) -> ContentFile:
        """Рисует картинку-заглушку, если у товара нет фотографии."""
        width, height = 640, 420
        image = Image.new("RGB", (width, height), "#f7ede2")
        draw = ImageDraw.Draw(image)
        draw.ellipse((width - 300, -120, width + 80, 260), fill="#fbdcc4")
        draw.ellipse((-90, height - 150, 160, height + 90), fill="#f3c9a8")
        draw.rectangle((0, height - 74, width, height), fill="#111827")
        title_font = _load_font(46)
        brand_font = _load_font(26)
        draw.text((44, height - 190), name, font=title_font, fill="#111827")
        draw.text(
            (44, height - 54),
            "Star Burger",
            font=brand_font,
            fill="#f9fafb",
        )
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=88)
        return ContentFile(buffer.getvalue())


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    )
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)
