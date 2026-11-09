"""
Two-way sync between Django and the Google Sheet (through the Apps Script web app in Code.gs).

Rules that make sure no record is ever lost:
  * Saving in Django pushes the row to the sheet immediately. If that fails the record is
    marked "pending" and is pushed again on the next sync.
  * Sync first pushes everything pending, then pulls every product tab from the sheet:
      - rows that only exist in the sheet are created in Django,
      - rows edited in the sheet update Django (unless Django still has unsent changes),
      - records that exist in Django but are missing from the sheet are written back.
  * Fee settings: whichever side changed them most recently wins.
"""
import copy
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation

import requests
from django.utils import timezone

from . import lists
from .columns import STORED_COLUMNS
from .models import DropshipSettings, Product

TIMEOUT = 45


class SheetError(Exception):
    pass


class SheetClient:
    def __init__(self, conf):
        if not conf.sheet_connected:
            raise SheetError('Google Sheet is not connected yet. Open Settings → Google Sheet connection.')
        self.url = conf.sheet_webapp_url
        self.token = conf.sync_token

    def call(self, action, **payload):
        try:
            resp = requests.post(self.url, json={'token': self.token, 'action': action, **payload}, timeout=TIMEOUT)
        except requests.RequestException as e:
            raise SheetError(f'Could not reach Google: {e.__class__.__name__}. Check your internet connection.')
        try:
            data = resp.json()
        except ValueError:
            raise SheetError('Google returned an unexpected page. Make sure the web app is deployed with '
                             '“Who has access: Anyone” and that you copied the /exec URL.')
        if not data.get('ok'):
            raise SheetError(data.get('error') or 'Unknown error from Google Sheet.')
        return data


# ----------------------------------------------------------------- conversion

def _num(value):
    if value is None or value == '':
        return ''
    return float(value)


def product_to_row(p):
    row = {}
    for col in STORED_COLUMNS:
        value = getattr(p, col.key)
        row[col.key] = _num(value) if col.kind in ('money', 'int') else (value or '')
    competitors, suppliers = p.competitors, p.suppliers
    if not competitors and not suppliers:  # saved before the tables existed
        competitors, suppliers = lists.lists_from_flat(row)
    row['competitors'] = lists.competitors_to_text(lists.clean_competitors(competitors))
    row['suppliers'] = lists.suppliers_to_text(lists.clean_suppliers(suppliers))
    row['ebay_link'] = p.ebay_link
    return row


def _clean(col, value):
    """Convert a value read from the sheet into the model's type."""
    if value is None:
        value = ''
    if isinstance(value, str):
        value = value.strip()
    if col.kind == 'int':
        if value == '':
            return None
        try:
            return max(int(float(str(value).replace(',', ''))), 0)
        except ValueError:
            return None
    if col.kind == 'money':
        if value == '':
            return None
        try:
            return Decimal(str(value).replace(',', '').replace('$', '')).quantize(Decimal('0.01'))
        except InvalidOperation:
            return None
    if col.kind == 'competitors':
        return lists.text_to_competitors(value)
    if col.kind == 'suppliers':
        return lists.text_to_suppliers(value)
    if col.kind == 'status':
        valid = dict(Product.STATUS_CHOICES)
        return value if value in valid else 'Researching'
    if col.key == 'item_id':
        text = str(value)
        return text[:-2] if text.endswith('.0') else text
    return str(value)


TABLE_KEYS = ('competitors', 'suppliers')


def sheet_lacks_tables(row):
    """True when the sheet row has no table text – an older Code.gs, or a column just added to an old row."""
    return any(not str(row.get(key) or '').strip() for key in TABLE_KEYS)


def row_to_fields(row, current=None):
    """
    Sheet row → model fields. `current` is the product already in Django (if any): when the sheet has
    no table text, Django's tables are kept – an empty or missing column must never wipe them.
    """
    fields = {col.key: _clean(col, row.get(col.key)) for col in STORED_COLUMNS}
    if current is not None:
        for key in TABLE_KEYS:
            if not str(row.get(key) or '').strip():
                fields[key] = copy.deepcopy(getattr(current, key))
    return lists.reconcile_with_sheet(fields)


# ---------------------------------------------------------------- operations

def _mark(product, status, error=''):
    values = {'sync_status': status, 'sync_error': error[:255]}
    if status == 'synced':
        values['synced_at'] = timezone.now()
    Product.objects.filter(pk=product.pk).update(**values)  # .update() keeps updated_at untouched
    for k, v in values.items():
        setattr(product, k, v)


def push_product(product, conf=None, client=None):
    """Write one product to the sheet. Returns True on success; never raises."""
    conf = conf or DropshipSettings.load()
    try:
        client = client or SheetClient(conf)
        client.call('upsert', tab=product.tab, row=product_to_row(product), fees=conf.fees_dict())
        _mark(product, 'synced')
        return True
    except SheetError as e:
        _mark(product, 'error' if conf.sheet_connected else 'pending', str(e))
        return False


def delete_remote(product, conf=None):
    conf = conf or DropshipSettings.load()
    SheetClient(conf).call('delete', tab=product.tab, item_id=product.item_id)


def push_fees(conf):
    SheetClient(conf).call('saveSettings', fees=conf.fees_dict(),
                           updated_at=int(conf.fees_updated_at.timestamp() * 1000))


def list_tabs(conf):
    """[{'name': …, 'usable': bool}] – tabs that already hold other data are not usable."""
    client = SheetClient(conf)
    data = client.call('listTabs')
    info = data.get('tabInfo')
    if info is None:
        # Older Code.gs can't tell which tabs hold other data, so play safe: only tabs that
        # already have this tool's headers (the ones "pull" returns) are usable.
        ours = set((client.call('pull').get('tabs') or {}).keys())
        info = [{'name': n, 'usable': n in ours} for n in data.get('tabs', [])]
    return info


def sync_all(conf=None):
    """Full two-way sync. Returns a summary dict; raises SheetError if Google can't be reached."""
    conf = conf or DropshipSettings.load()
    client = SheetClient(conf)
    summary = {'pushed': 0, 'created': 0, 'updated': 0, 'restored': 0, 'failed': 0, 'fees': ''}

    # 1. Send everything Django hasn't delivered yet.
    for p in Product.objects.exclude(sync_status='synced'):
        if push_product(p, conf, client):
            summary['pushed'] += 1
        else:
            summary['failed'] += 1

    # 2. Read the whole sheet.
    data = client.call('pull')
    sheet_fees = data.get('settings') or {}

    # 3. Fee settings – newest side wins.
    sheet_ts = sheet_fees.get('updated_at') or 0
    django_ts = int(conf.fees_updated_at.timestamp() * 1000)
    if sheet_ts > django_ts and sheet_fees.get('ebay_fee_pct') is not None:
        for name in DropshipSettings.FEE_FIELDS:
            if sheet_fees.get(name) is not None:  # an older Code.gs may not send every setting
                setattr(conf, name, Decimal(str(sheet_fees[name])))
        conf.fees_updated_at = datetime.fromtimestamp(sheet_ts / 1000, tz=dt_timezone.utc)
        conf.save()
        summary['fees'] = 'Fee settings updated from the sheet.'
    elif django_ts > sheet_ts:
        push_fees(conf)

    # 4. Bring sheet rows into Django.
    seen, refill = set(), []
    item_col = next(c for c in STORED_COLUMNS if c.key == 'item_id')
    for tab, rows in (data.get('tabs') or {}).items():
        for row in rows:
            item_id = _clean(item_col, row.get('item_id'))
            if not item_id:
                continue
            seen.add((tab, item_id))
            product = Product.objects.filter(tab=tab, item_id=item_id).first()
            fields = row_to_fields(row, product)
            fields.pop('item_id')
            # The sheet has the table columns but this row's cells are empty (column added after it was written):
            # write the row again so the sheet gets the tables too.
            if product is not None and all(k in row for k in TABLE_KEYS) and sheet_lacks_tables(row)                     and (product.competitors or product.suppliers):
                refill.append(product)
            if product is None:
                Product.objects.create(tab=tab, item_id=item_id, sync_status='synced',
                                       synced_at=timezone.now(), **fields)
                summary['created'] += 1
            elif product.sync_status == 'synced':
                changed = {k: v for k, v in fields.items() if getattr(product, k) != v}
                if changed:
                    Product.objects.filter(pk=product.pk).update(
                        synced_at=timezone.now(), updated_at=timezone.now(), **changed)
                    summary['updated'] += 1

    for p in refill:
        p.refresh_from_db()
        push_product(p, conf, client)

    # 5. Anything Django has that the sheet lost gets written back.
    for p in Product.objects.filter(sync_status='synced'):
        if (p.tab, p.item_id) not in seen:
            if push_product(p, conf, client):
                summary['restored'] += 1
            else:
                summary['failed'] += 1

    parts = [f"{summary[k]} {label}" for k, label in
             (('pushed', 'sent'), ('created', 'imported'), ('updated', 'updated from sheet'),
              ('restored', 'restored to sheet'), ('failed', 'failed')) if summary[k]]
    message = 'Everything is in sync.' if not parts else 'Sync complete: ' + ', '.join(parts) + '.'
    if summary['fees']:
        message += ' ' + summary['fees']
    conf.last_sync_at = timezone.now()
    conf.last_sync_message = message[:255]
    conf.save(update_fields=['last_sync_at', 'last_sync_message'])
    summary['message'] = message
    return summary
