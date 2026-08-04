from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["product", "quantity"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    products = OrderItemSerializer(many=True, write_only=True)

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
