from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Supplier, Category, Country, State
from .forms import SupplierForm


# ─── AJAX: Load States by Country ─────────────────────────────────────────────
def load_states(request):
    country_id = request.GET.get('country_id')
    if not country_id:
        return JsonResponse({'states': []})
    states = State.objects.filter(country_id=country_id).order_by('name').values('id', 'name')
    return JsonResponse({'states': list(states)})


# ─── Supplier List ─────────────────────────────────────────────────────────────
@login_required
def supplier_list(request):
    suppliers = Supplier.objects.select_related('category', 'country', 'state').all()
    category_id = request.GET.get('category')
    country_id  = request.GET.get('country')
    state_id    = request.GET.get('state')

    if category_id:
        suppliers = suppliers.filter(category_id=category_id)
    if country_id:
        suppliers = suppliers.filter(country_id=country_id)
    if state_id:
        suppliers = suppliers.filter(state_id=state_id)

    context = {
        'suppliers': suppliers,
        'categories': Category.objects.all(),
        'countries': Country.objects.all(),
        'states': State.objects.all(),
        'selected_category': category_id,
        'selected_country': country_id,
        'selected_state': state_id,
    }
    return render(request, 'supplier_management/supplier_list.html', context)


# ─── Add Supplier ──────────────────────────────────────────────────────────────
@login_required
def supplier_add(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier added successfully!')
            return redirect('supplier_management:supplier_list')
    else:
        form = SupplierForm()
    return render(request, 'supplier_management/supplier_form.html', {
        'form': form,
        'title': 'Add New Supplier',
        'btn_label': 'Add Supplier',
    })


# ─── Edit Supplier ─────────────────────────────────────────────────────────────
@login_required
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier updated successfully!')
            return redirect('supplier_management:supplier_list')
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'supplier_management/supplier_form.html', {
        'form': form,
        'title': f'Edit Supplier: {supplier.name}',
        'btn_label': 'Save Changes',
        'supplier': supplier,
    })


# ─── Delete Supplier ───────────────────────────────────────────────────────────
@login_required
@require_POST
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.delete()
    messages.success(request, f'"{supplier.name}" deleted successfully!')
    return redirect('supplier_management:supplier_list')


# ══════════════════════════════════════════════════════════════════════════════
# ─── MANAGE DATA PAGE (Category / Country / State) ───────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def manage_data(request):
    """Single page to manage all reference data: Categories, Countries, States."""
    context = {
        'categories': Category.objects.all().order_by('name'),
        'countries':  Country.objects.all().order_by('name'),
        'states':     State.objects.select_related('country').all().order_by('country__name', 'name'),
        'active_tab': request.GET.get('tab', 'categories'),
    }
    return render(request, 'supplier_management/manage_data.html', context)


# ── Category CRUD ──────────────────────────────────────────────────────────────
@login_required
@require_POST
def category_add(request):
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Category name cannot be empty.')
    elif Category.objects.filter(name__iexact=name).exists():
        messages.error(request, f'Category "{name}" already exists.')
    else:
        Category.objects.create(name=name)
        messages.success(request, f'Category "{name}" added successfully!')
    return redirect('/suppliers/manage/?tab=categories')


@login_required
@require_POST
def category_delete(request, pk):
    cat = get_object_or_404(Category, pk=pk)
    name = cat.name
    cat.delete()
    messages.success(request, f'Category "{name}" deleted.')
    return redirect('/suppliers/manage/?tab=categories')


# ── Country CRUD ───────────────────────────────────────────────────────────────
@login_required
@require_POST
def country_add(request):
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Country name cannot be empty.')
    elif Country.objects.filter(name__iexact=name).exists():
        messages.error(request, f'Country "{name}" already exists.')
    else:
        Country.objects.create(name=name)
        messages.success(request, f'Country "{name}" added successfully!')
    return redirect('/suppliers/manage/?tab=countries')


@login_required
@require_POST
def country_delete(request, pk):
    country = get_object_or_404(Country, pk=pk)
    name = country.name
    country.delete()
    messages.success(request, f'Country "{name}" deleted.')
    return redirect('/suppliers/manage/?tab=countries')


# ── State CRUD ─────────────────────────────────────────────────────────────────
@login_required
@require_POST
def state_add(request):
    name       = request.POST.get('name', '').strip()
    country_id = request.POST.get('country_id', '').strip()
    if not name or not country_id:
        messages.error(request, 'State name and country are required.')
    else:
        country = get_object_or_404(Country, pk=country_id)
        if State.objects.filter(name__iexact=name, country=country).exists():
            messages.error(request, f'State "{name}" already exists in {country.name}.')
        else:
            State.objects.create(name=name, country=country)
            messages.success(request, f'State "{name}" added to {country.name}!')
    return redirect('/suppliers/manage/?tab=states')


@login_required
@require_POST
def state_delete(request, pk):
    state = get_object_or_404(State, pk=pk)
    name = state.name
    state.delete()
    messages.success(request, f'State "{name}" deleted.')
    return redirect('/suppliers/manage/?tab=states')
