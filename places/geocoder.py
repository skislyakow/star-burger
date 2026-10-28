"""Кэш координат в `Place` и клиент Яндекс.Геокодера.

Удачные ответы живут месяц: адреса ресторанов и клиентов меняются редко,
а лишний запрос к внешнему API стоит квоты и времени. Неудачные — сутки:
если Яндекс не разобрал адрес, нет смысла спрашивать его на каждом
открытии страницы менеджера, но и вечно хранить отказ нельзя.

Когда срок удачного ответа истёк, координаты запрашиваются заново. Если
Яндекс в этот момент недоступен, страница продолжает показывать старые
координаты: лучше чуть устаревшее расстояние, чем никакого.
"""

from datetime import date, timedelta

import requests
from django.conf import settings
from django.utils import timezone

from places.models import Place


class GeocoderError(Exception):
    pass


def fetch_coordinates(address, apikey):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(
        base_url,
        params={"geocode": address, "apikey": apikey, "format": "json"},
        timeout=10,
    )
    response.raise_for_status()
    found_places = response.json()["response"]["GeoObjectCollection"][
        "featureMember"
    ]
    if not found_places:
        raise GeocoderError("Геокодер не нашёл координаты")
    most_relevant = found_places[0]
    lon, lat = most_relevant["GeoObject"]["Point"]["pos"].split(" ")
    return float(lat), float(lon)


def _fetch_coordinates_safe(address) -> tuple[float, float] | None:
    try:
        return fetch_coordinates(address, settings.YANDEX_GEOCODER_API_KEY)
    except (
        GeocoderError,
        requests.exceptions.RequestException,
        KeyError,
        IndexError,
        ValueError,
    ):
        return None


def _coordinates(place: Place | None) -> tuple[float, float] | None:
    if place is None or place.lat is None or place.lon is None:
        return None
    return place.lat, place.lon


def _is_fresh(place: Place, today: date) -> bool:
    ttl_days = (
        settings.GEOCODER_CACHE_TTL_DAYS
        if _coordinates(place) is not None
        else settings.GEOCODER_NEGATIVE_TTL_DAYS
    )
    return (
        place.requested_at is not None
        and place.requested_at > today - timedelta(days=ttl_days)
    )


def get_coordinates_map(addresses) -> dict[str, tuple[float, float] | None]:
    addresses = set(addresses)
    places = {
        place.address: place
        for place in Place.objects.filter(address__in=addresses)
    }
    today = timezone.localdate()
    coordinates_by_address: dict[str, tuple[float, float] | None] = {}

    for address in addresses:
        place = places.get(address)
        if place is not None and _is_fresh(place, today):
            coordinates_by_address[address] = _coordinates(place)
            continue

        coordinates = _fetch_coordinates_safe(address)
        if coordinates is None:
            coordinates_by_address[address] = _coordinates(place)
            if place is None:
                Place.objects.create(address=address)
            else:
                place.save(update_fields=["requested_at"])
            continue

        coordinates_by_address[address] = coordinates
        if place is None:
            Place.objects.create(
                address=address, lat=coordinates[0], lon=coordinates[1]
            )
        else:
            place.lat, place.lon = coordinates
            place.save(update_fields=["lat", "lon", "requested_at"])

    return coordinates_by_address
