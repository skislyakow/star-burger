from django import forms
from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import redirect, render
from django.views import View

from foodcartapp.fulfillment import FulfillmentService
from foodcartapp.models import Order, Product, Restaurant


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


def product_availability_matrix(products, restaurants):
    matrix = []
    for product in products:
        availability = {
            item.restaurant_id: item.availability
            for item in product.menu_items.all()
        }
        ordered_availability = [
            availability.get(restaurant.id, False)
            for restaurant in restaurants
        ]
        matrix.append((product, ordered_availability))
    return matrix


@user_passes_test(is_manager, login_url="restaurateur:login")
def view_products(request):
    restaurants = list(Restaurant.objects.order_by("name"))
    products = list(Product.objects.prefetch_related("menu_items"))

    return render(
        request,
        template_name="products_list.html",
        context={
            "products_with_restaurant_availability": product_availability_matrix(
                products, restaurants
            ),
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


@user_passes_test(is_manager, login_url="restaurateur:login")
def view_orders(request):
    fulfillments = FulfillmentService().fulfillments(list(get_open_orders()))
    return render(
        request,
        template_name="order_items.html",
        context={"fulfillments": fulfillments},
    )
