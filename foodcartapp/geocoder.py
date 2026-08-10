import hashlib

import requests
from django.conf import settings
from django.core.cache import cache


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


def _cache_key(address):
    digest = hashlib.sha1(address.encode("utf-8")).hexdigest()
    return f"geocoder:{digest}"


def get_coordinates(address):
    key = _cache_key(address)
    coordinates = cache.get(key)
    if coordinates:
        return coordinates
    try:
        coordinates = fetch_coordinates(
            address, settings.YANDEX_GEOCODER_API_KEY
        )
    except (
        GeocoderError,
        requests.exceptions.RequestException,
        KeyError,
        IndexError,
        ValueError,
    ):
        return None
    cache.set(key, coordinates, timeout=3600)
    return coordinates
