"""Геокодер: кэш в `Place`, разбор ответа Яндекса и молчаливые отказы."""

import pytest

from places import geocoder
from places.models import Place

pytestmark = pytest.mark.django_db

MOSCOW = "Москва, Тверская, 1"
OTHER = "Москва, Арбат, 1"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def yandex_payload(*positions):
    return {
        "response": {
            "GeoObjectCollection": {
                "featureMember": [
                    {"GeoObject": {"Point": {"pos": position}}}
                    for position in positions
                ]
            }
        }
    }


def test_cached_coordinates_do_not_hit_network(monkeypatch):
    Place.objects.create(address=MOSCOW, lat=55.75, lon=37.61)

    def fail(*args, **kwargs):
        raise AssertionError("кэш должен был отменить запрос в сеть")

    monkeypatch.setattr(geocoder, "fetch_coordinates", fail)

    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: (55.75, 37.61)}


def test_missing_address_is_fetched_and_stored(monkeypatch):
    monkeypatch.setattr(
        geocoder, "fetch_coordinates", lambda address, apikey: (55.7, 37.6)
    )

    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: (55.7, 37.6)}

    place = Place.objects.get(address=MOSCOW)
    assert (place.lat, place.lon) == (55.7, 37.6)


def test_only_missing_addresses_are_fetched(monkeypatch):
    Place.objects.create(address=MOSCOW, lat=55.75, lon=37.61)
    requested = []

    def fake_fetch(address, apikey):
        requested.append(address)
        return (55.8, 37.5)

    monkeypatch.setattr(geocoder, "fetch_coordinates", fake_fetch)

    geocoder.get_coordinates_map([MOSCOW, OTHER])

    assert requested == [OTHER]


def test_failed_lookup_returns_none_and_stores_nothing(monkeypatch):
    def fail(address, apikey):
        raise geocoder.GeocoderError("не нашёл")

    monkeypatch.setattr(geocoder, "fetch_coordinates", fail)

    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: None}
    assert Place.objects.count() == 0


def test_cached_place_without_coordinates_is_not_refetched(monkeypatch):
    Place.objects.create(address=MOSCOW)

    def fail(*args, **kwargs):
        raise AssertionError("точка без координат уже в кэше")

    monkeypatch.setattr(geocoder, "fetch_coordinates", fail)

    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: None}


def test_fetch_coordinates_parses_yandex_response(monkeypatch):
    monkeypatch.setattr(
        geocoder.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(yandex_payload("37.61 55.75")),
    )

    assert geocoder.fetch_coordinates(MOSCOW, "key") == (55.75, 37.61)


def test_fetch_coordinates_raises_when_nothing_found(monkeypatch):
    monkeypatch.setattr(
        geocoder.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(yandex_payload()),
    )

    with pytest.raises(geocoder.GeocoderError):
        geocoder.fetch_coordinates(MOSCOW, "key")
