"""
The profit formulas – the ONE place they live on the Django side.

The same logic exists as sheet formulas in google_apps_script/Code.gs (FORMULAS) and as
JavaScript in static/ebay_dropshipping/js/ebay-tool.js (calculate). Change all three together.

    Costs             = Supplier Cost + Supplier Shipping + Other Cost
    Total Sale        = My Listed Price + My Shipping Charge
    Fixed Fee         = low fee if Total Sale ≤ threshold, otherwise high fee   ($0.30 / $0.40 at $10)
    eBay Fee          = Total Sale × (1 + Sales Tax %) × eBay Fee % + Fixed Fee
    Ad Fee            = Total Sale × Ad Rate %
    Total Cost        = Costs + eBay Fee + Ad Fee
    Profit            = Total Sale − Total Cost
    Profit %          = Profit ÷ Total Sale × 100
    ROI %             = Profit ÷ Costs × 100
    Break-even Price  = (Costs + high fixed fee) ÷ (1 − eBay Fee % × (1 + Sales Tax %) − Ad Rate %) − My Shipping
                        (the lowest listed price without a loss; uses the higher fixed fee to stay on the safe side)

Everything except Break-even needs My Listed Price; Break-even needs Supplier Cost.
"""
from decimal import Decimal, ROUND_HALF_UP

TWO = Decimal('0.01')
KEYS = ('total_sale', 'ebay_fee', 'ad_fee', 'total_cost', 'profit', 'profit_pct', 'break_even', 'roi')


def _d(value):
    return Decimal(str(value)) if value not in (None, '') else Decimal('0')


def calculate(listed_price, supplier_cost, supplier_shipping, other_cost, settings, my_shipping=None):
    """Return the calculated columns rounded to 2 decimals; a value is None when it can't be calculated."""
    result = dict.fromkeys(KEYS)
    fee_pct = _d(settings.ebay_fee_pct) / 100
    ad_pct = _d(settings.ad_rate_pct) / 100
    tax = 1 + _d(settings.sales_tax_pct) / 100
    costs = _d(supplier_cost) + _d(supplier_shipping) + _d(other_cost)
    shipping = _d(my_shipping)

    if listed_price not in (None, '') and _d(listed_price) != 0:
        total_sale = _d(listed_price) + shipping
        fixed = _d(settings.ebay_fixed_fee) if total_sale <= _d(settings.fixed_fee_threshold) \
            else _d(settings.ebay_fixed_fee_high)
        ebay_fee = total_sale * tax * fee_pct + fixed
        ad_fee = total_sale * ad_pct
        total_cost = costs + ebay_fee + ad_fee
        profit = total_sale - total_cost
        result.update(total_sale=total_sale, ebay_fee=ebay_fee, ad_fee=ad_fee, total_cost=total_cost,
                      profit=profit, profit_pct=profit / total_sale * 100,
                      roi=(profit / costs * 100) if costs else None)

    if supplier_cost not in (None, ''):
        divisor = 1 - fee_pct * tax - ad_pct
        if divisor > 0:
            result['break_even'] = (costs + _d(settings.ebay_fixed_fee_high)) / divisor - shipping

    return {k: (v.quantize(TWO, ROUND_HALF_UP) if v is not None else None) for k, v in result.items()}
