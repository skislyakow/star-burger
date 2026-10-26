"""`/healthz/`: мониторинг видит и процесс, и базу."""

import pytest
from django.db import OperationalError
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_healthz_reports_ok(client):
    response = client.get(reverse("healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_reports_database_failure(client, monkeypatch):
    class BrokenConnection:
        def cursor(self):
            raise OperationalError("database is down")

    monkeypatch.setattr("star_burger.views.connection", BrokenConnection())

    response = client.get(reverse("healthz"))

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
