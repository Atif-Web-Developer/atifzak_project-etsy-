import json
import re
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role
from keywords.models import User

from . import sheets
from .calculations import calculate
from .models import DropshipSettings, Product, UserTabPreference


class FakeSheet:
    """In-memory stand-in for the Apps Script web app (same actions as Code.gs)."""

    def __init__(self):
        self.tabs = {'Products': {}}
        self.settings = {'ebay_fee_pct': 13.6, 'ebay_fixed_fee': 0.3, 'ebay_fixed_fee_high': 0.4,
                         'fixed_fee_threshold': 10, 'ad_rate_pct': 5, 'sales_tax_pct': 0, 'updated_at': 0}
        self.down = False

    def client(self, conf):
        if not conf.sheet_connected:
            raise sheets.SheetError('not connected')
        fake = self

        class Client:
            def call(self, action, **p):
                if fake.down:
                    raise sheets.SheetError('Could not reach Google')
                return fake.handle(action, p)
        return Client()

    def handle(self, action, p):
        if action == 'ping':
            return {'ok': True}
        if action == 'listTabs':
            return {'ok': True, 'tabs': list(self.tabs)}
        if action == 'upsert':
            self.tabs.setdefault(p['tab'], {})[str(p['row']['item_id'])] = dict(p['row'])
            return {'ok': True}
        if action == 'delete':
            self.tabs.get(p['tab'], {}).pop(str(p['item_id']), None)
            return {'ok': True}
        if action == 'pull':
            return {'ok': True, 'tabs': {t: list(rows.values()) for t, rows in self.tabs.items()},
                    'settings': dict(self.settings)}
        if action == 'saveSettings':
            self.settings.update(p['fees'], updated_at=p['updated_at'])
            return {'ok': True}
        raise AssertionError(action)


def product_data(**overrides):
    data = {
        'tab_choice': 'Products', 'item_id': '147123049946',
        'product_name': 'Automatic Curling Iron', 'seller_name': 'SpellBeautiful7', 'seller_feedback': '25270',
        'seller_price': '23.99', 'buyer_shipping': '35', 'sold_orders': '7',
        'sales_line': '24h: 0, 3d: 0, 1w: 0, 2w: 0, 1m: 1, 3m: 2', 'variation': 'No',
        'supplier_link': 'https://supplier.example.com/item', 'supplier_cost': '3.81', 'supplier_shipping': '0',
        'other_cost': '0', 'competitor_links': 'https://a.example.com\nhttps://b.example.com',
        'competitor_feedbacks': '100', 'competitor_sold': '12', 'listed_price': '6.88', 'status': 'Testing',
    }
    data.update(overrides)
    return data


class CalculationTests(TestCase):
    @staticmethod
    def fees(**overrides):
        values = dict(ebay_fee_pct=13.6, ebay_fixed_fee=0.30, ebay_fixed_fee_high=0.40, fixed_fee_threshold=10,
                      ad_rate_pct=5, sales_tax_pct=0)
        values.update(overrides)
        return SimpleNamespace(**values)

    def values(self, r, keys):
        return [None if r[k] is None else str(r[k]) for k in keys]

    def test_defaults_match_current_ebay_rates(self):
        conf = DropshipSettings.load()
        self.assertEqual(conf.fees_dict(), {'ebay_fee_pct': 13.6, 'ebay_fixed_fee': 0.3, 'ebay_fixed_fee_high': 0.4,
                                            'fixed_fee_threshold': 10.0, 'ad_rate_pct': 5.0, 'sales_tax_pct': 0.0})

    def test_row2_small_order_uses_low_fixed_fee(self):
        # Listed $6.88, supplier $3.81 → Total Sale ≤ $10 so the fixed fee is $0.30.
        r = calculate(Decimal('6.88'), Decimal('3.81'), 0, 0, self.fees())
        self.assertEqual(self.values(r, ('total_sale', 'ebay_fee', 'ad_fee', 'total_cost', 'profit', 'profit_pct', 'roi')),
                         ['6.88', '1.24', '0.34', '5.39', '1.49', '21.66', '39.12'])
        self.assertEqual(str(r['break_even']), '5.17')  # (3.81 + 0.40) ÷ (1 − 0.136 − 0.05)

    def test_row3_large_order_uses_high_fixed_fee(self):
        # Listed $16.55, supplier $8.99 → fixed fee $0.40, profit $4.08 (was $4.24 with the old rate).
        r = calculate(Decimal('16.55'), Decimal('8.99'), 0, 0, self.fees())
        self.assertEqual(self.values(r, ('ebay_fee', 'profit')), ['2.65', '4.08'])

    def test_old_rate_still_gives_the_original_result(self):
        r = calculate(Decimal('6.88'), Decimal('3.81'), 0, 0, self.fees(ebay_fee_pct=13.25, ebay_fixed_fee_high=0.30))
        self.assertEqual(self.values(r, ('ebay_fee', 'ad_fee', 'total_cost', 'profit', 'profit_pct')),
                         ['1.21', '0.34', '5.37', '1.51', '22.01'])

    def test_my_shipping_is_part_of_total_sale(self):
        # $9 + $2 shipping = $11 → above the $10 threshold, fee on $11, fixed fee $0.40.
        r = calculate(Decimal('9'), Decimal('4'), 0, 0, self.fees(), my_shipping=Decimal('2'))
        self.assertEqual(self.values(r, ('total_sale', 'ebay_fee', 'ad_fee', 'profit')), ['11.00', '1.90', '0.55', '4.55'])

    def test_sales_tax_buffer_raises_the_fee(self):
        r = calculate(Decimal('20'), Decimal('5'), 0, 0, self.fees(sales_tax_pct=7))
        self.assertEqual(str(r['ebay_fee']), '3.31')  # 20 × 1.07 × 13.6% + 0.40

    def test_empty_price_gives_empty_results_but_break_even(self):
        r = calculate(None, 5, 1, 0, self.fees())
        self.assertTrue(all(r[k] is None for k in r if k != 'break_even'))
        self.assertEqual(str(r['break_even']), '7.86')  # (5 + 1 + 0.40) ÷ 0.814
        self.assertTrue(all(v is None for v in calculate(0, None, None, 0, self.fees()).values()))


class ModuleTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('boss', 'boss@example.com', 'S3cure-pass!',
                                             role=Role.objects.get(slug='administrator'))
        self.client.force_login(self.user)
        cache.clear()  # the sheet's tab list is cached between requests
        self.sheet = FakeSheet()
        patcher = mock.patch.object(sheets, 'SheetClient', side_effect=self.sheet.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def connect(self):
        conf = DropshipSettings.load()
        conf.sheet_webapp_url = 'https://script.google.com/macros/s/abc/exec'
        conf.save()
        return conf


class ProductFormTests(ModuleTestBase):
    def test_save_without_sheet_keeps_it_pending(self):
        r = self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        self.assertRedirects(r, reverse('ebay_dropshipping:product_add'), fetch_redirect_response=False)
        p = Product.objects.get()
        self.assertEqual(p.sync_status, 'pending')
        self.assertEqual(p.ebay_link, 'https://www.ebay.com/itm/147123049946')
        self.assertEqual(str(p.calc()['profit']), '1.49')
        self.assertEqual(p.my_shipping, 0)
        self.assertEqual(UserTabPreference.objects.get(user=self.user).last_tab, 'Products')

    def test_save_writes_to_sheet(self):
        self.connect()
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        self.assertEqual(Product.objects.get().sync_status, 'synced')
        row = self.sheet.tabs['Products']['147123049946']
        self.assertEqual(row['seller_price'], 23.99)
        self.assertEqual(row['ebay_link'], 'https://www.ebay.com/itm/147123049946')

    def test_duplicate_asks_then_updates(self):
        self.connect()
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        r = self.client.post(reverse('ebay_dropshipping:product_add'), product_data(listed_price='9.99'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Update existing row')
        self.assertEqual(Product.objects.get().listed_price, Decimal('6.88'))

        self.client.post(reverse('ebay_dropshipping:product_add'), product_data(listed_price='9.99', confirm_update='1'))
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Product.objects.get().listed_price, Decimal('9.99'))
        self.assertEqual(self.sheet.tabs['Products']['147123049946']['listed_price'], 9.99)

    def test_success_shows_sweetalert(self):
        r = self.client.post(reverse('ebay_dropshipping:product_add'), product_data(), follow=True)
        self.assertContains(r, 'class="d-none app-swal"')
        self.assertContains(r, 'Product saved!::')

    def test_tab_with_other_data_is_blocked(self):
        self.connect()
        handle = self.sheet.handle

        def with_info(action, p):
            if action == 'listTabs':
                return {'ok': True, 'tabs': ['US', 'Products'],
                        'tabInfo': [{'name': 'US', 'usable': False}, {'name': 'Products', 'usable': True}]}
            return handle(action, p)
        self.sheet.handle = with_info

        page = self.client.get(reverse('ebay_dropshipping:product_add')).content.decode()
        self.assertIn('US (has other data)', page)
        r = self.client.post(reverse('ebay_dropshipping:product_add'), product_data(tab_choice='US'))
        self.assertContains(r, 'already has other data')
        r = self.client.post(reverse('ebay_dropshipping:product_add'), product_data(tab_choice='__new__', new_tab='us'))
        self.assertContains(r, 'already has other data')
        self.assertFalse(Product.objects.exists())

    def test_all_tabs_blocked_suggests_a_new_tab_name(self):
        self.connect()
        handle = self.sheet.handle
        self.sheet.handle = lambda action, p: (
            {'ok': True, 'tabs': ['US'], 'tabInfo': [{'name': 'US', 'usable': False}]}
            if action == 'listTabs' else handle(action, p))
        page = self.client.get(reverse('ebay_dropshipping:product_add')).content.decode()
        self.assertIn('value="eBay Products"', page)
        r = self.client.post(reverse('ebay_dropshipping:product_add'), product_data(tab_choice='__new__', new_tab='eBay Products'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Product.objects.get().tab, 'eBay Products')

    def test_item_id_accepts_a_full_ebay_link(self):
        self.client.post(reverse('ebay_dropshipping:product_add'),
                         product_data(item_id='https://www.ebay.com/itm/Flea-Drops/256677889900?hash=item3b&var=0'))
        self.assertEqual(Product.objects.get().item_id, '256677889900')

    def test_errors_are_listed_for_the_popup(self):
        r = self.client.post(reverse('ebay_dropshipping:product_add'), product_data(tab_choice='__new__', new_tab='', item_id='abc'))
        self.assertContains(r, 'New tab name: Type a name for the new tab.')
        self.assertContains(r, 'ID: The eBay item ID should contain digits only (or paste the eBay listing link).')

    def test_create_new_tab(self):
        self.connect()
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data(tab_choice='__new__', new_tab='Kitchen'))
        self.assertEqual(Product.objects.get().tab, 'Kitchen')
        self.assertIn('147123049946', self.sheet.tabs['Kitchen'])
        r = self.client.post(reverse('ebay_dropshipping:product_add'), product_data(tab_choice='__new__', new_tab=''))
        self.assertContains(r, 'Type a name for the new tab')

    def test_moving_to_another_tab_removes_old_sheet_row(self):
        self.connect()
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        p = Product.objects.get()
        self.client.post(reverse('ebay_dropshipping:product_edit', args=[p.pk]), product_data(tab_choice='__new__', new_tab='Moved'))
        self.assertNotIn('147123049946', self.sheet.tabs['Products'])
        self.assertIn('147123049946', self.sheet.tabs['Moved'])

    def test_sheet_down_marks_error_and_next_sync_sends_it(self):
        self.connect()
        self.sheet.down = True
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        self.assertEqual(Product.objects.get().sync_status, 'error')
        self.sheet.down = False
        self.client.post(reverse('ebay_dropshipping:sync'))
        self.assertEqual(Product.objects.get().sync_status, 'synced')
        self.assertIn('147123049946', self.sheet.tabs['Products'])

    def test_delete_removes_from_sheet(self):
        self.connect()
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        p = Product.objects.get()
        self.client.post(reverse('ebay_dropshipping:product_delete', args=[p.pk]))
        self.assertFalse(Product.objects.exists())
        self.assertNotIn('147123049946', self.sheet.tabs['Products'])

    def test_delete_refused_when_sheet_unreachable(self):
        self.connect()
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        self.sheet.down = True
        self.client.post(reverse('ebay_dropshipping:product_delete', args=[Product.objects.get().pk]))
        self.assertTrue(Product.objects.exists())


class SyncTests(ModuleTestBase):
    def setUp(self):
        super().setUp()
        self.conf = self.connect()

    def test_rows_added_in_sheet_are_imported(self):
        self.sheet.tabs['Products']['999888777666'] = {
            'item_id': '999888777666', 'product_name': 'From the sheet', 'listed_price': 12.5,
            'supplier_cost': 4, 'status': 'Listed', 'seller_feedback': '', 'competitor_links': 'x',
        }
        summary = sheets.sync_all(self.conf)
        self.assertEqual(summary['created'], 1)
        p = Product.objects.get(item_id='999888777666')
        self.assertEqual(p.listed_price, Decimal('12.50'))
        self.assertEqual(p.status, 'Listed')
        self.assertIsNone(p.seller_feedback)

    def test_edits_in_sheet_update_django(self):
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        self.sheet.tabs['Products']['147123049946']['listed_price'] = 8.5
        self.sheet.tabs['Products']['147123049946']['status'] = 'Winning'
        self.assertEqual(sheets.sync_all(self.conf)['updated'], 1)
        p = Product.objects.get()
        self.assertEqual((p.listed_price, p.status), (Decimal('8.50'), 'Winning'))

    def test_rows_deleted_in_sheet_are_restored(self):
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        self.sheet.tabs['Products'].clear()
        self.assertEqual(sheets.sync_all(self.conf)['restored'], 1)
        self.assertIn('147123049946', self.sheet.tabs['Products'])

    def test_whole_tab_deleted_in_sheet_is_restored(self):
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        del self.sheet.tabs['Products']
        sheets.sync_all(self.conf)
        self.assertIn('147123049946', self.sheet.tabs['Products'])

    def test_newer_sheet_fees_win(self):
        self.sheet.settings = {'ebay_fee_pct': 15, 'ebay_fixed_fee': 0.4, 'ebay_fixed_fee_high': 0.5,
                               'fixed_fee_threshold': 12, 'ad_rate_pct': 3, 'sales_tax_pct': 7,
                               'updated_at': int(timezone.now().timestamp() * 1000) + 60000}
        sheets.sync_all(self.conf)
        self.conf.refresh_from_db()
        self.assertEqual((self.conf.ebay_fee_pct, self.conf.ad_rate_pct, self.conf.ebay_fixed_fee_high, self.conf.sales_tax_pct),
                         (Decimal('15.00'), Decimal('3.00'), Decimal('0.50'), Decimal('7.00')))

    def test_old_code_gs_settings_keep_new_fields(self):
        # An older Code.gs only sends three settings; the new ones must stay as they are.
        self.sheet.settings = {'ebay_fee_pct': 14, 'ebay_fixed_fee': 0.3, 'ad_rate_pct': 5,
                               'updated_at': int(timezone.now().timestamp() * 1000) + 60000}
        sheets.sync_all(self.conf)
        self.conf.refresh_from_db()
        self.assertEqual((self.conf.ebay_fee_pct, self.conf.ebay_fixed_fee_high), (Decimal('14.00'), Decimal('0.40')))

    def test_newer_django_fees_are_pushed(self):
        self.client.post(reverse('ebay_dropshipping:save_fees'),
                         {'ebay_fee_pct': '12', 'ebay_fixed_fee': '0.25', 'ebay_fixed_fee_high': '0.45',
                          'fixed_fee_threshold': '10', 'ad_rate_pct': '4', 'sales_tax_pct': '0'})
        self.assertEqual(self.sheet.settings['ebay_fee_pct'], 12.0)
        self.assertEqual(self.sheet.settings['ebay_fixed_fee_high'], 0.45)
        sheets.sync_all(self.conf)
        self.conf.refresh_from_db()
        self.assertEqual(self.conf.ebay_fee_pct, Decimal('12.00'))

    def test_sync_endpoint_json(self):
        r = self.client.post(reverse('ebay_dropshipping:sync'), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(r.json()['ok'])


class PagesAndAccessTests(ModuleTestBase):
    def test_pages_render(self):
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        p = Product.objects.get()
        for url in (reverse('ebay_dropshipping:product_list'), reverse('ebay_dropshipping:product_add'),
                    reverse('ebay_dropshipping:product_edit', args=[p.pk]), reverse('ebay_dropshipping:settings')):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_research_quick_fill_panel_is_on_the_form(self):
        page = self.client.get(reverse('ebay_dropshipping:product_add')).content.decode()
        for marker in ('id="supplier-platform"', 'id="btn-fill-supplier"', 'id="btn-add-competitor"', 'ebay-tool.js'):
            self.assertIn(marker, page)
        from django.contrib.staticfiles import finders
        body = open(finders.find('ebay_dropshipping/js/ebay-tool.js'), encoding='utf-8').read()
        for name in ('parseSupplier', 'parseCompetitor', 'AliExpress', 'CJ Dropshipping', 'Temu', 'Local / Other'):
            self.assertIn(name, body)

    def test_clear_shipping_labels_and_red_loss(self):
        page = self.client.get(reverse('ebay_dropshipping:product_add')).content.decode()
        self.assertIn('Competitor Shipping', page)
        self.assertIn('My Buyer Shipping', page)
        # Selling below cost → negative profit shown in red in the list.
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data(listed_price='3.00'))
        p = Product.objects.get()
        self.assertLess(p.calc()['profit'], 0)
        html = self.client.get(reverse('ebay_dropshipping:product_list')).content.decode()
        self.assertIn(f'text-danger">${p.calc()["profit"]}', html)

    def test_script_download_contains_key_and_parser(self):
        code = self.client.get(reverse('ebay_dropshipping:download_script', args=['Code.gs'])).content.decode()
        self.assertIn(f"const SYNC_KEY = '{DropshipSettings.load().sync_token}';", code)
        self.assertIn("SYNC_KEY === 'PASTE_YOUR_SYNC_KEY_HERE'", code)  # safety check kept intact
        form = self.client.get(reverse('ebay_dropshipping:download_script', args=['Form.html'])).content.decode()
        self.assertIn('var EbayTool', form)
        self.assertNotIn('__EBAY_TOOL__', form)

    def test_role_without_module_is_blocked(self):
        analyst = User.objects.create_user('ana', 'ana@example.com', 'S3cure-pass!', role=Role.objects.get(slug='analyst'))
        self.client.force_login(analyst)
        self.assertEqual(self.client.get(reverse('ebay_dropshipping:product_list')).status_code, 403)


class ImageAndOneClickTests(ModuleTestBase):
    IMG = 'https://i.ebayimg.com/images/g/abc/s-l1600.jpg'

    def test_image_is_saved_shown_and_sent_to_sheet(self):
        self.connect()
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data(image_url=self.IMG))
        self.assertEqual(Product.objects.get().image_url, self.IMG)
        self.assertEqual(self.sheet.tabs['Products']['147123049946']['image_url'], self.IMG)
        self.assertContains(self.client.get(reverse('ebay_dropshipping:product_list')), f'src="{self.IMG}"')

    def test_image_comes_back_from_sheet(self):
        self.connect()
        self.client.post(reverse('ebay_dropshipping:product_add'), product_data())
        self.sheet.tabs['Products']['147123049946']['image_url'] = self.IMG
        self.client.post(reverse('ebay_dropshipping:sync'))
        self.assertEqual(Product.objects.get().image_url, self.IMG)

    def test_settings_page_has_working_bookmarklet(self):
        from urllib.parse import unquote
        html = self.client.get(reverse('ebay_dropshipping:settings')).content.decode()
        m = re.search(r'href="(javascript:[^"]+)" class="btn btn-success" id="bookmarklet-btn"', html)
        self.assertIsNotNone(m)
        code = unquote(m.group(1)[len('javascript:'):].replace('&#x27;', "'"))
        self.assertIn("var TOOL = 'http://testserver';", code)
        self.assertIn('/static/ebay_dropshipping/capture.html#', code)
        self.assertNotIn('__TOOL__', code)

    def test_capture_page_and_form_receiver_exist(self):
        from django.contrib.staticfiles import finders
        self.assertIsNotNone(finders.find('ebay_dropshipping/capture.html'))
        html = self.client.get(reverse('ebay_dropshipping:product_add')).content.decode()
        self.assertIn("new BroadcastChannel('ebay-capture')", html)
        self.assertIn("localStorage.getItem('ebay-capture-pending')", html)


class TableTests(ModuleTestBase):
    COMPS = [
        {'seller': 'Small', 'link': 'https://www.ebay.com/itm/226000000002', 'price': '22', 'shipping': '0', 'sold': '5', 'feedback': '99999'},
        {'seller': 'Big', 'link': 'https://www.ebay.com/itm/226000000001', 'price': '21.5', 'shipping': '1', 'sold': '50', 'feedback': '9000'},
    ]
    SUPS = [
        {'source': 'amazon', 'link': 'https://www.amazon.com/dp/B0ABCDE123', 'cost': '12.49', 'shipping': '0'},
        {'source': 'aliexpress', 'link': 'https://www.aliexpress.com/item/1005.html', 'cost': '3.10', 'shipping': '0.71'},
    ]

    def post(self, comps, sups, **extra):
        data = product_data(competitors=json.dumps(comps), suppliers=json.dumps(sups), **extra)
        for f in ('competitor_links', 'competitor_feedbacks', 'competitor_sold', 'supplier_link', 'supplier_cost', 'supplier_shipping'):
            data.pop(f)
        return self.client.post(reverse('ebay_dropshipping:product_add'), data)

    def test_biggest_competitor_and_cheapest_supplier_fill_the_single_fields(self):
        self.connect()
        self.post(self.COMPS, self.SUPS)
        p = Product.objects.get()
        self.assertEqual(len(p.competitors), 2)
        self.assertEqual((p.competitor_sold, p.competitor_feedbacks), (50, 9000))   # biggest = most sold
        self.assertEqual(p.competitor_links.splitlines(), [c['link'] for c in self.COMPS])
        self.assertEqual((p.supplier_cost, p.supplier_shipping), (Decimal('3.10'), Decimal('0.71')))  # cheapest
        self.assertIn('aliexpress', p.supplier_link)
        row = self.sheet.tabs['Products']['147123049946']
        self.assertIn('★ Big | $21.50 | ship $1.00 | sold 50 | fb 9000 | https://www.ebay.com/itm/226000000001', row['competitors'])
        self.assertIn('✓ AliExpress | $3.10 | ship $0.71', row['suppliers'])

    def test_picked_main_competitor_and_supplier_win(self):
        comps = [dict(self.COMPS[0], pinned=True), self.COMPS[1]]
        sups = [dict(self.SUPS[0], pinned=True), self.SUPS[1]]
        self.post(comps, sups)
        p = Product.objects.get()
        self.assertEqual((p.competitor_sold, p.competitor_feedbacks), (5, 99999))
        self.assertEqual(p.supplier_cost, Decimal('12.49'))
        self.assertTrue(p.competitors[0]['pinned'] and p.suppliers[0]['pinned'])

    def test_tables_survive_a_round_trip_through_the_sheet(self):
        self.connect()
        self.post([dict(self.COMPS[0], pinned=True), self.COMPS[1]], self.SUPS)
        p = Product.objects.get()
        before = (p.competitors, p.suppliers)
        Product.objects.all().delete()
        self.client.post(reverse('ebay_dropshipping:sync'))   # imported back from the sheet
        p = Product.objects.get()
        self.assertEqual((p.competitors, p.suppliers), before)
        self.assertEqual(p.competitor_sold, 5)

    def test_single_field_edited_in_sheet_updates_the_table_row(self):
        self.connect()
        self.post(self.COMPS, self.SUPS)
        self.sheet.tabs['Products']['147123049946']['supplier_cost'] = 2.5
        self.client.post(reverse('ebay_dropshipping:sync'))
        p = Product.objects.get()
        self.assertEqual(p.suppliers[1]['cost'], '2.50')
        self.assertEqual(p.supplier_cost, Decimal('2.50'))

    def test_bad_link_in_table_is_refused(self):
        r = self.post([{'seller': 'X', 'link': 'not a link'}], [])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Competitor row 1: the link must start with http')
        self.assertFalse(Product.objects.exists())

    def test_old_product_opens_with_tables_built_from_its_fields(self):
        p = Product.objects.create(tab='Products', item_id='111222333444', competitor_links='https://www.ebay.com/itm/1',
                                   competitor_sold=7, supplier_link='https://www.temu.com/x.html', supplier_cost=Decimal('4'))
        html = self.client.get(reverse('ebay_dropshipping:product_edit', args=[p.pk])).content.decode()
        self.assertIn('&quot;source&quot;: &quot;temu&quot;', html)
        self.assertIn('&quot;sold&quot;: &quot;7&quot;', html)

    def test_old_code_gs_without_table_columns_keeps_the_tables(self):
        # An older Code.gs doesn't know "All Competitors" / "All Suppliers": syncing must not wipe the tables.
        self.connect()
        self.post(self.COMPS, self.SUPS)
        before = Product.objects.get()
        for key in ('competitors', 'suppliers'):
            del self.sheet.tabs['Products']['147123049946'][key]
        self.client.post(reverse('ebay_dropshipping:sync'))
        p = Product.objects.get()
        self.assertEqual((p.competitors, p.suppliers), (before.competitors, before.suppliers))
        self.assertEqual(p.competitors[1]['seller'], 'Big')

    def test_empty_table_cells_keep_the_tables_and_are_filled_again(self):
        self.connect()
        self.post(self.COMPS, self.SUPS)
        row = self.sheet.tabs['Products']['147123049946']
        row['competitors'] = row['suppliers'] = ''
        self.client.post(reverse('ebay_dropshipping:sync'))
        self.assertEqual(len(Product.objects.get().suppliers), 2)
        self.assertIn('✓ AliExpress', self.sheet.tabs['Products']['147123049946']['suppliers'])
