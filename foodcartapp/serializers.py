from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["product", "quantity"]


class OrderProductsField(serializers.ListField):
    child = OrderItemSerializer()

    def __init__(self, **kwargs):
        kwargs.setdefault("allow_empty", False)
        kwargs.setdefault("error_messages", {}).update(
            {
                "required": "Обязательное поле.",
                "null": "Это поле не может быть пустым.",
                "empty": "Этот список не может быть пустым.",
                "not_a_list": 'Ожидался list со значениями, но был получен "{input_type}".',
            }
        )
        super().__init__(**kwargs)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    products = OrderProductsField(write_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "firstname",
            "lastname",
            "phonenumber",
            "address",
            "created_at",
            "items",
            "products",
        ]

    def create(self, validated_data):
        products = validated_data.pop("products")
        order = Order.objects.create(**validated_data)
        for product_data in products:
            OrderItem.objects.create(order=order, **product_data)
        return order
