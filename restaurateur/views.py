from django import forms
from django.shortcuts import redirect, render
from django.views import View
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.db.models import Case, When, Value, IntegerField
from geopy.distance import distance

from places.geocoder import get_coordinates_map
from foodcartapp.models import Order, Product, Restaurant, RestaurantMenuItem


class Login(forms.Form):
    username = forms.CharField(
        label="Логин",
        max_length=75,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Укажите имя пользователя",
            }
        ),
    )
    password = forms.CharField(
        label="Пароль",
        max_length=75,
        required=True,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Введите пароль"}
        ),
    )


class LoginView(View):
    def get(self, request, *args, **kwargs):
        form = Login()
        return render(request, "login.html", context={"form": form})

    def post(self, request):
        form = Login(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            user = authenticate(request, username=username, password=password)
            if isinstance(user, User):
                login(request, user)
                if user.is_staff:  # FIXME replace with specific permission
                    return redirect("restaurateur:RestaurantView")
                return redirect("start_page")

        return render(
            request,
            "login.html",
            context={
                "form": form,
                "ivalid": True,
            },
        )


class LogoutView(auth_views.LogoutView):
    next_page = "restaurateur:login"


def is_manager(user):
    return user.is_staff  # FIXME replace with specific permission


@user_passes_test(is_manager, login_url="restaurateur:login")
def view_products(request):
    restaurants = list(Restaurant.objects.order_by("name"))
    products = list(Product.objects.prefetch_related("menu_items"))

    products_with_restaurant_availability = []
    for product in products:
        availability = {
            item.restaurant_id: item.availability
            for item in product.menu_items.all()  # type: ignore[attr-defined]
        }
        ordered_availability = [
            availability.get(restaurant.id, False)
            for restaurant in restaurants
        ]

        products_with_restaurant_availability.append(
            (product, ordered_availability)
        )

    return render(
        request,
        template_name="products_list.html",
        context={
            "products_with_restaurant_availability": products_with_restaurant_availability,
            "restaurants": restaurants,
        },
    )


@user_passes_test(is_manager, login_url="restaurateur:login")
def view_restaurants(request):
    return render(
        request,
        template_name="restaurants_list.html",
        context={
            "restaurants": Restaurant.objects.all(),
        },
    )


def get_open_orders():
    return (
        Order.objects.exclude(status=Order.Status.COMPLETED)
        .select_related("restaurant")
        .prefetch_related("items")
        .with_total_cost()  # type: ignore[attr-defined]
        .annotate(
            priority=Case(
                When(status=Order.Status.UNPROCESSED, then=Value(0)),
                When(status=Order.Status.ASSEMBLED, then=Value(1)),
                When(status=Order.Status.DELIVERED, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        )
        .order_by("priority", "-created_at")
    )


def load_restaurants() -> dict[int, Restaurant]:
    return {r.id: r for r in Restaurant.objects.all()}


def load_restaurants_for_product() -> dict[int, set[int]]:
    menu_items = RestaurantMenuItem.objects.filter(
        availability=True
    ).values_list("product_id", "restaurant_id")
    result = {}
    for product_id, restaurant_id in menu_items:
        result.setdefault(product_id, set()).add(restaurant_id)
    return result


def available_restaurants_for_order(
    order, restaurants_for_product
) -> set[int]:
    available = None
    for item in order.items.all():
        restaurants = restaurants_for_product.get(item.product_id, set())
        available = (
            restaurants if available is None else (available & restaurants)
        )
        if not available:
            break
    return available or set()


def distance_km(a, b) -> float | None:
    if a and b:
        return distance(a, b).km
    return None


def restaurant_offers(
    order, restaurants_by_id, coordinates_by_address, restaurants_for_product
):
    order_coordinates = coordinates_by_address.get(order.address)
    offers = []
    for restaurant_id in available_restaurants_for_order(
        order, restaurants_for_product
    ):
        restaurant = restaurants_by_id[restaurant_id]
        coords = coordinates_by_address.get(restaurant.address)
        offers.append(
            (restaurant.name, distance_km(order_coordinates, coords))
        )
    offers.sort(key=lambda entry: (entry[1] is None, entry[1] or 0, entry[0]))
    return offers


@user_passes_test(is_manager, login_url="restaurateur:login")
def view_orders(request):
    orders = list(get_open_orders())
    restaurants_by_id = load_restaurants()
    restaurants_for_product = load_restaurants_for_product()

    addresses = {order.address for order in orders}
    addresses.update(r.address for r in restaurants_by_id.values())
    coordinates_by_address = get_coordinates_map(addresses)

    order_info = [
        (
            order,
            restaurant_offers(
                order,
                restaurants_by_id,
                coordinates_by_address,
                restaurants_for_product,
            ),
            coordinates_by_address.get(order.address) is not None,
        )
        for order in orders
    ]
    return render(
        request,
        template_name="order_items.html",
        context={"order_items": order_info},
    )
