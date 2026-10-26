from rest_framework import serializers

from .models import Order, OrderItem
from .orders import OrderError, OrderLine, place_order


class OrderItemSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True
    )

    class Meta:
        model = OrderItem
        fields = ["product", "quantity", "price"]


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
        try:
            return place_order(
                **validated_data,
                lines=[
                    OrderLine(
                        product_id=item["product"].id,
                        quantity=item["quantity"],
                    )
                    for item in products
                ],
            )
        except OrderError as error:
            raise serializers.ValidationError(
                {"products": str(error)}
            ) from error
