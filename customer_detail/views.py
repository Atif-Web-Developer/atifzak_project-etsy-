from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import Customer
from .forms import CustomerForm


def customer_dashboard(request):
    """Dashboard view showing stats and recently added customers."""
    total_customers = Customer.objects.count()
    recent_customers = Customer.objects.order_by('-created_date')[:5]

    # Customers added in the last 7 days
    seven_days_ago = timezone.now() - timedelta(days=7)
    new_this_week = Customer.objects.filter(created_date__gte=seven_days_ago).count()

    # Customers added in the last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    new_this_month = Customer.objects.filter(created_date__gte=thirty_days_ago).count()

    context = {
        'total_customers': total_customers,
        'recent_customers': recent_customers,
        'new_this_week': new_this_week,
        'new_this_month': new_this_month,
    }
    return render(request, 'customer_detail/dashboard.html', context)


def customer_list(request):
    """View to list all customers with search functionality and date filter."""
    query = request.GET.get('q', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    customers = Customer.objects.all()

    if query:
        customers = customers.filter(
            Q(full_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(company_name__icontains=query) |
            Q(address__icontains=query) |
            Q(notes__icontains=query)
        )

    if start_date:
        customers = customers.filter(created_date__gte=start_date + " 00:00:00")
    if end_date:
        customers = customers.filter(created_date__lte=end_date + " 23:59:59")

    context = {
        'customers': customers,
        'query': query,
        'start_date': start_date,
        'end_date': end_date,
        'total_results': customers.count(),
    }
    return render(request, 'customer_detail/customer_list.html', context)


def customer_create(request):
    """View to create a new customer."""
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Customer "{customer.full_name}" has been created successfully!')
            return redirect('customer_detail:customer_list')
    else:
        form = CustomerForm()

    context = {'form': form, 'title': 'Add New Customer'}
    return render(request, 'customer_detail/customer_form.html', context)


def customer_update(request, pk):
    """View to update an existing customer."""
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f'Customer "{customer.full_name}" has been updated successfully!')
            return redirect('customer_detail:customer_list')
    else:
        form = CustomerForm(instance=customer)

    context = {'form': form, 'title': 'Edit Customer', 'customer': customer}
    return render(request, 'customer_detail/customer_form.html', context)


def customer_delete(request, pk):
    """View to delete a customer."""
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        name = customer.full_name
        customer.delete()
        messages.success(request, f'Customer "{name}" has been deleted successfully!')
        return redirect('customer_detail:customer_list')
    context = {'customer': customer}
    return render(request, 'customer_detail/customer_confirm_delete.html', context)


def customer_view(request, pk):
    """View to display a single customer's full details."""
    customer = get_object_or_404(Customer, pk=pk)
    context = {'customer': customer}
    return render(request, 'customer_detail/customer_view.html', context)
