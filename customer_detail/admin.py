from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone_number', 'company_name', 'created_date')
    list_filter = ('created_date',)
    search_fields = ('full_name', 'email', 'phone_number', 'company_name', 'address')
    ordering = ('-created_date',)
    readonly_fields = ('created_date', 'updated_date')
