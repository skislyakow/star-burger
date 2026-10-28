"""Геокодер: кэш в `Place`, разбор ответа Яндекса и молчаливые отказы."""

from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

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


def make_stale(place: Place, *, days: int) -> None:
    """Сдвигает дату запроса в прошлое, не трогая auto_now."""
    Place.objects.filter(pk=place.pk).update(
        requested_at=timezone.localdate() - timedelta(days=days)
    )
    place.refresh_from_db()


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


def test_failed_lookup_returns_none_and_is_cached(monkeypatch):
    requested = []

    def fail(address, apikey):
        requested.append(address)
        raise geocoder.GeocoderError("не нашёл")

    monkeypatch.setattr(geocoder, "fetch_coordinates", fail)

    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: None}
    assert requested == [MOSCOW]

    # Повторный запрос в тот же день не должен снова идти в Яндекс.
    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: None}
    assert requested == [MOSCOW]

    place = Place.objects.get(address=MOSCOW)
    assert (place.lat, place.lon) == (None, None)


def test_cached_place_without_coordinates_is_not_refetched(monkeypatch):
    Place.objects.create(address=MOSCOW)

    def fail(*args, **kwargs):
        raise AssertionError("точка без координат уже в кэше")

    monkeypatch.setattr(geocoder, "fetch_coordinates", fail)

    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: None}


def test_stale_coordinates_are_refetched(monkeypatch):
    place = Place.objects.create(address=MOSCOW, lat=55.75, lon=37.61)
    make_stale(place, days=31)
    monkeypatch.setattr(
        geocoder, "fetch_coordinates", lambda address, apikey: (55.8, 37.5)
    )

    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: (55.8, 37.5)}

    place.refresh_from_db()
    assert (place.lat, place.lon) == (55.8, 37.5)
    assert place.requested_at == timezone.localdate()


def test_coordinates_within_ttl_are_not_refetched(monkeypatch):
    place = Place.objects.create(address=MOSCOW, lat=55.75, lon=37.61)
    make_stale(place, days=29)

    def fail(*args, **kwargs):
        raise AssertionError("координаты ещё не просрочены")

    monkeypatch.setattr(geocoder, "fetch_coordinates", fail)

    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: (55.75, 37.61)}


@override_settings(GEOCODER_CACHE_TTL_DAYS=1)
def test_freshness_follows_configured_ttl(monkeypatch):
    place = Place.objects.create(address=MOSCOW, lat=55.75, lon=37.61)
    make_stale(place, days=2)
    monkeypatch.setattr(
        geocoder, "fetch_coordinates", lambda address, apikey: (55.8, 37.5)
    )

    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: (55.8, 37.5)}


def test_stale_negative_cache_is_retried(monkeypatch):
    place = Place.objects.create(address=MOSCOW)
    make_stale(place, days=2)
    monkeypatch.setattr(
        geocoder, "fetch_coordinates", lambda address, apikey: (55.8, 37.5)
    )

    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: (55.8, 37.5)}

    place.refresh_from_db()
    assert (place.lat, place.lon) == (55.8, 37.5)


def test_stale_coordinates_survive_failed_refresh(monkeypatch):
    place = Place.objects.create(address=MOSCOW, lat=55.75, lon=37.61)
    make_stale(place, days=31)

    def fail(address, apikey):
        raise geocoder.GeocoderError("Яндекс недоступен")

    monkeypatch.setattr(geocoder, "fetch_coordinates", fail)

    assert geocoder.get_coordinates_map([MOSCOW]) == {MOSCOW: (55.75, 37.61)}

    place.refresh_from_db()
    assert (place.lat, place.lon) == (55.75, 37.61)
    assert place.requested_at == timezone.localdate()


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
