from decimal import Decimal

from django.db import migrations, models
from django.core.validators import MinValueValidator


def backfill_prices(apps, schema_editor):
    OrderItem = apps.get_model("foodcartapp", "OrderItem")
    for item in OrderItem.objects.select_related("product").iterator():
        item.price = item.product.price
        item.save(update_fields=["price"])


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("foodcartapp", "0040_alter_order_created_at"),
    ]
    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="price",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                max_digits=8,
                validators=[MinValueValidator(0)],
                verbose_name="цена",
            ),
        ),
        migrations.RunPython(backfill_prices, reverse_backfill),
        migrations.AlterField(
            model_name="orderitem",
            name="price",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=8,
                validators=[MinValueValidator(0)],
                verbose_name="цена",
            ),
        ),
    ]
