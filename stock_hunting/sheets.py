"""
Google Sheet sync for Stock Hunting – the same safety rules as eBay Dropshipping:
  * saving a hunt writes it to the sheet straight away (or marks it "pending" if the sheet can't be reached),
  * "Sync now" sends pending hunts, reads both tabs, imports rows added in the sheet, takes edits made there
    and writes back anything the sheet lost – a record never disappears from either side.

Tabs (ma'am's layout): "Product selection" – one row per hunt; "Competitors selection" – one row per
competitor, linked by Sr No. The Apps Script side is google_apps_script/Code.gs (same keys as below).
"""
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from ebay_dropshipping.sheets import SheetClient, SheetError  # noqa: F401 (re-exported for views/tests)

from . import rules
from .models import Hunt, StockSettings

# Ma'am's "Product selection" columns stored on Hunt (Sr. No is the link between the tabs).
TEXT_FIELDS = ('main_keyword', 'seller_listing_link')
INT_FIELDS = ('total_sellers',)
DEC_FIELDS = ('avg_price',)
CHOICE_FIELDS = ('sales_trend', 'two_sellers_100')
HUNT_FIELDS = TEXT_FIELDS + INT_FIELDS + DEC_FIELDS + CHOICE_FIELDS
TREND_WORDS = {'up': 'Up', 'rising': 'Up', 'increasing': 'Up', 'stable': 'Stable', 'same': 'Stable',
               'down': 'Down', 'falling': 'Down', 'decreasing': 'Down'}


def _plain(value):
    if value is None:
        return ''
    if isinstance(value, Decimal):
        return float(value)
    return value


def hunt_to_payload(hunt, conf=None):
    row = {'sr_no': hunt.sr_no}
    row.update({f: _plain(getattr(hunt, f)) for f in HUNT_FIELDS})
    comps = [{'sr_no': hunt.sr_no, 'main_keyword': hunt.main_keyword, 'link': c['link'],
              'feedback': int(c['feedback']) if c['feedback'] else '',
              'price': float(c['price']) if c['price'] else '',
              'sales_30d': int(c['sales_30d']) if c['sales_30d'] else '',
              'variation': c['variation']}
             for c in rules.clean_competitors(hunt.competitors)]
    return {'product': row, 'competitors': comps, 'currency': hunt.market_info['currency']}


def _mark(hunt, status, error=''):
    values = {'sync_status': status, 'sync_error': error[:255]}
    if status == 'synced':
        values['synced_at'] = timezone.now()
    Hunt.objects.filter(pk=hunt.pk).update(**values)  # .update() keeps updated_at untouched
    for k, v in values.items():
        setattr(hunt, k, v)


def push(hunt, conf=None, client=None):
    """Write one hunt (its product row + competitor rows). True on success; never raises."""
    conf = conf or StockSettings.load()
    try:
        client = client or SheetClient(conf)
        client.call('upsert', **hunt_to_payload(hunt, conf))
        _mark(hunt, 'synced')
        return True
    except SheetError as e:
        _mark(hunt, 'error' if conf.sheet_connected else 'pending', str(e))
        return False


def delete_remote(hunt, conf=None):
    conf = conf or StockSettings.load()
    SheetClient(conf).call('delete', sr_no=hunt.sr_no)


# ----------------------------------------------------------------- reading the sheet

def _clean_value(field, value):
    if value is None:
        value = ''
    if isinstance(value, str):
        value = value.strip()
    if field in INT_FIELDS:
        try:
            return max(int(float(str(value).replace(',', ''))), 0) if value != '' else None
        except ValueError:
            return None
    if field in DEC_FIELDS:
        return rules._dec(value)
    if field == 'sales_trend':
        return TREND_WORDS.get(str(value).lower(), '')
    if field == 'two_sellers_100':
        return rules._yes_no(value)
    return str(value)


def market_from_price(text):
    """"£19.99" → UK, "A$20" → AU, "$20" → US, no symbol → None (keep what we have)."""
    text = str(text or '').strip()
    if text.startswith('£'):
        return 'UK'
    if text.startswith('A$') or text.startswith('AU$'):
        return 'AU'
    if text.startswith('$') or text.startswith('US$'):
        return 'US'
    return None


def row_to_fields(row, current=None):
    """Sheet row → Hunt fields. An empty cell never wipes a value the website already has."""
    fields = {}
    for f in HUNT_FIELDS:
        value = _clean_value(f, row.get(f))
        if value in (None, '') and current is not None:
            value = getattr(current, f)
        fields[f] = value
    fields['main_keyword'] = (fields['main_keyword'] or '(no keyword)')[:200]
    market = market_from_price(row.get('avg_price'))
    fields['market'] = market or (current.market if current is not None else 'US')
    return fields


def sync_all(conf=None):
    """Full two-way sync. Returns a summary dict; raises SheetError if Google can't be reached."""
    conf = conf or StockSettings.load()
    client = SheetClient(conf)
    summary = {'pushed': 0, 'created': 0, 'updated': 0, 'restored': 0, 'failed': 0}

    # 1. Send everything Django hasn't delivered yet.
    for h in Hunt.objects.exclude(sync_status='synced'):
        summary['pushed' if push(h, conf, client) else 'failed'] += 1

    # 2. Read both tabs.
    data = client.call('pull')
    groups = {}
    for c in data.get('competitors') or []:
        try:
            groups.setdefault(int(float(c.get('sr_no'))), []).append(c)
        except (TypeError, ValueError):
            continue

    # 3. Bring sheet rows into Django.
    seen, refill = set(), []
    for row in data.get('products') or []:
        try:
            sr = int(float(row.get('sr_no')))
        except (TypeError, ValueError):
            continue
        seen.add(sr)
        hunt = Hunt.objects.filter(sr_no=sr).first()
        fields = row_to_fields(row, hunt)
        comps = rules.clean_competitors(groups.get(sr, []))
        if not comps and hunt is not None and hunt.competitors:
            # No competitor rows in the sheet for this hunt: keep ours (an empty sheet must never wipe them)
            # and write them back.
            comps = hunt.competitors
            refill.append(sr)
        fields['competitors'] = comps
        if hunt is None:
            Hunt.objects.create(sr_no=sr, sync_status='synced', synced_at=timezone.now(), **fields)
            summary['created'] += 1
        elif hunt.sync_status == 'synced':
            changed = {k: v for k, v in fields.items() if getattr(hunt, k) != v}
            if changed:
                Hunt.objects.filter(pk=hunt.pk).update(synced_at=timezone.now(), updated_at=timezone.now(), **changed)
                summary['updated'] += 1

    # 4. Anything Django has that the sheet lost (or lost the competitors of) gets written back.
    for h in Hunt.objects.filter(sync_status='synced'):
        if h.sr_no not in seen or h.sr_no in refill:
            if push(h, conf, client):
                summary['restored'] += 1
            else:
                summary['failed'] += 1

    parts = [f"{summary[k]} {label}" for k, label in
             (('pushed', 'sent'), ('created', 'imported'), ('updated', 'updated from sheet'),
              ('restored', 'restored to sheet'), ('failed', 'failed')) if summary[k]]
    message = 'Everything is in sync.' if not parts else 'Sync complete: ' + ', '.join(parts) + '.'
    conf.last_sync_at = timezone.now()
    conf.last_sync_message = message[:255]
    conf.save(update_fields=['last_sync_at', 'last_sync_message'])
    summary['message'] = message
    return summary
