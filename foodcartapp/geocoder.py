import requests
from django.conf import settings

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


def _fetch_coordinates_safe(address):
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


def get_coordinates_map(addresses):
    addresses = set(addresses)
    coordinates_by_address = {
        address: (lat, lon)
        for address, lat, lon in Place.objects.filter(
            address__in=addresses
        ).values_list("address", "lat", "lon")
    }

    missing = addresses - set(coordinates_by_address)
    new_places = []
    for address in missing:
        coordinates = _fetch_coordinates_safe(address)
        coordinates_by_address[address] = coordinates
        if coordinates:
            new_places.append(
                Place(address=address, lat=coordinates[0], lon=coordinates[1])
            )
    if new_places:
        Place.objects.bulk_create(new_places, ignore_conflicts=True)
    return coordinates_by_address
