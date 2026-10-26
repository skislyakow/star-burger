from django.db import models


class Place(models.Model):
    address = models.CharField("адрес", max_length=200, unique=True)
    lat = models.FloatField("широта", null=True, blank=True)
    lon = models.FloatField("долгота", null=True, blank=True)
    requested_at = models.DateField("дата запроса к геокодеру", auto_now=True)

    def __str__(self):
        return self.address
