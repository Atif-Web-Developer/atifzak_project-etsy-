import json
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from accounts.models import Role
from keywords.models import User

from . import rules, sheets
from .models import Hunt, StockSettings


class FakeSheet:
    """In-memory stand-in for the Apps Script web app (same actions as Code.gs)."""

    def __init__(self):
        self.products, self.competitors = {}, {}
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
        if action == 'upsert':
            sr = p['product']['sr_no']
            self.products[sr] = dict(p['product'])
            self.competitors[sr] = [dict(c) for c in p['competitors']]
            return {'ok': True}
        if action == 'delete':
            self.products.pop(p['sr_no'], None)
            self.competitors.pop(p['sr_no'], None)
            return {'ok': True}
        if action == 'pull':
            return {'ok': True, 'products': list(self.products.values()),
                    'competitors': [c for rows in self.competitors.values() for c in rows]}
        raise AssertionError(action)


def comps(*rows):
    """rows: (feedback, price, sales_30d)"""
    return [{'link': f'https://www.ebay.com/itm/22600000000{i}', 'feedback': fb, 'price': pr,
             'sales_30d': sa, 'variation': '1 pack'} for i, (fb, pr, sa) in enumerate(rows)]


GOOD = comps((1500, 19.99, 150), (8000, 21.5, 120), (300, 18, 40), (12000, 24, 20), (900, 22, 5))


def hunt_data(**over):
    data = {'main_keyword': 'Soft TPR Toy', 'sales_trend': 'Stable', 'two_sellers_100': '', 'avg_price': '',
            'market': 'US', 'total_sellers': '30', 'seller_listing_link': '', 'competitors': json.dumps(GOOD)}
    data.update(over)
    return data


def ns(**over):
    d = dict(main_keyword='Soft TPR Toy', sales_trend='Stable', two_sellers_100='', avg_price=None, market='US',
             total_sellers=30, seller_listing_link='', competitors=GOOD)
    d.update(over)
    return SimpleNamespace(**d)


class RulesTests(TestCase):
    def setUp(self):
        self.conf = StockSettings.load()

    def test_all_good_is_green_and_auto_values(self):
        r = rules.evaluate(ns(), self.conf)
        self.assertEqual(r['verdict'], 'green')
        self.assertEqual(r['two_sellers_100'], 'Yes')
        self.assertEqual(r['avg_price'], Decimal('21.10'))
        self.assertEqual(r['auto']['seller_listing_link'], GOOD[0]['link'])

    def test_many_sellers_is_yellow(self):
        self.assertEqual(rules.evaluate(ns(total_sellers=120), self.conf)['verdict'], 'yellow')

    def test_any_rule_fail_is_red(self):
        for over in ({'sales_trend': 'Down'},
                     {'competitors': comps((10, 9, 150), (10, 9, 150), (1, 9, 1))},
                     {'competitors': comps((1, 20, 150), (1, 20, 50), (1, 20, 1))},
                     {'competitors': comps((5000, 20, 150), (5000, 20, 150), (9000, 20, 1))},
                     {'two_sellers_100': 'No'}, {'avg_price': Decimal('50')}):
            self.assertEqual(rules.evaluate(ns(**over), self.conf)['verdict'], 'red', over)

    def test_typed_values_win_over_auto(self):
        r = rules.evaluate(ns(avg_price=Decimal('30'), two_sellers_100='Yes',
                              competitors=comps((1, 9, 150), (1, 9, 1))), self.conf)
        self.assertEqual((r['avg_price'], r['two_sellers_100'], r['verdict']), (Decimal('30'), 'Yes', 'green'))

    def test_missing_data_is_incomplete(self):
        self.assertEqual(rules.evaluate(ns(competitors=[]), self.conf)['verdict'], 'incomplete')
        self.assertEqual(rules.evaluate(ns(sales_trend=''), self.conf)['verdict'], 'incomplete')

    def test_uk_uses_pounds(self):
        r = rules.evaluate(ns(market='UK'), self.conf)
        self.assertEqual(r['currency'], '£')
        self.assertIn('£13–£35', [c['label'] for c in r['checks'] if c['key'] == 'price'][0])


class ModuleTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('boss', 'boss@example.com', 'S3cure-pass!',
                                             role=Role.objects.get(slug='administrator'))
        self.client.force_login(self.user)
        self.sheet = FakeSheet()
        patcher = mock.patch.object(sheets, 'SheetClient', side_effect=self.sheet.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def connect(self):
        conf = StockSettings.load()
        conf.sheet_webapp_url = 'https://script.google.com/macros/s/abc/exec'
        conf.save()

    def add(self, **over):
        return self.client.post(reverse('stock_hunting:hunt_add'), hunt_data(**over))


class HuntTests(ModuleTestBase):
    def test_save_without_sheet_keeps_it_pending_and_numbers_hunts(self):
        r = self.add()
        self.assertRedirects(r, reverse('stock_hunting:hunt_list'), fetch_redirect_response=False)
        self.add(main_keyword='Second')
        self.assertEqual(list(Hunt.objects.order_by('sr_no').values_list('sr_no', 'sync_status')), [(1, 'pending'), (2, 'pending')])
        self.assertEqual(len(Hunt.objects.get(sr_no=1).competitors), 5)

    def test_save_writes_both_tabs_with_only_mams_columns(self):
        self.connect()
        self.add()
        row = self.sheet.products[1]
        self.assertEqual(set(row), {'sr_no', 'main_keyword', 'sales_trend', 'two_sellers_100', 'avg_price',
                                    'total_sellers', 'seller_listing_link'})
        self.assertEqual((row['main_keyword'], row['two_sellers_100'], row['avg_price'], row['seller_listing_link']),
                         ('Soft TPR Toy', 'Yes', 21.1, GOOD[0]['link']))
        self.assertEqual(len(self.sheet.competitors[1]), 5)
        self.assertEqual(set(self.sheet.competitors[1][0]),
                         {'sr_no', 'main_keyword', 'link', 'feedback', 'price', 'sales_30d', 'variation'})
        self.assertEqual(self.sheet.competitors[1][0]['main_keyword'], 'Soft TPR Toy')
        self.assertEqual(Hunt.objects.get().sync_status, 'synced')

    def test_typed_values_are_kept(self):
        self.add(avg_price='25', two_sellers_100='No', seller_listing_link='https://www.ebay.com/itm/9')
        h = Hunt.objects.get()
        self.assertEqual((h.avg_price, h.two_sellers_100, h.seller_listing_link),
                         (Decimal('25.00'), 'No', 'https://www.ebay.com/itm/9'))

    def test_bad_competitor_link_is_refused(self):
        r = self.add(competitors=json.dumps([{'link': 'not a link'}]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Competitor row 1: the link must start with http')
        self.assertFalse(Hunt.objects.exists())

    def test_evaluate_endpoint(self):
        d = self.client.post(reverse('stock_hunting:evaluate'), hunt_data(total_sellers='99')).json()
        self.assertEqual(d['verdict'], 'yellow')
        self.assertEqual(d['avg_price'], '21.10')
        self.assertEqual(d['auto']['two_sellers_100'], 'Yes')

    def test_delete_removes_from_sheet(self):
        self.connect()
        self.add()
        self.client.post(reverse('stock_hunting:hunt_delete', args=[Hunt.objects.get().pk]))
        self.assertFalse(Hunt.objects.exists())
        self.assertEqual(self.sheet.products, {})

    def test_delete_refused_when_sheet_unreachable(self):
        self.connect()
        self.add()
        self.sheet.down = True
        self.client.post(reverse('stock_hunting:hunt_delete', args=[Hunt.objects.get().pk]))
        self.assertTrue(Hunt.objects.exists())


class SyncTests(ModuleTestBase):
    def setUp(self):
        super().setUp()
        self.connect()

    def test_rows_added_in_sheet_are_imported(self):
        self.sheet.products[7] = {'sr_no': 7, 'main_keyword': 'Pet brush', 'sales_trend': 'up',
                                  'two_sellers_100': 'yes', 'avg_price': '£15.50', 'total_sellers': 40}
        self.sheet.competitors[7] = [{'sr_no': 7, 'link': 'https://www.ebay.co.uk/itm/1', 'feedback': 120,
                                      'price': '£15.00', 'sales_30d': 110}]
        self.client.post(reverse('stock_hunting:sync'))
        h = Hunt.objects.get(sr_no=7)
        self.assertEqual((h.market, h.sales_trend, h.two_sellers_100, h.avg_price, h.total_sellers),
                         ('UK', 'Up', 'Yes', Decimal('15.50'), 40))
        self.assertEqual(h.competitors[0]['price'], '15.00')
        self.assertEqual(h.competitors[0]['sales_30d'], '110')
        self.assertEqual(Hunt.next_sr_no(), 8)

    def test_edits_in_sheet_update_django(self):
        self.add()
        self.sheet.products[1]['sales_trend'] = 'Down'
        self.sheet.competitors[1][0]['price'] = 30
        self.client.post(reverse('stock_hunting:sync'))
        h = Hunt.objects.get()
        self.assertEqual(h.sales_trend, 'Down')
        self.assertEqual(h.competitors[0]['price'], '30.00')
        self.assertEqual(h.evaluate()['verdict'], 'red')

    def test_empty_sheet_cells_never_wipe_ours(self):
        self.add()
        self.sheet.products[1].update(main_keyword='', avg_price='', total_sellers='', sales_trend='')
        self.client.post(reverse('stock_hunting:sync'))
        h = Hunt.objects.get()
        self.assertEqual((h.main_keyword, h.avg_price, h.total_sellers, h.sales_trend),
                         ('Soft TPR Toy', Decimal('21.10'), 30, 'Stable'))

    def test_rows_deleted_in_sheet_are_restored(self):
        self.add()
        self.sheet.products.clear()
        self.sheet.competitors.clear()
        self.client.post(reverse('stock_hunting:sync'))
        self.assertIn(1, self.sheet.products)
        self.assertEqual(len(self.sheet.competitors[1]), 5)

    def test_missing_competitor_rows_never_wipe_ours(self):
        self.add()
        self.sheet.competitors.clear()
        self.client.post(reverse('stock_hunting:sync'))
        self.assertEqual(len(Hunt.objects.get().competitors), 5)
        self.assertEqual(len(self.sheet.competitors[1]), 5)   # written back

    def test_pending_hunts_are_sent(self):
        self.sheet.down = True
        self.add()
        self.assertEqual(Hunt.objects.get().sync_status, 'error')
        self.sheet.down = False
        self.client.post(reverse('stock_hunting:sync'))
        self.assertEqual(Hunt.objects.get().sync_status, 'synced')


class PagesTests(ModuleTestBase):
    def test_pages_render(self):
        self.add()
        h = Hunt.objects.get()
        for name, args in (('hunt_list', []), ('hunt_add', []), ('hunt_edit', [h.pk]), ('guide', []), ('settings', [])):
            self.assertEqual(self.client.get(reverse(f'stock_hunting:{name}', args=args)).status_code, 200, name)
        self.assertContains(self.client.get(reverse('stock_hunting:hunt_list')), 'Source karein')
        self.assertContains(self.client.get(reverse('stock_hunting:guide')), 'Ek bhi fail ho to yahin ruk jayein')

    def test_form_has_only_the_sheet_fields(self):
        form = self.client.get(reverse('stock_hunting:hunt_add')).content.decode()
        for label in ('Product selection', 'Competitors selection', 'Main Keyword', 'Sales Trend',
                      '2 Sellers with 100 above sales', 'Avg sales price', 'Total Sellers', 'seller listing link',
                      'Listing link of competitors', 'Seller Feedback', '30 Days sales of competitors',
                      'pack/colour variation of competitors'):
            self.assertIn(label, form)
        for gone in ('AliExpress rating', 'Test quantity', 'Source quantity', 'name="status"', 'name="ali_rating"'):
            self.assertNotIn(gone, form)

    def test_filter_by_verdict(self):
        self.add()
        self.add(main_keyword='Bad one', sales_trend='Down')
        self.client.get(reverse('stock_hunting:hunt_list'))  # shows (and clears) the "saved" popups
        html = self.client.get(reverse('stock_hunting:hunt_list') + '?verdict=red').content.decode()
        self.assertIn('Bad one', html)
        self.assertNotIn('Soft TPR Toy', html)

    def test_script_has_key(self):
        code = self.client.get(reverse('stock_hunting:download_script')).content.decode()
        self.assertIn(f"const SYNC_KEY = '{StockSettings.load().sync_token}';", code)
        self.assertIn("SYNC_KEY === 'PASTE_YOUR_SYNC_KEY_HERE'", code)

    def test_role_without_module_is_blocked(self):
        analyst = User.objects.create_user('ana', 'ana@example.com', 'S3cure-pass!', role=Role.objects.get(slug='analyst'))
        self.client.force_login(analyst)
        self.assertEqual(self.client.get(reverse('stock_hunting:hunt_list')).status_code, 403)
