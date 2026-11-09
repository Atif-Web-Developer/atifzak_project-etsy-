"""
Competitor and supplier tables of a product.

Each product keeps a list of competitors and a list of suppliers (JSON on the model).
The single sheet columns used by the formulas are filled from them:
  - Competitor Links      = every competitor's link
  - Competitor Feedbacks / Solds = the MAIN competitor (★): the one you picked, otherwise the biggest
  - Supplier Link / Cost / Shipping = the supplier USED for the profit (✓): the one you picked,
    otherwise the cheapest (cost + shipping)

In Google Sheet the full tables live in "All Competitors" / "All Suppliers", one line per row:
  ★ Leal_Mart_69 | $23.99 | ship $0.00 | sold 20 | fb 1236 | https://www.ebay.com/itm/147123049946
  ✓ Amazon | $12.49 | ship $0.00 | https://www.amazon.com/dp/B0ABCDE123
The same rules live in ebay-tool.js (mainCompetitor / cheapestSupplier / usedSupplier) for the form.
"""
import re
from decimal import Decimal, InvalidOperation

SOURCES = [('aliexpress', 'AliExpress'), ('amazon', 'Amazon'), ('cj', 'CJ Dropshipping'),
           ('temu', 'Temu'), ('other', 'Local / Other')]
SOURCE_LABELS = dict(SOURCES)
COMPETITOR_KEYS = ('seller', 'link', 'price', 'shipping', 'sold', 'feedback')
SUPPLIER_KEYS = ('source', 'link', 'cost', 'shipping')
MAIN_MARK, USED_MARK = '★', '✓'
# Single product fields that are filled from the tables.
TABLE_SOURCE_FIELDS = ('competitor_links', 'competitor_feedbacks', 'competitor_sold',
                       'supplier_link', 'supplier_cost', 'supplier_shipping')


# ----------------------------------------------------------------- values

def _dec(value):
    text = str(value if value is not None else '').replace(',', '').replace('$', '').strip()
    if not text:
        return None
    try:
        d = Decimal(text).quantize(Decimal('0.01'))
    except InvalidOperation:
        return None
    return d if d >= 0 else None


def _money(value):
    d = _dec(value)
    return '' if d is None else str(d)


def _count(value):
    d = _dec(value)
    return '' if d is None else str(int(d))


def _text(value, limit):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:limit]


def _int_or_none(text):
    return int(text) if text != '' else None


# ----------------------------------------------------------------- cleaning

def clean_competitors(items):
    """Normalised list (same shape every time, so comparisons work); empty rows are dropped."""
    out, pinned = [], False
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        c = {'seller': _text(item.get('seller'), 150), 'link': _text(item.get('link'), 1000),
             'price': _money(item.get('price')), 'shipping': _money(item.get('shipping')),
             'sold': _count(item.get('sold')), 'feedback': _count(item.get('feedback')),
             'pinned': bool(item.get('pinned')) and not pinned}
        if not any(c[k] for k in COMPETITOR_KEYS):
            continue
        pinned = pinned or c['pinned']
        out.append(c)
    return out


def clean_suppliers(items):
    out, pinned = [], False
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        source = str(item.get('source') or '').strip().lower()
        s = {'source': source if source in SOURCE_LABELS else 'other', 'link': _text(item.get('link'), 1000),
             'cost': _money(item.get('cost')), 'shipping': _money(item.get('shipping')),
             'pinned': bool(item.get('pinned')) and not pinned}
        if not (s['link'] or s['cost'] or s['shipping']):
            continue
        pinned = pinned or s['pinned']
        out.append(s)
    return out


def link_problems(competitors, suppliers):
    """Messages for links that aren't web addresses (shown when saving)."""
    problems = []
    for label, items in (('Competitor', competitors), ('Supplier', suppliers)):
        for n, item in enumerate(items, 1):
            if item['link'] and not re.match(r'^https?://\S+$', item['link']):
                problems.append(f'{label} row {n}: the link must start with http:// or https://')
    return problems


# ----------------------------------------------------------------- main / cheapest

def _bigger(a, b):
    """Same rule as EbayTool.isBiggerCompetitor: more sold wins, then more feedback."""
    n = lambda v: int(v) if v != '' else -1  # noqa: E731
    if n(a['sold']) != n(b['sold']):
        return n(a['sold']) > n(b['sold'])
    return n(a['feedback']) > n(b['feedback'])


def biggest_competitor(items):
    best = None
    for i, c in enumerate(items):
        if best is None or _bigger(c, items[best]):
            best = i
    return best


def main_competitor(items):
    """Index of the ★ competitor: the pinned one, otherwise the biggest. None when empty."""
    for i, c in enumerate(items):
        if c.get('pinned'):
            return i
    return biggest_competitor(items)


def supplier_total(s):
    return None if s['cost'] == '' else Decimal(s['cost']) + (Decimal(s['shipping']) if s['shipping'] else 0)


def cheapest_supplier(items):
    best = None
    for i, s in enumerate(items):
        total = supplier_total(s)
        if total is not None and (best is None or total < supplier_total(items[best])):
            best = i
    return best


def used_supplier(items):
    """Index of the ✓ supplier (used for the profit): pinned, otherwise the cheapest, otherwise the first."""
    for i, s in enumerate(items):
        if s.get('pinned'):
            return i
    cheapest = cheapest_supplier(items)
    if cheapest is not None:
        return cheapest
    return 0 if items else None


# ----------------------------------------------------------------- single fields

def flat_fields(competitors, suppliers):
    """The single columns (formulas, sheet) taken from the tables."""
    main = main_competitor(competitors)
    used = used_supplier(suppliers)
    m = competitors[main] if main is not None else None
    s = suppliers[used] if used is not None else None
    return {
        'competitor_links': '\n'.join(c['link'] for c in competitors if c['link']),
        'competitor_feedbacks': _int_or_none(m['feedback']) if m else None,
        'competitor_sold': _int_or_none(m['sold']) if m else None,
        'supplier_link': s['link'] if s else '',
        'supplier_cost': _dec(s['cost']) if s else None,
        'supplier_shipping': _dec(s['shipping']) if s else None,
    }


def lists_from_flat(fields):
    """Tables for a product saved before the tables existed (or added in the sheet's single columns)."""
    links = [l.strip() for l in str(fields.get('competitor_links') or '').splitlines() if l.strip()]
    competitors = [{'link': l} for l in links]
    fb, sold = fields.get('competitor_feedbacks'), fields.get('competitor_sold')
    if fb is not None or sold is not None:
        if not competitors:
            competitors = [{}]
        competitors[0].update(feedback=fb, sold=sold)
    suppliers = []
    if fields.get('supplier_link') or fields.get('supplier_cost') is not None:
        link = str(fields.get('supplier_link') or '')
        suppliers = [{'source': detect_source(link), 'link': link, 'cost': fields.get('supplier_cost'),
                      'shipping': fields.get('supplier_shipping')}]
    return clean_competitors(competitors), clean_suppliers(suppliers)


def detect_source(link):
    for key, pattern in (('aliexpress', r'aliexpress\.'), ('amazon', r'amazon\.|amzn\.'),
                         ('cj', r'cjdropshipping\.'), ('temu', r'temu\.')):
        if re.search(pattern, link or '', re.I):
            return key
    return 'other'


def reconcile_with_sheet(fields):
    """
    Rows read from the sheet: the single columns win (that's what people edit and what the formulas use).
    Their values are put into the ★ competitor / ✓ supplier row, links typed only in "Competitor Links" become
    rows, and an empty table is built from the single columns.
    """
    competitors, suppliers = fields.get('competitors') or [], fields.get('suppliers') or []
    flat_c, flat_s = lists_from_flat(fields)
    if not competitors:
        competitors = flat_c
    else:
        known = {c['link'] for c in competitors}
        typed = [l.strip() for l in str(fields.get('competitor_links') or '').splitlines() if l.strip()]
        competitors += clean_competitors([{'link': l} for l in typed if l not in known])
        main = main_competitor(competitors)
        for key, field in (('feedback', 'competitor_feedbacks'), ('sold', 'competitor_sold')):
            competitors[main][key] = _count(fields.get(field))
    if not suppliers:
        suppliers = flat_s
    elif flat_s:
        used = used_supplier(suppliers)
        suppliers[used].update(link=flat_s[0]['link'], cost=flat_s[0]['cost'], shipping=flat_s[0]['shipping'])
    fields['competitors'] = clean_competitors(competitors)
    fields['suppliers'] = clean_suppliers(suppliers)
    fields.update(flat_fields(fields['competitors'], fields['suppliers']))
    return fields


# ----------------------------------------------------------------- sheet text

def competitors_to_text(items):
    main = main_competitor(items)
    lines = []
    for i, c in enumerate(items):
        parts = [(MAIN_MARK + ' ' if i == main else '') + (c['seller'] or '-')]
        if c['price']:
            parts.append('$' + c['price'])
        if c['shipping']:
            parts.append('ship $' + c['shipping'])
        if c['sold']:
            parts.append('sold ' + c['sold'])
        if c['feedback']:
            parts.append('fb ' + c['feedback'])
        if c['link']:
            parts.append(c['link'])
        lines.append(' | '.join(parts))
    return '\n'.join(lines)


def suppliers_to_text(items):
    used = used_supplier(items)
    lines = []
    for i, s in enumerate(items):
        parts = [(USED_MARK + ' ' if i == used else '') + SOURCE_LABELS[s['source']]]
        if s['cost']:
            parts.append('$' + s['cost'])
        if s['shipping']:
            parts.append('ship $' + s['shipping'])
        if s['link']:
            parts.append(s['link'])
        lines.append(' | '.join(parts))
    return '\n'.join(lines)


def _parse_lines(text, mark):
    rows = []
    for line in str(text or '').splitlines():
        line = line.strip()
        if not line:
            continue
        marked = line.startswith(mark)
        row = {'_marked': marked}
        for part in [p.strip() for p in line.lstrip(mark).split('|')]:
            low = part.lower()
            if re.match(r'^https?://', part):
                row['link'] = part
            elif m := re.match(r'^ship\s*\$?\s*([\d.,]+)$', low):
                row['shipping'] = m.group(1)
            elif m := re.match(r'^sold\s*([\d,]+)$', low):
                row['sold'] = m.group(1)
            elif m := re.match(r'^(?:fb|feedback)\s*([\d,]+)$', low):
                row['feedback'] = m.group(1)
            elif m := re.match(r'^\$\s*([\d.,]+)$', part):
                row['price'] = m.group(1)
            elif part and part != '-' and 'name' not in row:
                row['name'] = part
        rows.append(row)
    return rows


def text_to_competitors(text):
    rows = _parse_lines(text, MAIN_MARK)
    items = clean_competitors([{'seller': r.get('name'), 'link': r.get('link'), 'price': r.get('price'),
                                'shipping': r.get('shipping'), 'sold': r.get('sold'), 'feedback': r.get('feedback')}
                               for r in rows])
    marked = [i for i, r in enumerate(rows) if r['_marked']]
    # ★ on a row that isn't the biggest means it was picked by hand.
    if len(items) == len(rows) and marked and marked[0] != biggest_competitor(items):
        items[marked[0]]['pinned'] = True
    return items


def text_to_suppliers(text):
    rows = _parse_lines(text, USED_MARK)
    by_label = {label.lower(): key for key, label in SOURCES} | {key: key for key, _ in SOURCES}
    items = clean_suppliers([{'source': by_label.get((r.get('name') or '').lower(), detect_source(r.get('link'))),
                              'link': r.get('link'), 'cost': r.get('price'), 'shipping': r.get('shipping')}
                             for r in rows])
    marked = [i for i, r in enumerate(rows) if r['_marked']]
    if len(items) == len(rows) and marked and marked[0] != used_supplier(items):
        items[marked[0]]['pinned'] = True
    return items
