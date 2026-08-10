from django.db import models


class Place(models.Model):
    address = models.CharField("адрес", max_length=200, unique=True)
    lat = models.FloatField("широта")
    lon = models.FloatField("долгота")
    requested_at = models.DateField("дата запроса к геокодеру", auto_now=True)
