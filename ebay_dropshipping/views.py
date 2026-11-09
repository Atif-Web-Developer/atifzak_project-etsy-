from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

from django.contrib import messages
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .columns import COLUMNS
from .forms import NEW_TAB, ConnectionForm, FeeSettingsForm, ProductForm
from .models import DropshipSettings, Product, UserTabPreference
from . import sheets

SCRIPT_DIR = Path(__file__).resolve().parent / 'google_apps_script'
TOOL_JS = Path(__file__).resolve().parent / 'static' / 'ebay_dropshipping' / 'js' / 'ebay-tool.js'
BOOKMARKLET_JS = Path(__file__).resolve().parent / 'static' / 'ebay_dropshipping' / 'js' / 'bookmarklet.js'
DEFAULT_TAB = 'Products'
DEFAULT_SUGGESTED_TAB = 'eBay Products'
TABS_CACHE_KEY = 'ebay-sheet-tabs'


def _wants_json(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json'


def _available_tabs(conf, refresh=False):
    """
    Tabs from the Google Sheet (cached for a minute) merged with tabs already used in Django.
    Returns (all tab names, set of blocked names) – blocked tabs hold other data in the sheet.
    """
    info = []
    if conf.sheet_connected:
        info = None if refresh else cache.get(TABS_CACHE_KEY)
        if info is None:
            try:
                info = sheets.list_tabs(conf)
                cache.set(TABS_CACHE_KEY, info, 60)
            except sheets.SheetError:
                info = []
    blocked = {t['name'] for t in info if not t['usable']}
    known = list(Product.objects.order_by().values_list('tab', flat=True).distinct())
    merged = list(dict.fromkeys([*(t['name'] for t in info), *known]))
    return (merged or [DEFAULT_TAB]), blocked


# ======================================================================
# Product list
# ======================================================================

def product_list(request):
    conf = DropshipSettings.load()
    qs = Product.objects.select_related('created_by')
    f = {k: request.GET.get(k, '').strip() for k in ('q', 'tab', 'status')}
    if f['q']:
        qs = qs.filter(Q(item_id__icontains=f['q']) | Q(product_name__icontains=f['q']) |
                       Q(seller_name__icontains=f['q']))
    if f['tab']:
        qs = qs.filter(tab=f['tab'])
    if f['status']:
        qs = qs.filter(status=f['status'])

    page = Paginator(qs, 25).get_page(request.GET.get('page'))
    rows = [(p, p.calc(conf)) for p in page]

    status_counts = dict(Product.objects.values_list('status').annotate(n=Count('id')))
    profits = [p.calc(conf)['profit'] for p in Product.objects.exclude(listed_price=None)]
    profits = [x for x in profits if x is not None]
    stats = {
        'total': Product.objects.count(),
        'winning': status_counts.get('Winning', 0),
        'listed': status_counts.get('Listed', 0),
        'avg_profit': (sum(profits) / len(profits)).quantize(Decimal('0.01')) if profits else None,
        'unsynced': Product.objects.exclude(sync_status='synced').count(),
    }
    auto_sync = conf.sheet_connected and (
        conf.last_sync_at is None or (timezone.now() - conf.last_sync_at).total_seconds() > 120)
    return render(request, 'ebay_dropshipping/product_list.html', {
        'conf': conf, 'page': page, 'rows': rows, 'filters': f, 'stats': stats,
        'status_counts': status_counts, 'statuses': Product.STATUS_CHOICES,
        'tabs': Product.objects.order_by('tab').values_list('tab', flat=True).distinct(),
        'auto_sync': auto_sync,
    })


# ======================================================================
# Add / edit
# ======================================================================

def product_form(request, pk=None):
    conf = DropshipSettings.load()
    instance = get_object_or_404(Product, pk=pk) if pk else None
    tabs, blocked = _available_tabs(conf, refresh=request.GET.get('refresh_tabs') == '1')
    usable = [t for t in tabs if t not in blocked]

    pref = UserTabPreference.objects.filter(user=request.user).first()
    if instance:
        selected_tab = instance.tab
    elif pref and pref.last_tab not in blocked:
        selected_tab = pref.last_tab
    else:
        selected_tab = usable[0] if usable else NEW_TAB
    if selected_tab not in tabs and selected_tab != NEW_TAB:
        tabs.append(selected_tab)

    # No usable tab yet → suggest a name so the first product can be submitted straight away.
    suggested = DEFAULT_SUGGESTED_TAB if DEFAULT_SUGGESTED_TAB.lower() not in {b.lower() for b in blocked} else ''
    form = ProductForm(request.POST or None, instance=instance, tabs=tabs, blocked_tabs=blocked,
                       initial={'tab_choice': selected_tab, 'new_tab': suggested if selected_tab == NEW_TAB else ''})
    duplicate = None

    if request.method == 'POST' and form.is_valid():
        tab, item_id = form.cleaned_data['tab'], form.cleaned_data['item_id']
        existing = Product.objects.filter(tab=tab, item_id=item_id)
        if instance:
            existing = existing.exclude(pk=instance.pk)
        existing = existing.first()

        if existing and request.POST.get('confirm_update') != '1':
            duplicate = existing  # ask the user: update the existing row or cancel
        else:
            old_key = (instance.tab, instance.item_id) if instance else None
            if existing:
                # User confirmed: overwrite the existing record with the submitted values.
                # When editing, the record being edited merges into the existing one; old_key
                # (still the edited record's key) makes sure its sheet row is removed below.
                if instance:
                    instance.delete()
                form = ProductForm(request.POST, instance=existing, tabs=tabs, blocked_tabs=blocked)
                form.is_valid()
            product = form.save(commit=False)
            if not product.created_by_id:
                product.created_by = request.user
            product.sync_status = 'pending'
            product.save()

            UserTabPreference.objects.update_or_create(user=request.user, defaults={'last_tab': product.tab})
            if form.cleaned_data.get('tab_choice') == NEW_TAB:
                cache.delete(TABS_CACHE_KEY)

            # The row moved to another tab or got a new ID: remove the old sheet row.
            if old_key and old_key != (product.tab, product.item_id) and conf.sheet_connected:
                ghost = Product(tab=old_key[0], item_id=old_key[1])
                try:
                    sheets.delete_remote(ghost, conf)
                except sheets.SheetError:
                    messages.warning(request, 'The old row could not be removed from the sheet; please delete it there.')

            # Shown as a SweetAlert popup ("Title::Body", see templates/partials/messages.html).
            verb = 'updated' if (instance or existing) else 'saved'
            title = f'Product {verb}!'
            if not conf.sheet_connected:
                messages.success(request, f'{title}::Item {product.item_id} was {verb}. Connect Google Sheet in '
                                          f'Settings to copy it there too.', extra_tags='swal')
            elif sheets.push_product(product, conf):
                messages.success(request, f'{title}::Item {product.item_id} was {verb} and written to the '
                                          f'“{product.tab}” tab in Google Sheet.', extra_tags='swal')
            else:
                messages.warning(request, f'Saved here, sheet pending::Item {product.item_id} was {verb} on the website, '
                                          f'but Google Sheet could not be reached ({product.sync_error}). '
                                          f'It will be sent automatically on the next sync.', extra_tags='swal')
            if instance:
                return redirect('ebay_dropshipping:product_list')
            return redirect('ebay_dropshipping:product_add')

    # Every validation problem, shown together in a SweetAlert popup.
    error_list = [
        f'{form.fields[name].label}: {err}' if name in form.fields else str(err)
        for name, errs in form.errors.items() for err in errs
    ] if form.is_bound and not duplicate else []

    return render(request, 'ebay_dropshipping/product_form.html', {
        'form': form, 'instance': instance, 'error_list': error_list, 'tabs': tabs, 'blocked_tabs': blocked,
        'selected_tab': form['tab_choice'].value() or selected_tab,
        'new_tab_value': NEW_TAB, 'conf': conf, 'fees': conf.fees_dict(), 'fee_form': FeeSettingsForm(instance=conf),
        'duplicate': duplicate, 'duplicate_calc': duplicate.calc(conf) if duplicate else None,
        'statuses': Product.STATUS_CHOICES,
    })


@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    conf = DropshipSettings.load()
    if conf.sheet_connected and product.sync_status != 'pending':
        try:
            sheets.delete_remote(product, conf)
        except sheets.SheetError as e:
            messages.error(request, f'Not deleted: the sheet could not be reached ({e}). '
                                    f'Otherwise the next sync would bring the product back.')
            return redirect('ebay_dropshipping:product_list')
    item_id = product.item_id
    product.delete()
    messages.success(request, f'Product {item_id} was deleted here and from Google Sheet.')
    return redirect('ebay_dropshipping:product_list')


# ======================================================================
# Sync & settings
# ======================================================================

@require_POST
def sync_now(request):
    conf = DropshipSettings.load()
    try:
        summary = sheets.sync_all(conf)
        cache.delete(TABS_CACHE_KEY)
    except sheets.SheetError as e:
        if _wants_json(request):
            return JsonResponse({'ok': False, 'error': str(e)}, status=502)
        messages.error(request, f'Sync failed: {e}')
        return redirect('ebay_dropshipping:product_list')
    if _wants_json(request):
        changed = summary['created'] + summary['updated'] + summary['restored'] + summary['pushed']
        return JsonResponse({'ok': True, 'message': summary['message'], 'changed': changed})
    messages.success(request, summary['message'])
    return redirect('ebay_dropshipping:product_list')


@require_POST
def save_fees(request):
    """Saves fee settings (from the settings page or the product form) and sends them to the sheet."""
    conf = DropshipSettings.load()
    form = FeeSettingsForm(request.POST, instance=conf)
    if not form.is_valid():
        if _wants_json(request):
            return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        messages.error(request, 'Please enter valid fee values.')
        return redirect('ebay_dropshipping:settings')
    conf = form.save(commit=False)
    conf.fees_updated_at = timezone.now()
    conf.save()
    note = ''
    if conf.sheet_connected:
        try:
            sheets.push_fees(conf)
        except sheets.SheetError as e:
            note = f' (Sheet not updated yet: {e})'
    if _wants_json(request):
        return JsonResponse({'ok': True, 'fees': conf.fees_dict(), 'note': note})
    messages.success(request, 'Fee settings saved.' + note)
    return redirect('ebay_dropshipping:settings')


def bookmarklet_href(request):
    """The one-click button: bookmarklet.js as a javascript: link that sends pages to this site."""
    code = BOOKMARKLET_JS.read_text(encoding='utf-8').replace('__TOOL__', request.build_absolute_uri('/').rstrip('/'))
    return 'javascript:' + quote(code, safe="!'()*~-_.")


def settings_view(request):
    conf = DropshipSettings.load()
    conn_form = ConnectionForm(request.POST or None, instance=conf)
    if request.method == 'POST' and conn_form.is_valid():
        conn_form.save()
        cache.delete(TABS_CACHE_KEY)
        if conf.sheet_webapp_url:
            try:
                sheets.SheetClient(conf).call('ping')
                messages.success(request, 'Connected! Google Sheet answered correctly. Click “Sync now” to send your products.')
            except sheets.SheetError as e:
                messages.error(request, f'URL saved, but the test failed: {e}')
        else:
            messages.info(request, 'Google Sheet disconnected.')
        return redirect('ebay_dropshipping:settings')
    return render(request, 'ebay_dropshipping/settings.html', {
        'conf': conf, 'conn_form': conn_form, 'fee_form': FeeSettingsForm(instance=conf),
        'columns': COLUMNS, 'bookmarklet': bookmarklet_href(request),
    })


@require_POST
def regenerate_token(request):
    import secrets
    conf = DropshipSettings.load()
    conf.sync_token = secrets.token_urlsafe(24)
    conf.save(update_fields=['sync_token'])
    messages.warning(request, 'A new sync key was created. Download Code.gs again and paste it into Apps Script, then redeploy.')
    return redirect('ebay_dropshipping:settings')


def download_script(request, name):
    """Serves Code.gs / Form.html with this installation's sync key already filled in."""
    if name not in ('Code.gs', 'Form.html'):
        return HttpResponse(status=404)
    text = (SCRIPT_DIR / name).read_text(encoding='utf-8')
    if name == 'Code.gs':
        # Only the constant's value – the placeholder check further down in doPost stays intact.
        text = text.replace("const SYNC_KEY = 'PASTE_YOUR_SYNC_KEY_HERE';",
                            f"const SYNC_KEY = '{DropshipSettings.load().sync_token}';")
    else:
        # The parser/calculator is shared with the website form, so it is injected here.
        text = text.replace('/*__EBAY_TOOL__*/', TOOL_JS.read_text(encoding='utf-8'))
    response = HttpResponse(text, content_type='text/plain; charset=utf-8')
    if request.GET.get('download'):
        response['Content-Disposition'] = f'attachment; filename="{name}"'
    return response
