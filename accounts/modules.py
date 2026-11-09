"""
Single source of truth for the application's modules.

Every feature area of the platform is registered here once. The registry drives:
  * the sidebar menu (only modules the user may access are shown),
  * role permissions (a Role stores the list of module keys it grants),
  * request-level access control (ModuleAccessMiddleware maps each view to a module).
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Module:
    key: str
    label: str
    icon: str
    url_name: str
    group: str
    description: str = ''
    # Apps whose views all belong to this module.
    apps: tuple = field(default_factory=tuple)
    # Individual url names (used for apps that host several modules, e.g. `keywords`).
    url_names: tuple = field(default_factory=tuple)


MODULES = (
    # ---------------------------------------------------------------- Overview
    Module('overview', 'Dashboard', 'ri-dashboard-2-line', 'overview', 'Main',
           'System overview with KPIs and charts.',
           url_names=('overview',)),

    # ------------------------------------------------------- Keyword research
    Module('analyzer', 'CSV Analyzer', 'ri-file-search-line', 'dashboard', 'Keyword Research',
           'Upload eRank CSVs and score keywords.',
           url_names=('dashboard', 'analyze', 'upload_csv', 'load_results', 'toggle_favorite', 'export')),
    Module('history', 'File History', 'ri-history-line', 'view_history', 'Keyword Research',
           'Previously analysed files.',
           url_names=('view_history', 'delete_history')),
    Module('saved', 'Saved Keywords', 'ri-bookmark-3-line', 'saved_keywords', 'Keyword Research',
           'Keywords you marked as favourites.',
           url_names=('saved_keywords',)),
    Module('rank_optimizer', 'Rank Optimizer', 'ri-rocket-2-line', 'rank_optimizer_dashboard', 'Keyword Research',
           'Filter and optimise keyword lists.',
           apps=('rank_optimizer',)),
    Module('keyword_bank', 'Data Hub', 'ri-safe-2-line', 'keyword_bank:keyword_vault', 'Keyword Research',
           'Central keyword vault and archive.',
           apps=('keyword_bank',)),

    # ------------------------------------------------------- Market & growth
    Module('competitors', 'Competitor Shops', 'ri-store-2-line', 'competitor_shop_dashboard', 'Market Intelligence',
           'Track competitor shops and their keywords.',
           apps=('competitor_shop_analysis',)),
    Module('forecaster', 'Trend Forecaster', 'ri-calendar-event-line', 'forecaster_dashboard', 'Market Intelligence',
           'Seasonal events and preparation tasks.',
           apps=('forecaster',)),
    Module('pinterest', 'Pinterest SEO', 'ri-pinterest-line', 'pinterest_tool', 'Market Intelligence',
           'Generate Pinterest titles and descriptions.',
           apps=('pinterest_seo',)),

    # ------------------------------------------------------------ Studio
    Module('profit', 'ProfitPulse', 'ri-calculator-line', 'calculator', 'Studio',
           'Etsy fee and profit calculator.',
           apps=('profit_pulse',)),
    Module('mockups', 'Mockup Master', 'ri-t-shirt-2-line', 'design_lab', 'Studio',
           'AI-assisted mockup generator.',
           apps=('mockups',)),

    # -------------------------------------------------------- Dropshipping
    Module('ebay', 'eBay Dropshipping', 'ri-shopping-bag-3-line', 'ebay_dropshipping:product_list', 'Dropshipping',
           'Research eBay products, calculate profit and sync with Google Sheets.',
           apps=('ebay_dropshipping',)),
    Module('stock', 'Stock Hunting', 'ri-archive-line', 'stock_hunting:hunt_list', 'Dropshipping',
           'Hunt white-label stock products by the hunting rules and sync with Google Sheets.',
           apps=('stock_hunting',)),

    # ---------------------------------------------------------- Operations
    Module('customers', 'Customer Hub', 'ri-contacts-book-2-line', 'customer_detail:customer_dashboard', 'Operations',
           'Customer directory and records.',
           apps=('customer_detail',)),
    Module('suppliers', 'Supplier Hub', 'ri-truck-line', 'supplier_management:supplier_list', 'Operations',
           'Supplier directory and master data.',
           apps=('supplier_management',)),
)

MODULE_MAP = {m.key: m for m in MODULES}
ALL_MODULE_KEYS = tuple(MODULE_MAP)

_BY_APP = {app: m.key for m in MODULES for app in m.apps}
_BY_URL_NAME = {name: m.key for m in MODULES for name in m.url_names}


def module_for_view(app_label, url_name):
    """Return the module key that guards a view, or None if the view is not module-scoped."""
    if url_name in _BY_URL_NAME:
        return _BY_URL_NAME[url_name]
    return _BY_APP.get(app_label)


def grouped_modules(keys=None):
    """Modules grouped by sidebar section, preserving registry order."""
    groups = {}
    for m in MODULES:
        if keys is None or m.key in keys:
            groups.setdefault(m.group, []).append(m)
    return list(groups.items())
