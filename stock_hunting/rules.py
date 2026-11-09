"""
Ma'am's rules – the ONE place they are checked, using only the fields of her two sheet tabs.

  * auto_fields(competitors, conf) works out the three "Product selection" values that come from the
    competitor rows: 2 Sellers with 100 above sales, Avg sales price and seller listing link.
  * evaluate(hunt, conf) checks the rules and gives the verdict:
      green      – Source karein: every rule passes
      yellow     – Test karein:   rules pass, but there are many sellers
      red        – Chhod dein:    a rule fails
      incomplete – data still missing
"""
import re
from decimal import Decimal, InvalidOperation

COMPETITOR_KEYS = ('link', 'feedback', 'price', 'sales_30d', 'variation')


# ----------------------------------------------------------------- competitors

def _dec(value):
    text = re.sub(r'^(A\$|US\$|\$|£)', '', str(value if value is not None else '').replace(',', '').strip())
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


def _yes_no(value):
    v = str(value or '').strip().lower()
    return 'Yes' if v in ('yes', 'y', 'haan', 'true', '1') else 'No' if v in ('no', 'n', 'nahi', 'false', '0') else ''


def clean_competitors(items):
    """Same shape every time (so comparisons work); empty rows are dropped."""
    out = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        c = {'link': _text(item.get('link'), 1000), 'feedback': _count(item.get('feedback')),
             'price': _money(item.get('price')), 'sales_30d': _count(item.get('sales_30d')),
             'variation': _text(item.get('variation'), 200)}
        if any(c[k] for k in COMPETITOR_KEYS):
            out.append(c)
    return out


def link_problems(competitors):
    return [f'Competitor row {n}: the link must start with http:// or https://'
            for n, c in enumerate(competitors, 1) if c['link'] and not re.match(r'^https?://\S+$', c['link'])]


def _num(d):
    """13.00 → '13', 4.50 → '4.5' (for labels)."""
    return '{:f}'.format(Decimal(d).normalize())


# ----------------------------------------------------------------- worked out from the competitors

def auto_fields(competitors, conf):
    comps = clean_competitors(competitors)
    prices = [Decimal(c['price']) for c in comps if c['price']]
    sales = [int(c['sales_30d']) for c in comps if c['sales_30d']]
    strong = sum(1 for s in sales if s >= conf.min_sales_30d)
    best = max((c for c in comps if c['link']), key=lambda c: int(c['sales_30d'] or 0), default=None)
    return {
        'avg_price': (sum(prices) / len(prices)).quantize(Decimal('0.01')) if prices else None,
        'two_sellers_100': '' if not sales else ('Yes' if strong >= conf.min_strong_sellers else 'No'),
        'seller_listing_link': best['link'] if best else '',
        'strong_sellers': strong,
    }


def fill_blanks(hunt, conf):
    """Blank auto fields get the value worked out from the competitors (typed values are kept)."""
    auto = auto_fields(hunt.competitors, conf)
    for key in ('avg_price', 'two_sellers_100', 'seller_listing_link'):
        if getattr(hunt, key) in (None, ''):
            setattr(hunt, key, auto[key])


# ----------------------------------------------------------------- verdict

def _check(key, label, required, ok, detail):
    """ok: True / False / None (None = data still missing)."""
    return {'key': key, 'label': label, 'required': required,
            'status': 'missing' if ok is None else 'pass' if ok else 'fail', 'detail': detail}


def evaluate(hunt, conf):
    from .models import MARKETS
    market = MARKETS.get(getattr(hunt, 'market', 'US'), MARKETS['US'])
    cur = market['currency']
    comps = clean_competitors(getattr(hunt, 'competitors', []))
    auto = auto_fields(comps, conf)
    avg = getattr(hunt, 'avg_price', None)
    avg = auto['avg_price'] if avg in (None, '') else Decimal(str(avg))
    two = getattr(hunt, 'two_sellers_100', '') or auto['two_sellers_100']
    feedbacks = [int(c['feedback']) for c in comps if c['feedback']]
    low_fb = sum(1 for f in feedbacks if f < conf.max_feedback)
    trend = getattr(hunt, 'sales_trend', '')
    total = getattr(hunt, 'total_sellers', None)

    checks = [
        _check('price', f'Avg price {cur}{_num(conf.price_min)}–{cur}{_num(conf.price_max)}', True,
               None if avg is None else conf.price_min <= avg <= conf.price_max, '—' if avg is None else f'{cur}{avg}'),
        _check('two_sellers', f'{conf.min_strong_sellers} sellers with {conf.min_sales_30d}+ sales', True,
               None if not two else two == 'Yes', two or '—'),
        _check('low_feedback', f'{conf.min_low_feedback_sellers}+ seller with feedback under {conf.max_feedback:,}', True,
               None if not feedbacks else low_fb >= conf.min_low_feedback_sellers,
               f'{low_fb} of {len(feedbacks)}' if feedbacks else '—'),
        _check('trend', 'Sales trend not going down', True, None if not trend else trend != 'Down', trend or '—'),
        _check('total_sellers', f'Total sellers up to {conf.max_total_sellers}', False,
               None if total is None else total <= conf.max_total_sellers, '—' if total is None else str(total)),
    ]
    required = [c for c in checks if c['required']]
    if any(c['status'] == 'fail' for c in required):
        verdict = 'red'
    elif any(c['status'] == 'missing' for c in required):
        verdict = 'incomplete'
    elif all(c['status'] == 'pass' for c in checks):
        verdict = 'green'
    else:
        verdict = 'yellow'
    return {
        'checks': checks, 'verdict': verdict, 'verdict_label': VERDICTS[verdict]['label'],
        'currency': cur, 'market': market, 'avg_price': avg, 'two_sellers_100': two,
        'competitor_count': len(comps), 'auto': auto,
    }


VERDICTS = {
    'green': {'label': 'Source karein', 'icon': '🟢', 'color': 'success'},
    'yellow': {'label': 'Test karein', 'icon': '🟡', 'color': 'warning'},
    'red': {'label': 'Chhod dein', 'icon': '🔴', 'color': 'danger'},
    'incomplete': {'label': 'Data poora karein', 'icon': '⚪', 'color': 'secondary'},
}
