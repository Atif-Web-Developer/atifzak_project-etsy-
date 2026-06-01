from django.db import models


class Customer(models.Model):
    """Model to store customer details permanently."""
    full_name = models.CharField(max_length=200, verbose_name='Full Name')
    phone_number = models.CharField(max_length=30, blank=True, verbose_name='Phone Number')
    email = models.EmailField(max_length=254, blank=True, verbose_name='Email Address')
    company_name = models.CharField(max_length=200, blank=True, verbose_name='Company Name')
    address = models.TextField(blank=True, verbose_name='Address')
    notes = models.TextField(blank=True, verbose_name='Notes')
    created_date = models.DateTimeField(auto_now_add=True, verbose_name='Created Date')
    updated_date = models.DateTimeField(auto_now=True, verbose_name='Last Updated')

    class Meta:
        ordering = ['-created_date']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return self.full_name
