/**
 * eBay Dropshipping – Google Sheets side
 * ======================================
 * 1. Adds the menu "eBay Dropshipping → Open form" with a sidebar form (Form.html).
 * 2. Works as a web app so the Atif-Zak Analytics website can sync products both ways.
 *
 * Where to change things:
 *   - COLUMNS  : the column list (order, headers, form fields). Keys must match the website.
 *   - FORMULAS : the profit formulas written into every row.
 *   - Fee settings live on the "eBay Settings" tab (named ranges used by the formulas).
 */

// Filled in automatically when you copy this file from the website's Settings page.
const SYNC_KEY = 'PASTE_YOUR_SYNC_KEY_HERE';

const SETTINGS_TAB = 'eBay Settings';
const STATUS_OPTIONS = ['Researching', 'Testing', 'Listed', 'Winning', 'Rejected'];
const DEFAULT_SETTINGS = {
  ebay_fee_pct: 13.6, ebay_fixed_fee: 0.30, ebay_fixed_fee_high: 0.40, fixed_fee_threshold: 10,
  ad_rate_pct: 5, sales_tax_pct: 0,
};
const HEADER_STYLE = { background: '#434343', font: '#FFFFFF' };  // "eBay Settings" tab header

/* =====================================================================
 * COLUMNS – in sheet order.
 *   group: auto (filled from the pasted eBay text) | manual (you type) | calc (formula)
 *   type : text | number | money | url | image | textarea | status | link | calc
 *          (image: the cell shows the picture with =IMAGE("link"); the link is what syncs)
 *   aliases: old header names – an existing tab with an old name is renamed automatically.
 * ===================================================================== */
const COLUMNS = [
  { key: 'item_id',              header: 'ID',                               group: 'auto',   type: 'text' },
  { key: 'product_name',         header: 'Product Name',                     group: 'auto',   type: 'text' },
  { key: 'ebay_link',            header: 'eBay Item Link',                   group: 'auto',   type: 'link' },
  { key: 'image_url',            header: 'Image',                            group: 'auto',   type: 'image' },
  { key: 'seller_name',          header: 'Seller Name',                      group: 'auto',   type: 'text' },
  { key: 'seller_feedback',      header: 'Total Seller Feedback Count',      group: 'auto',   type: 'number' },
  { key: 'seller_price',         header: 'eBay Seller Price',                group: 'auto',   type: 'money' },
  { key: 'buyer_shipping',       header: 'Competitor Shipping',              group: 'auto',   type: 'money', aliases: ['Buyer Shipping'] },
  { key: 'sold_orders',          header: 'Sold / Orders',                    group: 'auto',   type: 'number' },
  { key: 'sales_line',           header: 'Sales Line',                       group: 'auto',   type: 'text' },
  { key: 'variation',            header: 'Variation',                        group: 'auto',   type: 'text' },
  { key: 'supplier_link',        header: 'Supplier Link',                    group: 'manual', type: 'url' },
  { key: 'supplier_cost',        header: 'Supplier Cost',                    group: 'manual', type: 'money' },
  { key: 'supplier_shipping',    header: 'Supplier Shipping',                group: 'manual', type: 'money' },
  { key: 'other_cost',           header: 'Sourcing Buying Fee / Other Cost', group: 'manual', type: 'money', default: '0' },
  { key: 'suppliers',            header: 'All Suppliers',                    group: 'manual', type: 'textarea',
    placeholder: '✓ Amazon | $12.49 | ship $0 | https://…  (one supplier per line)' },
  { key: 'competitor_links',     header: 'Competitor Links',                 group: 'manual', type: 'textarea' },
  { key: 'competitor_feedbacks', header: 'Competitor No. of Feedbacks',      group: 'manual', type: 'number' },
  { key: 'competitor_sold',      header: 'Competitor Solds / Orders',        group: 'manual', type: 'number' },
  { key: 'competitors',          header: 'All Competitors',                  group: 'manual', type: 'textarea',
    placeholder: '★ Seller | $23.99 | ship $0 | sold 20 | fb 1236 | https://…  (one per line)' },
  { key: 'listed_price',         header: 'My Listed Price',                  group: 'manual', type: 'money' },
  { key: 'my_shipping',          header: 'My Buyer Shipping',                group: 'manual', type: 'money', default: '0', aliases: ['My Shipping Charge'] },
  { key: 'status',               header: 'Status',                           group: 'manual', type: 'status', default: 'Researching' },
  { key: 'total_sale',           header: 'Total Sale',                       group: 'calc',   type: 'calc' },
  { key: 'ebay_fee',             header: 'eBay Fee',                         group: 'calc',   type: 'calc' },
  { key: 'ad_fee',               header: 'Ad Fee',                           group: 'calc',   type: 'calc' },
  { key: 'total_cost',           header: 'Total Cost',                       group: 'calc',   type: 'calc', aliases: ['Minimum Listing Price'] },
  { key: 'profit',               header: 'Profit',                           group: 'calc',   type: 'calc' },
  { key: 'profit_pct',           header: 'Profit Percentage',                group: 'calc',   type: 'calc' },
  { key: 'break_even',           header: 'Break-even Price',                 group: 'calc',   type: 'calc' },
  { key: 'roi',                  header: 'ROI %',                            group: 'calc',   type: 'calc' },
];

/* =====================================================================
 * FORMULAS – c('key') gives the cell of that column in the same row (e.g. "R5").
 * Settings are named ranges on the "eBay Settings" tab:
 *   EBAY_FEE_PCT, EBAY_FIXED_FEE (order ≤ threshold), EBAY_FIXED_FEE_HIGH (order > threshold),
 *   FIXED_FEE_THRESHOLD, AD_RATE_PCT, SALES_TAX_PCT.
 * Everything except Break-even shows an empty cell when My Listed Price is empty;
 * Break-even shows an empty cell when Supplier Cost is empty.
 * ===================================================================== */
const costs_ = c => `N(${c('supplier_cost')})+N(${c('supplier_shipping')})+N(${c('other_cost')})`;
const FORMULAS = {
  // Total Sale = My Listed Price + My Buyer Shipping (the competitor's shipping is NOT used)
  total_sale: c => `=IF(${c('listed_price')}="","",${c('listed_price')}+N(${c('my_shipping')}))`,
  // eBay Fee = Total Sale × (1 + Sales Tax %) × eBay Fee % + (Total Sale ≤ threshold ? low fixed fee : high fixed fee)
  ebay_fee:   c => `=IF(${c('listed_price')}="","",${c('total_sale')}*(1+SALES_TAX_PCT)*EBAY_FEE_PCT+IF(${c('total_sale')}<=FIXED_FEE_THRESHOLD,EBAY_FIXED_FEE,EBAY_FIXED_FEE_HIGH))`,
  // Ad Fee = Total Sale × Ad Rate %
  ad_fee:     c => `=IF(${c('listed_price')}="","",${c('total_sale')}*AD_RATE_PCT)`,
  // Total Cost = Supplier Cost + Supplier Shipping + Other Cost + eBay Fee + Ad Fee
  total_cost: c => `=IF(${c('listed_price')}="","",${costs_(c)}+${c('ebay_fee')}+${c('ad_fee')})`,
  // Profit = Total Sale − Total Cost
  profit:     c => `=IF(${c('listed_price')}="","",${c('total_sale')}-${c('total_cost')})`,
  // Profit Percentage = Profit ÷ Total Sale × 100
  profit_pct: c => `=IF(OR(${c('listed_price')}="",N(${c('total_sale')})=0),"",(${c('profit')}/${c('total_sale')})*100)`,
  // Break-even Price = (costs + high fixed fee) ÷ (1 − Fee % × (1 + Tax %) − Ad %) − My Buyer Shipping
  break_even: c => `=IF(${c('supplier_cost')}="","",(${costs_(c)}+EBAY_FIXED_FEE_HIGH)/(1-EBAY_FEE_PCT*(1+SALES_TAX_PCT)-AD_RATE_PCT)-N(${c('my_shipping')}))`,
  // ROI % = Profit ÷ (Supplier Cost + Supplier Shipping + Other Cost) × 100
  roi:        c => `=IF(OR(${c('listed_price')}="",(${costs_(c)})=0),"",${c('profit')}/(${costs_(c)})*100)`,
};


/* =====================================================================
 * SHEET STYLE – how product tabs look (header colours, notes, widths, number formats).
 * Only formatting: applying it never changes data or formulas, and it is safe to run again.
 * ===================================================================== */
const SHEET_STYLE = {
  headerHeight: 45,
  headerFontSize: 10,
  headerFont: '#FFFFFF',
  groups: {
    auto:   { background: '#1F4E78', note: 'Auto Fill: eBay page paste se khud bharta hai. Check kar ke theek kar sakte hain.' },
    manual: { background: '#38761D', note: 'Manual: ye aap khud likhte hain.' },
    calc:   { background: '#434343', note: 'Calculated: khud banta hai (formula), edit na karein.' },
  },
  calcDataBackground: '#F3F3F3',
  banding: { first: '#FFFFFF', second: '#F6F8FA' },
  moneyFormat: '$#,##0.00;[Red]-$#,##0.00',
  percentFormat: '0.00"%";[Red]-0.00"%"',
  countFormat: '#,##0',
  // Default width per column type, and exceptions per column (pixels).
  widths: { image: 70, text: 140, number: 95, money: 100, url: 180, link: 180, textarea: 200, status: 115, calc: 105 },
  widthByKey: { suppliers: 280, competitors: 320, item_id: 125, product_name: 300, sales_line: 230, variation: 85, total_cost: 110, break_even: 115 },
};
const PERCENT_COLUMNS = ['profit_pct', 'roi'];  // values are already × 100, so they get a "%" sign, not % format

// Short explanation shown when you hover a header.
const COLUMN_NOTES = {
  item_id: 'eBay listing ka Item ID (sirf digits).',
  product_name: 'Listing ka title.',
  ebay_link: 'ID se banta hai: ebay.com/itm/ID',
  image_url: 'Product ki tasveer. Bari dekhne ke liye row ki height barha dein.',
  seller_name: 'Competitor seller ka naam.',
  seller_feedback: 'Competitor seller ke total feedback.',
  seller_price: 'Competitor ki price.',
  buyer_shipping: 'Competitor ki shipping. Sirf muqable ke liye, hisaab mein shamil nahi.',
  sold_orders: 'Competitor ki listing kitni biki.',
  sales_line: 'Kis waqt mein kitni sales (24h, 3d, 1w, 2w, 1m, 3m).',
  variation: 'Listing mein variations hain ya nahi.',
  supplier_link: 'Jahan se aap product khareedenge.',
  supplier_cost: 'Supplier ki price.',
  supplier_shipping: 'Supplier ki shipping.',
  other_cost: 'Sourcing/buying fee ya koi aur kharcha (warna 0).',
  competitor_links: 'Doosre competitors ke links, har line mein ek.',
  suppliers: 'Saare suppliers, har line mein ek: Source | $cost | ship $x | link. ✓ = profit isi se (warna sab se sasta).',
  competitors: 'Saare competitors, har line mein ek: Seller | $price | ship $x | sold n | fb n | link. ★ = Main (warna sab se bara).',
  competitor_feedbacks: 'Competitor ke feedback.',
  competitor_sold: 'Competitor ki sales.',
  listed_price: 'Jis price par aap list karenge.',
  my_shipping: 'Jo shipping AAP buyer se lenge (0 = free). Fee aur profit isi se.',
  status: 'Researching, Testing, Listed, Winning ya Rejected.',
  total_sale: 'My Listed Price + My Buyer Shipping.',
  ebay_fee: 'Total Sale × (1 + Tax %) × Fee % + fixed fee ($0.30 / $0.40).',
  ad_fee: 'Total Sale × Ad Rate %.',
  total_cost: 'Supplier Cost + Supplier Shipping + Other Cost + eBay Fee + Ad Fee.',
  profit: 'Total Sale − Total Cost. Manfi = loss (laal).',
  profit_pct: 'Profit ÷ Total Sale × 100.',
  break_even: 'Is price se neeche list kiya to loss hoga.',
  roi: 'Profit ÷ (Supplier Cost + Supplier Shipping + Other Cost) × 100.',
};


/* =====================================================================
 * Menu + sidebar
 * ===================================================================== */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('eBay Dropshipping')
    .addItem('Open form', 'showForm')
    .addItem('Update formulas in all rows', 'refreshAllFormulas')
    .addItem('Format headers', 'formatAllTabs')
    .addToUi();
}

/** Applies SHEET_STYLE to every product tab (only formatting – data and formulas are untouched). */
function formatAllTabs() {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  let tabs = 0;
  try {
    const ss = SpreadsheetApp.getActive();
    productTabNames_().forEach(name => {
      const sheet = ss.getSheetByName(name);
      if (!headerMap_(sheet).item_id) return;  // not one of this tool's tabs – never touched
      formatSheet_(sheet);
      tabs++;
    });
  } finally {
    lock.releaseLock();
  }
  SpreadsheetApp.getActive().toast(tabs + ' tab(s) formatted.', 'eBay Dropshipping', 5);
  return tabs;
}

/** Rewrites the calculated columns of every product row (use after changing FORMULAS). */
function refreshAllFormulas() {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  let rows = 0;
  try {
    ensureSettingsTab_();
    const ss = SpreadsheetApp.getActive();
    productTabNames_().forEach(name => {
      const sheet = ss.getSheetByName(name);
      if (!headerMap_(sheet).item_id) return;  // not one of this tool's tabs
      ensureHeaders_(sheet);
      rows += writeFormulas_(sheet);
    });
  } finally {
    lock.releaseLock();
  }
  SpreadsheetApp.getActive().toast(rows + ' row(s) updated with the latest formulas.', 'eBay Dropshipping', 5);
  return rows;
}

/** Writes FORMULAS into rows 2…last of a tab; returns the number of rows updated. */
function writeFormulas_(sheet) {
  const last = sheet.getLastRow();
  if (last < 2) return 0;
  const map = headerMap_(sheet);
  COLUMNS.filter(c => c.type === 'calc' && map[c.key]).forEach(c => {
    const formulas = [];
    for (let r = 2; r <= last; r++) {
      const cell = key => columnLetter_(map[key]) + r;
      formulas.push([FORMULAS[c.key](cell)]);
    }
    sheet.getRange(2, map[c.key], last - 1, 1).setFormulas(formulas);  // formats come from formatSheet_
  });
  return last - 1;
}

function showForm() {
  const html = HtmlService.createHtmlOutputFromFile('Form').setTitle('eBay Dropshipping');
  SpreadsheetApp.getUi().showSidebar(html);
}

/** Data the sidebar needs when it opens. */
function getFormData() {
  const info = tabInfo_();
  const usable = info.filter(t => t.usable).map(t => t.name);
  const lastTab = PropertiesService.getUserProperties().getProperty('lastTab');
  return {
    tabs: info,
    lastTab: usable.indexOf(lastTab) !== -1 ? lastTab : (usable[0] || '__new__'),
    settings: readSettings_(),
    statuses: STATUS_OPTIONS,
    columns: COLUMNS,
  };
}

function saveSettingsFromForm(settings) {
  writeSettings_(settings, Date.now());
  return readSettings_();
}

/**
 * Called by the sidebar's Submit button.
 * Returns {duplicate:true,…} when the Item ID already exists and confirmUpdate is false.
 */
function submitProduct(data, tabChoice, newTabName, confirmUpdate) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    let tabName = tabChoice;
    if (tabChoice === '__new__') {
      tabName = String(newTabName || '').trim();
      if (!tabName) throw new Error('Type a name for the new tab.');
      if (tabName === SETTINGS_TAB) throw new Error('Please choose another tab name.');
    }
    if (!tabName) throw new Error('Choose a tab.');
    const itemId = String(data.item_id || '').replace(/\s+/g, '');
    if (!/^\d+$/.test(itemId)) throw new Error('Item ID is required (digits only).');
    data.item_id = itemId;

    const sheet = getOrCreateTab_(tabName);
    const existingRow = findRowById_(sheet, itemId);
    if (existingRow && !confirmUpdate) {
      return { duplicate: true, tab: tabName, row: existingRow };
    }
    const row = writeRow_(sheet, existingRow || sheet.getLastRow() + 1, data);
    PropertiesService.getUserProperties().setProperty('lastTab', tabName);
    return { ok: true, updated: !!existingRow, tab: tabName, row: row };
  } finally {
    lock.releaseLock();
  }
}


/* =====================================================================
 * Web app API (used by the website to sync)
 * ===================================================================== */

function doGet() {
  return json_({ ok: true, message: 'eBay Dropshipping sync is running. Use the website to sync.' });
}

function doPost(e) {
  let req;
  try {
    req = JSON.parse(e.postData.contents);
  } catch (err) {
    return json_({ ok: false, error: 'Bad request.' });
  }
  if (!SYNC_KEY || SYNC_KEY === 'PASTE_YOUR_SYNC_KEY_HERE' || req.token !== SYNC_KEY) {
    return json_({ ok: false, error: 'Wrong sync key. Copy Code.gs again from the website Settings page and redeploy.' });
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    switch (req.action) {
      case 'ping':
        ensureSettingsTab_();
        return json_({ ok: true, spreadsheet: SpreadsheetApp.getActive().getName() });

      case 'listTabs':
        return json_({ ok: true, tabs: productTabNames_(), tabInfo: tabInfo_() });

      case 'upsert': {
        ensureSettingsTab_(req.fees);
        const sheet = getOrCreateTab_(req.tab);
        const id = String(req.row.item_id);
        const row = writeRow_(sheet, findRowById_(sheet, id) || sheet.getLastRow() + 1, req.row);
        return json_({ ok: true, row: row });
      }

      case 'delete': {
        const sheet = SpreadsheetApp.getActive().getSheetByName(req.tab);
        const row = sheet ? findRowById_(sheet, String(req.item_id)) : 0;
        if (row) sheet.deleteRow(row);
        return json_({ ok: true, deleted: !!row });
      }

      case 'pull':
        return json_({ ok: true, tabs: readAllProducts_(), settings: readSettings_() });

      case 'saveSettings':
        writeSettings_(req.fees, req.updated_at || Date.now());
        return json_({ ok: true });

      default:
        return json_({ ok: false, error: 'Unknown action: ' + req.action });
    }
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err) });
  } finally {
    lock.releaseLock();
  }
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}


/* =====================================================================
 * Sheet helpers
 * ===================================================================== */

/** All tabs except the settings tab. */
function productTabNames_() {
  return SpreadsheetApp.getActive().getSheets()
    .map(s => s.getName())
    .filter(n => n !== SETTINGS_TAB);
}

/** A tab is usable when it is empty or already has this tool's "ID" header. */
function isUsableTab_(sheet) {
  return sheet.getLastRow() === 0 || !!headerMap_(sheet).item_id;
}

/** [{name, usable}] – tabs that already hold other data are protected. */
function tabInfo_() {
  const ss = SpreadsheetApp.getActive();
  return productTabNames_().map(name => ({ name: name, usable: isUsableTab_(ss.getSheetByName(name)) }));
}

/** Returns the tab, creating it only when it doesn't exist. Never creates a new spreadsheet. */
function getOrCreateTab_(name) {
  const ss = SpreadsheetApp.getActive();
  const sheet = ss.getSheetByName(name) || ss.insertSheet(name);
  ensureSettingsTab_();  // first, so the formulas' named ranges exist
  ensureHeaders_(sheet);
  return sheet;
}

/** Writes the header row on an empty tab (bold, yellow) and adds any missing headers. */
function ensureHeaders_(sheet) {
  if (!isUsableTab_(sheet)) {
    throw new Error('Tab "' + sheet.getName() + '" already has other data. Choose an empty tab or create a new one.');
  }
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, COLUMNS.length).setValues([COLUMNS.map(c => c.header)]);
    formatSheet_(sheet);  // a new tab gets the full styling straight away
    return;
  }
  const map = headerMap_(sheet);
  let added = false;
  COLUMNS.forEach(c => {
    const col = map[c.key];
    if (!col) {
      // New column (e.g. after an update): add it at the end of the header row.
      sheet.getRange(1, sheet.getLastColumn() + 1).setValue(c.header);
      added = true;
    } else if (String(sheet.getRange(1, col).getDisplayValue()).trim() !== c.header) {
      // Found under an old name (alias): rename the header in place.
      sheet.getRange(1, col).setValue(c.header);
      added = true;
    }
  });
  // Columns were added or renamed → refresh every row's formulas so they use the new columns.
  if (added) {
    writeFormulas_(sheet);
    formatSheet_(sheet);
  }
}

/** Shows Profit, Profit % and ROI in red when they are negative (a loss). */
const LOSS_COLUMNS = ['profit', 'profit_pct', 'roi'];
function highlightLosses_(sheet) {
  const map = headerMap_(sheet);
  const cols = LOSS_COLUMNS.map(k => map[k]).filter(Boolean);
  if (!cols.length) return;
  const rows = Math.max(sheet.getMaxRows() - 1, 1);
  // Drop this tool's earlier "< 0" rules on these columns, then add one fresh rule.
  const rules = sheet.getConditionalFormatRules().filter(rule => {
    const cond = rule.getBooleanCondition();
    const ours = cond && cond.getCriteriaType() === SpreadsheetApp.BooleanCriteria.NUMBER_LESS_THAN &&
      String(cond.getCriteriaValues()[0]) === '0';
    return !(ours && rule.getRanges().some(r => cols.indexOf(r.getColumn()) !== -1));
  });
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenNumberLessThan(0)
    .setFontColor('#C62828')
    .setBackground('#FDECEA')
    .setRanges(cols.map(c => sheet.getRange(2, c, rows, 1)))
    .build());
  sheet.setConditionalFormatRules(rules);
}

/**
 * Applies SHEET_STYLE to one product tab: header row, column colours/notes/widths, number formats,
 * banding, filter and the red "loss" rule. Only this tool's columns are styled; values and formulas
 * are never changed, so it can be run as often as you like.
 */
function formatSheet_(sheet) {
  const map = headerMap_(sheet);
  const lastCol = sheet.getLastColumn();
  if (!map.item_id || lastCol === 0) return;
  const rows = Math.max(sheet.getMaxRows() - 1, 1);
  const S = SHEET_STYLE;

  // Header row
  sheet.setFrozenRows(1);
  sheet.setRowHeight(1, S.headerHeight);

  COLUMNS.forEach(c => {
    const col = map[c.key];
    if (!col) return;
    const group = S.groups[c.group];

    sheet.getRange(1, col)
      .setBackground(group.background).setFontColor(S.headerFont)
      .setFontWeight('bold').setFontSize(S.headerFontSize)
      .setWrap(true).setHorizontalAlignment('center').setVerticalAlignment('middle')
      .setNote(group.note + (COLUMN_NOTES[c.key] ? '\n\n' + COLUMN_NOTES[c.key] : ''));
    sheet.setColumnWidth(col, S.widthByKey[c.key] || S.widths[c.type] || 120);

    // Data cells of this column (rows 2…end)
    const data = sheet.getRange(2, col, rows, 1).setVerticalAlignment('middle');
    if (c.key === 'item_id') data.setNumberFormat('@');
    else if (PERCENT_COLUMNS.indexOf(c.key) !== -1) data.setNumberFormat(S.percentFormat);
    else if (c.type === 'money' || c.type === 'calc') data.setNumberFormat(S.moneyFormat);
    else if (c.type === 'number') data.setNumberFormat(S.countFormat);

    if (c.type === 'calc') data.setBackground(S.calcDataBackground);
    if (c.type === 'image') data.setHorizontalAlignment('center');
    if (c.type === 'url' || c.type === 'link' || c.type === 'textarea') {
      data.setWrapStrategy(SpreadsheetApp.WrapStrategy.CLIP);  // long links stay on one line
    }
    if (c.type === 'status') {
      data.setDataValidation(SpreadsheetApp.newDataValidation()
        .requireValueInList(STATUS_OPTIONS, true).setAllowInvalid(false).build());
    }
  });

  // Alternate row shading – replaced each time so it never stacks up.
  sheet.getBandings().forEach(b => b.remove());
  sheet.getRange(2, 1, rows, lastCol)
    .applyRowBanding(SpreadsheetApp.BandingTheme.LIGHT_GREY, false, false)
    .setFirstRowColor(S.banding.first)
    .setSecondRowColor(S.banding.second);

  // Filter buttons on the header. An existing filter is kept (with your filter choices)
  // unless columns were added, then it is recreated to cover them.
  const filter = sheet.getFilter();
  if (filter && filter.getRange().getNumColumns() !== lastCol) filter.remove();
  if (!sheet.getFilter()) sheet.getRange(1, 1, sheet.getMaxRows(), lastCol).createFilter();

  highlightLosses_(sheet);
}

/** { key: columnNumber } found by header text, so moved columns still work. */
function headerMap_(sheet) {
  const lastCol = sheet.getLastColumn();
  if (lastCol === 0) return {};
  const headers = sheet.getRange(1, 1, 1, lastCol).getDisplayValues()[0].map(h => String(h).trim().toLowerCase());
  const map = {};
  COLUMNS.forEach(c => {
    const names = [c.header].concat(c.aliases || []).map(h => h.toLowerCase());
    const i = headers.findIndex(h => names.indexOf(h) !== -1);
    if (i !== -1) map[c.key] = i + 1;
  });
  return map;
}

function columnLetter_(n) {
  let s = '';
  while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); }
  return s;
}

/** Row number of an Item ID in this tab, or 0. */
function findRowById_(sheet, itemId) {
  const map = headerMap_(sheet);
  const last = sheet.getLastRow();
  if (!map.item_id || last < 2) return 0;
  const ids = sheet.getRange(2, map.item_id, last - 1, 1).getDisplayValues();
  for (let i = 0; i < ids.length; i++) {
    if (String(ids[i][0]).trim() === String(itemId).trim()) return i + 2;
  }
  return 0;
}

/** Writes one product into `rowNumber`, keeping any extra columns you added yourself. */
function writeRow_(sheet, rowNumber, data) {
  ensureHeaders_(sheet);
  if (rowNumber > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(), 100);
  const map = headerMap_(sheet);
  const width = sheet.getLastColumn();
  const range = sheet.getRange(rowNumber, 1, 1, width);
  const values = rowNumber <= sheet.getLastRow() ? range.getValues()[0] : new Array(width).fill('');
  const cell = key => columnLetter_(map[key]) + rowNumber;

  COLUMNS.forEach(c => {
    const col = map[c.key];
    if (!col) return;
    let v;
    if (c.type === 'calc') {
      v = FORMULAS[c.key](cell);
    } else if (c.key === 'ebay_link') {
      v = data.item_id ? 'https://www.ebay.com/itm/' + data.item_id : '';
    } else if (c.type === 'image') {
      v = imageFormula_(data[c.key]);
    } else {
      v = data[c.key];
      if (v === undefined || v === null) v = c.default !== undefined ? c.default : '';
      if ((c.type === 'money' || c.type === 'number') && v !== '') {
        const n = Number(String(v).replace(/[,$\s]/g, ''));
        v = isNaN(n) ? '' : n;
      } else if (c.type === 'status' && STATUS_OPTIONS.indexOf(v) === -1) {
        v = STATUS_OPTIONS[0];
      } else {
        v = String(v);
      }
    }
    values[col - 1] = v;
  });

  if (map.item_id) sheet.getRange(rowNumber, map.item_id).setNumberFormat('@');
  range.setValues([values]);
  return rowNumber;
}

/** A picture link becomes =IMAGE("link") so the sheet shows the picture; anything else stays empty. */
function imageFormula_(url) {
  url = String(url || '').trim();
  return /^https?:\/\/\S+$/i.test(url) ? '=IMAGE("' + url.replace(/"/g, '%22') + '")' : '';
}

/** The link back out of an image cell: from =IMAGE("…"), or the text when a plain link was typed. */
function imageUrlFrom_(formula, value) {
  const m = String(formula || '').match(/^=IMAGE\(\s*"([^"]+)"/i);
  if (m) return m[1];
  const text = String(value || '').trim();
  return /^https?:\/\//i.test(text) ? text : '';
}

/** { tabName: [ {key: value, …}, … ] } for every tab that has an "ID" column. */
function readAllProducts_() {
  const result = {};
  productTabNames_().forEach(name => {
    const sheet = SpreadsheetApp.getActive().getSheetByName(name);
    const map = headerMap_(sheet);
    if (!map.item_id || !map.product_name || sheet.getLastRow() < 2) {
      if (map.item_id && map.product_name) result[name] = [];
      return;
    }
    const data = sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn()).getValues();
    const display = sheet.getRange(2, map.item_id, sheet.getLastRow() - 1, 1).getDisplayValues();
    const images = map.image_url ? sheet.getRange(2, map.image_url, sheet.getLastRow() - 1, 1).getFormulas() : [];
    result[name] = data.map((row, i) => {
      const obj = {};
      COLUMNS.forEach(c => {
        if (c.group === 'calc' || !map[c.key]) return;
        if (c.key === 'item_id') obj[c.key] = String(display[i][0]).trim();
        else if (c.type === 'image') obj[c.key] = imageUrlFrom_(images[i][0], row[map[c.key] - 1]);
        else obj[c.key] = row[map[c.key] - 1];
      });
      return obj;
    }).filter(o => o.item_id);
  });
  return result;
}


/* =====================================================================
 * Fee settings – kept on the "eBay Settings" tab, one per row in column B.
 * Each value is a named range used by FORMULAS. Row 5 holds the last-changed time (for syncing).
 * Percentages are stored as fractions (13.6% → 0.136) and shown with a % format.
 * ===================================================================== */
const SETTINGS_ROWS = [
  { key: 'ebay_fee_pct',        row: 2, name: 'EBAY_FEE_PCT',        label: 'eBay Fee %',                     pct: true },
  { key: 'ebay_fixed_fee',      row: 3, name: 'EBAY_FIXED_FEE',      label: 'Fixed Fee (order ≤ threshold)' },
  { key: 'ad_rate_pct',         row: 4, name: 'AD_RATE_PCT',         label: 'Ad Rate %',                      pct: true },
  { key: 'ebay_fixed_fee_high', row: 6, name: 'EBAY_FIXED_FEE_HIGH', label: 'Fixed Fee (order > threshold)' },
  { key: 'fixed_fee_threshold', row: 7, name: 'FIXED_FEE_THRESHOLD', label: 'Fixed Fee threshold ($)' },
  { key: 'sales_tax_pct',       row: 8, name: 'SALES_TAX_PCT',       label: 'Sales Tax buffer %',             pct: true },
];
const SETTINGS_TS_ROW = 5;

/** Creates the settings tab, or adds any setting an older version didn't have. Never overwrites values. */
function ensureSettingsTab_(fees) {
  const ss = SpreadsheetApp.getActive();
  let sheet = ss.getSheetByName(SETTINGS_TAB);
  if (!sheet) {
    sheet = ss.insertSheet(SETTINGS_TAB);
    sheet.getRange('A1:B1').setValues([['Setting', 'Value']]).setFontWeight('bold')
      .setBackground(HEADER_STYLE.background).setFontColor(HEADER_STYLE.font);
    sheet.getRange(SETTINGS_TS_ROW, 1, 1, 2).setValues([['Last changed (do not edit)', 0]]).setFontColor('#999999');
    sheet.setColumnWidth(1, 240);
  }
  SETTINGS_ROWS.forEach(s => {
    if (ss.getRangeByName(s.name)) return;  // already there – keep the user's value
    const given = fees && fees[s.key] !== undefined ? fees[s.key] : DEFAULT_SETTINGS[s.key];
    const cell = sheet.getRange(s.row, 2);
    sheet.getRange(s.row, 1).setValue(s.label);
    cell.setValue(s.pct ? Number(given) / 100 : Number(given)).setNumberFormat(s.pct ? '0.00%' : '0.00');
    ss.setNamedRange(s.name, cell);
  });
  return sheet;
}

function readSettings_() {
  const sheet = ensureSettingsTab_();
  const out = { updated_at: Number(sheet.getRange(SETTINGS_TS_ROW, 2).getValue()) || 0 };
  SETTINGS_ROWS.forEach(s => {
    const v = Number(sheet.getRange(s.row, 2).getValue());
    out[s.key] = round2_(s.pct ? v * 100 : v);
  });
  return out;
}

function writeSettings_(fees, updatedAt) {
  const sheet = ensureSettingsTab_(fees);
  SETTINGS_ROWS.forEach(s => {
    if (fees[s.key] === undefined || fees[s.key] === null || fees[s.key] === '') return;
    sheet.getRange(s.row, 2).setValue(s.pct ? Number(fees[s.key]) / 100 : Number(fees[s.key]));
  });
  sheet.getRange(SETTINGS_TS_ROW, 2).setValue(Number(updatedAt) || Date.now());
}

/** Editing a setting by hand also counts as a change (so the website picks it up on sync). */
function onEdit(e) {
  const sheet = e.range.getSheet();
  const row = e.range.getRow();
  if (sheet.getName() === SETTINGS_TAB && e.range.getColumn() === 2 && SETTINGS_ROWS.some(s => s.row === row)) {
    sheet.getRange(SETTINGS_TS_ROW, 2).setValue(Date.now());
  }
}

function round2_(n) { return Math.round(n * 100) / 100; }
