"""
The sheet columns – the ONE place they are listed on the Django side.

`key` is the Product field name and is also the key used when talking to Google Sheets,
so google_apps_script/Code.gs must use the same keys in its own COLUMNS list.
Headers are matched by text, so columns can be moved around in the sheet safely.

To add a column: add a model field (+ migration), add it here, and add it to COLUMNS in Code.gs.
"""
from collections import namedtuple

Column = namedtuple('Column', 'key header group kind')

# kind: text | int | money | url | image | multiline | competitors | suppliers | status | calc
COLUMNS = [
    # Auto-filled from the pasted eBay page
    Column('item_id', 'ID', 'auto', 'text'),
    Column('product_name', 'Product Name', 'auto', 'text'),
    Column('ebay_link', 'eBay Item Link', 'auto', 'url'),
    Column('image_url', 'Image', 'auto', 'image'),                          # picture link; IMAGE() in the sheet
    Column('seller_name', 'Seller Name', 'auto', 'text'),
    Column('seller_feedback', 'Total Seller Feedback Count', 'auto', 'int'),
    Column('seller_price', 'eBay Seller Price', 'auto', 'money'),
    Column('buyer_shipping', 'Competitor Shipping', 'auto', 'money'),      # was "Buyer Shipping"
    Column('sold_orders', 'Sold / Orders', 'auto', 'int'),
    Column('sales_line', 'Sales Line', 'auto', 'text'),
    Column('variation', 'Variation', 'auto', 'text'),
    # Typed manually
    Column('supplier_link', 'Supplier Link', 'manual', 'url'),
    Column('supplier_cost', 'Supplier Cost', 'manual', 'money'),
    Column('supplier_shipping', 'Supplier Shipping', 'manual', 'money'),
    Column('other_cost', 'Sourcing Buying Fee / Other Cost', 'manual', 'money'),
    Column('suppliers', 'All Suppliers', 'manual', 'suppliers'),               # whole supplier table, one per line
    Column('competitor_links', 'Competitor Links', 'manual', 'multiline'),
    Column('competitor_feedbacks', 'Competitor No. of Feedbacks', 'manual', 'int'),
    Column('competitor_sold', 'Competitor Solds / Orders', 'manual', 'int'),
    Column('competitors', 'All Competitors', 'manual', 'competitors'),         # whole competitor table, one per line
    Column('listed_price', 'My Listed Price', 'manual', 'money'),
    Column('my_shipping', 'My Buyer Shipping', 'manual', 'money'),         # what YOU charge – used in the formulas
    Column('status', 'Status', 'manual', 'status'),
    # Calculated (sheet formulas) – see calculations.py
    Column('total_sale', 'Total Sale', 'calc', 'calc'),
    Column('ebay_fee', 'eBay Fee', 'calc', 'calc'),
    Column('ad_fee', 'Ad Fee', 'calc', 'calc'),
    Column('total_cost', 'Total Cost', 'calc', 'calc'),          # was "Minimum Listing Price"
    Column('profit', 'Profit', 'calc', 'calc'),
    Column('profit_pct', 'Profit Percentage', 'calc', 'calc'),
    Column('break_even', 'Break-even Price', 'calc', 'calc'),
    Column('roi', 'ROI %', 'calc', 'calc'),
]

# Columns stored on the Product model (everything except the derived link and calculations).
STORED_COLUMNS = [c for c in COLUMNS if c.group != 'calc' and c.key != 'ebay_link']
