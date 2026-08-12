from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from django.core.validators import MinValueValidator
from django.db.models import F, Sum, Value, DecimalField
from django.db.models.functions import Coalesce


class Restaurant(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField("название", max_length=50)
    address = models.CharField(
        "адрес",
        max_length=100,
        blank=True,
    )
    contact_phone = models.CharField(
        "контактный телефон",
        max_length=50,
        blank=True,
    )

    class Meta:
        verbose_name = "ресторан"
        verbose_name_plural = "рестораны"

    def __str__(self):
        return self.name


class ProductCategory(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField("название", max_length=50)

    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "категории"

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available(self):
        products = RestaurantMenuItem.objects.filter(
            availability=True
        ).values_list("product")
        return self.filter(pk__in=products)


class ProductManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return ProductQuerySet(self.model, using=self._db)


class Product(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField("название", max_length=50)
    category = models.ForeignKey(
        ProductCategory,
        verbose_name="категория",
        related_name="products",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    price = models.DecimalField(
        "цена",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    image = models.ImageField("картинка")
    special_status = models.BooleanField(
        "спец.предложение",
        default=False,
        db_index=True,
    )
    description = models.TextField(
        "описание",
        max_length=200,
        blank=True,
    )

    objects = ProductManager()

    class Meta:
        verbose_name = "товар"
        verbose_name_plural = "товары"

    def __str__(self):
        return self.name


class OrderQuerySet(models.QuerySet):
    def with_total_cost(self):
        return self.annotate(
            total_cost=Coalesce(
                Sum(F("items__quantity") * F("items__price")),
                Value(
                    0,
                    output_field=DecimalField(max_digits=8, decimal_places=2),
                ),
            )
        )


class Order(models.Model):
    id = models.AutoField(primary_key=True)
    firstname = models.CharField(
        "имя",
        max_length=50,
    )
    lastname = models.CharField(
        "фамилия",
        max_length=50,
    )
    phonenumber = PhoneNumberField(
        "телефон",
        db_index=True,
    )
    address = models.CharField(
        "адрес",
        max_length=200,
    )
    created_at = models.DateTimeField(
        "создан",
        auto_now_add=True,
        db_index=True,
    )

    class Status(models.TextChoices):
        UNPROCESSED = "unprocessed", "Необработанный"
        ASSEMBLED = "assembled", "Собран"
        DELIVERED = "delivered", "Доставлен"
        COMPLETED = "completed", "Выполнен"

    status = models.CharField(
        "статус",
        max_length=30,
        choices=Status.choices,
        default=Status.UNPROCESSED,
        db_index=True,
    )

    comment = models.TextField(
        "комментарий",
        blank=True,
        default="",
    )

    called_at = models.DateField(
        "Дата звонка",
        null=True,
        blank=True,
        db_index=True,
    )

    delivered_at = models.DateTimeField(
        "дата доставки",
        null=True,
        blank=True,
        db_index=True,
    )

    class PaymentMethod(models.TextChoices):
        ELECTRONIC = "electronic", "Электронно"
        CASH = "cash", "Наличными"

    payment_method = models.CharField(
        "способ оплаты",
        max_length=30,
        choices=PaymentMethod.choices,
        null=True,
        blank=True,
        db_index=True,
    )

    restaurant = models.ForeignKey(
        Restaurant,
        related_name="orders",
        verbose_name="ресторан",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    objects = OrderQuerySet.as_manager()

    class Meta:
        verbose_name = "заказ"
        verbose_name_plural = "заказы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Заказ #{self.id}: {self.firstname} {self.lastname}"


class OrderItem(models.Model):
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(
        Order,
        related_name="items",
        on_delete=models.CASCADE,
        verbose_name="заказ",
    )
    product = models.ForeignKey(
        Product,
        related_name="order_items",
        on_delete=models.CASCADE,
        verbose_name="товар",
    )
    quantity = models.PositiveIntegerField(
        "количество",
        validators=[MinValueValidator(1)],
    )
    price = models.DecimalField(
        "цена",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        verbose_name = "позиция заказа"
        verbose_name_plural = "позиции заказа"

    def __str__(self):
        return f"{self.product.name} * {self.quantity}"


class RestaurantMenuItem(models.Model):
    id = models.AutoField(primary_key=True)
    restaurant = models.ForeignKey(
        Restaurant,
        related_name="menu_items",
        verbose_name="ресторан",
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="menu_items",
        verbose_name="продукт",
    )
    availability = models.BooleanField(
        "в продаже", default=True, db_index=True
    )

    class Meta:
        verbose_name = "пункт меню ресторана"
        verbose_name_plural = "пункты меню ресторана"
        unique_together = [["restaurant", "product"]]

    def __str__(self):
        return f"{self.restaurant.name} - {self.product.name}"
