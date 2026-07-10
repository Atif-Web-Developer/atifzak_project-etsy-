from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Country(models.Model):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        verbose_name_plural = 'Countries'
        ordering = ['name']

    def __str__(self):
        return self.name


class State(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='states')
    name = models.CharField(max_length=200)

    class Meta:
        ordering = ['name']
        unique_together = ('country', 'name')

    def __str__(self):
        return f"{self.name}, {self.country.name}"


class Supplier(models.Model):
    name = models.CharField(max_length=300)
    link = models.URLField(max_length=500)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='suppliers')
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, related_name='suppliers')
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True, related_name='suppliers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name
