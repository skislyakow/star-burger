from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("foodcartapp", "0038_order_orderitem"),
    ]

    def normalize_phonenumbers(apps, schema_editor):
        Order = apps.get_model("foodcartapp", "Order")
        for order in Order.objects.iterator():
            order.save()

    def reverse_func(apps, schema_editor):
        pass

    operations = [migrations.RunPython(normalize_phonenumbers, reverse_func)]
