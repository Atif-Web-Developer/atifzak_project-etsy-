import json
import secrets
from pathlib import Path
from types import SimpleNamespace

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import rules, sheets
from .forms import HUNT_FIELDS, ConnectionForm, HuntForm, RulesForm
from .models import MARKETS, Hunt, StockSettings

SCRIPT = Path(__file__).resolve().parent / 'google_apps_script' / 'Code.gs'


def _wants_json(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _result_json(result):
    """evaluate() result → plain JSON for the live checklist on the form."""
    out = {k: v for k, v in result.items() if k not in ('market', 'auto')}
    out['avg_price'] = None if result['avg_price'] is None else str(result['avg_price'])
    auto = result['auto']
    out['auto'] = {'avg_price': '' if auto['avg_price'] is None else str(auto['avg_price']),
                   'two_sellers_100': auto['two_sellers_100'], 'seller_listing_link': auto['seller_listing_link'],
                   'strong_sellers': auto['strong_sellers']}
    out['verdict_info'] = rules.VERDICTS[result['verdict']]
    return out


# ======================================================================
# List
# ======================================================================

def hunt_list(request):
    conf = StockSettings.load()
    q = request.GET.get('q', '').strip()
    market = request.GET.get('market', '')
    verdict = request.GET.get('verdict', '')

    hunts = Hunt.objects.all()
    if q:
        hunts = hunts.filter(Q(main_keyword__icontains=q) | Q(competitors__icontains=q))
    if market in MARKETS:
        hunts = hunts.filter(market=market)

    rows = [(h, h.evaluate(conf)) for h in hunts]
    counts = {v: 0 for v in rules.VERDICTS}
    for _, r in rows:
        counts[r['verdict']] += 1
    if verdict in rules.VERDICTS:
        rows = [(h, r) for h, r in rows if r['verdict'] == verdict]

    page = Paginator(rows, 25).get_page(request.GET.get('page'))
    return render(request, 'stock_hunting/hunt_list.html', {
        'page': page, 'conf': conf, 'counts': counts, 'total': Hunt.objects.count(),
        'verdicts': rules.VERDICTS, 'markets': MARKETS,
        'filters': {'q': q, 'market': market, 'verdict': verdict},
        'pending': Hunt.objects.exclude(sync_status='synced').count(),
    })


# ======================================================================
# Add / edit
# ======================================================================

def hunt_form(request, pk=None):
    conf = StockSettings.load()
    instance = get_object_or_404(Hunt, pk=pk) if pk else None
    form = HuntForm(request.POST or None, instance=instance)

    if request.method == 'POST' and form.is_valid():
        hunt = form.save(commit=False)
        if not hunt.sr_no:
            hunt.sr_no = Hunt.next_sr_no()
        if not hunt.created_by_id:
            hunt.created_by = request.user
        rules.fill_blanks(hunt, conf)
        hunt.sync_status = 'pending'
        hunt.save()

        result = hunt.evaluate(conf)
        verdict = rules.VERDICTS[result['verdict']]
        title = f"{'Updated' if instance else 'Saved'}: {verdict['icon']} {verdict['label']}"
        body = f'#{hunt.sr_no} “{hunt.main_keyword}”'
        if not conf.sheet_connected:
            messages.success(request, f'{title}::{body} was saved. Connect Google Sheet in Settings to copy it there too.',
                             extra_tags='swal')
        elif sheets.push(hunt, conf):
            messages.success(request, f'{title}::{body} was saved and written to “Product selection” and '
                                      f'“Competitors selection” in Google Sheet.', extra_tags='swal')
        else:
            messages.warning(request, f'Saved here, sheet pending::{body} was saved on the website, but Google Sheet '
                                      f'could not be reached ({hunt.sync_error}). It will be sent on the next sync.',
                             extra_tags='swal')
        if request.POST.get('then') == 'new':
            return redirect('stock_hunting:hunt_add')
        return redirect('stock_hunting:hunt_list')

    error_list = []
    for name, errs in form.errors.items():
        label = form.fields[name].label if name in form.fields else ''
        error_list += [f'{label}: {e}' if label else e for e in errs]

    return render(request, 'stock_hunting/hunt_form.html', {
        'form': form, 'instance': instance, 'conf': conf, 'markets': MARKETS,
        'sr_no': instance.sr_no if instance else Hunt.next_sr_no(),
        'error_list': error_list,
        'rules_json': {f: str(getattr(conf, f)) for f in StockSettings.RULE_FIELDS},
        'markets_json': MARKETS,
    })


@require_POST
def evaluate_view(request):
    """Live checklist: the form posts its current values, the rules answer (nothing is saved)."""
    data = request.POST
    values = {f: sheets._clean_value(f, data.get(f)) for f in HUNT_FIELDS if f != 'competitors'}
    values['market'] = data.get('market') if data.get('market') in MARKETS else 'US'
    values['avg_price'] = rules._dec(data.get('avg_price'))
    try:
        values['competitors'] = json.loads(data.get('competitors') or '[]')
    except ValueError:
        values['competitors'] = []
    result = rules.evaluate(SimpleNamespace(**values), StockSettings.load())
    return JsonResponse(_result_json(result))


@require_POST
def hunt_delete(request, pk):
    hunt = get_object_or_404(Hunt, pk=pk)
    conf = StockSettings.load()
    if conf.sheet_connected and hunt.sync_status != 'pending':
        try:
            sheets.delete_remote(hunt, conf)
        except sheets.SheetError as e:
            messages.error(request, f'Not deleted: the sheet could not be reached ({e}). '
                                    f'Otherwise the next sync would bring it back.')
            return redirect('stock_hunting:hunt_list')
    label = f'#{hunt.sr_no} “{hunt.main_keyword}”'
    hunt.delete()
    messages.success(request, f'{label} was deleted here and from Google Sheet.')
    return redirect('stock_hunting:hunt_list')


def guide(request):
    return render(request, 'stock_hunting/guide.html', {'conf': StockSettings.load(), 'markets': MARKETS})


# ======================================================================
# Sync & settings
# ======================================================================

@require_POST
def sync_now(request):
    try:
        summary = sheets.sync_all(StockSettings.load())
    except sheets.SheetError as e:
        messages.error(request, f'Sync failed: {e}')
        return redirect('stock_hunting:hunt_list')
    messages.success(request, summary['message'])
    return redirect('stock_hunting:hunt_list')


def settings_view(request):
    conf = StockSettings.load()
    conn_form = ConnectionForm(request.POST or None, instance=conf)
    if request.method == 'POST' and conn_form.is_valid():
        conn_form.save()
        if conf.sheet_webapp_url:
            try:
                sheets.SheetClient(conf).call('ping')
                messages.success(request, 'Connected! Google Sheet answered and both tabs are ready. Click “Sync now” to send your hunts.')
            except sheets.SheetError as e:
                messages.error(request, f'URL saved, but the test failed: {e}')
        else:
            messages.info(request, 'Google Sheet disconnected.')
        return redirect('stock_hunting:settings')
    return render(request, 'stock_hunting/settings.html', {
        'conf': conf, 'conn_form': conn_form, 'rules_form': RulesForm(instance=conf),
    })


@require_POST
def save_rules(request):
    conf = StockSettings.load()
    form = RulesForm(request.POST, instance=conf)
    if form.is_valid():
        form.save()
        messages.success(request, 'Rules saved. Every hunt is checked with the new rules.')
    else:
        messages.error(request, 'Please enter valid numbers for the rules.')
    return redirect('stock_hunting:settings')


@require_POST
def regenerate_token(request):
    conf = StockSettings.load()
    conf.sync_token = secrets.token_urlsafe(24)
    conf.save(update_fields=['sync_token'])
    messages.warning(request, 'A new sync key was created. Copy Code.gs again into Apps Script, then redeploy.')
    return redirect('stock_hunting:settings')


def download_script(request):
    text = SCRIPT.read_text(encoding='utf-8').replace(
        "const SYNC_KEY = 'PASTE_YOUR_SYNC_KEY_HERE';", f"const SYNC_KEY = '{StockSettings.load().sync_token}';")
    response = HttpResponse(text, content_type='text/plain; charset=utf-8')
    if request.GET.get('download'):
        response['Content-Disposition'] = 'attachment; filename="Code.gs"'
    return response
