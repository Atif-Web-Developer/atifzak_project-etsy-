/**
 * Stock Hunting – Google Sheets side
 * ==================================
 * Works as a web app so the Atif-Zak Analytics website can save hunts here and sync both ways.
 *
 * Two tabs, in ma'am's layout:
 *   "Product selection"     – one row per product idea (Sr. No = the link between the tabs)
 *   "Competitors selection" – one row per competitor, with the same Sr No
 * Only ma'am's columns. They are found by their header text, so a copy of her sheet works as it is;
 * a missing column is added at the end, and your own extra columns are left alone.
 */

// Filled in automatically when you copy this file from the website's Settings page.
const SYNC_KEY = 'PASTE_YOUR_SYNC_KEY_HERE';

const PRODUCT_TAB = 'Product selection';
const COMPETITOR_TAB = 'Competitors selection';

/* =====================================================================
 * COLUMNS – exactly ma'am's sheet. Keys must match stock_hunting/sheets.py.
 * ===================================================================== */
const PRODUCT_COLUMNS = [
  { key: 'sr_no',               header: 'Sr. No',                                     type: 'number', aliases: ['Sr No'] },
  { key: 'main_keyword',        header: 'Main Keyword',                               type: 'text', aliases: ['Main Keywords'] },
  { key: 'sales_trend',         header: 'Sales Trend',                                type: 'text' },
  { key: 'two_sellers_100',     header: '2 Sellers with 100 above sales { Yes / no}', type: 'text' },
  { key: 'avg_price',           header: 'Avg sales price { USD/ POUND }',             type: 'money' },
  { key: 'total_sellers',       header: 'Total Sellers',                              type: 'number' },
  { key: 'seller_listing_link', header: 'seller listing link',                        type: 'url' },
];

const COMPETITOR_COLUMNS = [
  { key: 'sr_no',        header: 'Sr No',                                type: 'number', aliases: ['Sr. No'] },
  { key: 'main_keyword', header: 'Main Keywords',                        type: 'text', aliases: ['Main Keyword'] },
  { key: 'link',         header: 'Listing link of competitors',          type: 'url' },
  { key: 'feedback',     header: 'Seller Feedback',                      type: 'number' },
  { key: 'price',        header: 'Slaes price of competitors',           type: 'money', aliases: ['Sales price of competitors'] },
  { key: 'sales_30d',    header: '30 Days sales of competitors',         type: 'number' },
  { key: 'variation',    header: 'pack/colour variation of competitors', type: 'text' },
];

const STYLE = {
  widths: { text: 140, number: 110, money: 130, url: 220 },
  widthByKey: { main_keyword: 160, two_sellers_100: 210, avg_price: 160, variation: 120 },
};


/* =====================================================================
 * Menu
 * ===================================================================== */
function onOpen() {
  SpreadsheetApp.getUi().createMenu('Stock Hunting')
    .addItem('Format headers', 'formatTabs')
    .addToUi();
}

function formatTabs() {
  const ss = SpreadsheetApp.getActive();
  formatSheet_(getTab_(PRODUCT_TAB, PRODUCT_COLUMNS), PRODUCT_COLUMNS);
  formatSheet_(getTab_(COMPETITOR_TAB, COMPETITOR_COLUMNS), COMPETITOR_COLUMNS);
  ss.toast('Both tabs formatted.', 'Stock Hunting', 5);
}


/* =====================================================================
 * Web app (called by the website)
 * ===================================================================== */
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
        getTab_(PRODUCT_TAB, PRODUCT_COLUMNS);
        getTab_(COMPETITOR_TAB, COMPETITOR_COLUMNS);
        return json_({ ok: true, spreadsheet: SpreadsheetApp.getActive().getName() });
      case 'upsert':
        writeProduct_(req.product, req.currency);
        writeCompetitors_(req.product.sr_no, req.competitors || [], req.currency);
        return json_({ ok: true });
      case 'delete':
        deleteRows_(getTab_(PRODUCT_TAB, PRODUCT_COLUMNS), PRODUCT_COLUMNS, req.sr_no);
        deleteRows_(getTab_(COMPETITOR_TAB, COMPETITOR_COLUMNS), COMPETITOR_COLUMNS, req.sr_no);
        return json_({ ok: true });
      case 'pull':
        return json_({ ok: true,
          products: readRows_(getTab_(PRODUCT_TAB, PRODUCT_COLUMNS), PRODUCT_COLUMNS),
          competitors: readRows_(getTab_(COMPETITOR_TAB, COMPETITOR_COLUMNS), COMPETITOR_COLUMNS) });
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
 * Writing
 * ===================================================================== */

/** One "Product selection" row: updates the row with this Sr. No, or adds one. Your own extra columns are kept. */
function writeProduct_(data, currency) {
  const sheet = getTab_(PRODUCT_TAB, PRODUCT_COLUMNS);
  const map = headerMap_(sheet, PRODUCT_COLUMNS);
  const rowNumber = findRows_(sheet, map, data.sr_no)[0] || sheet.getLastRow() + 1;
  const width = sheet.getLastColumn();
  const range = sheet.getRange(rowNumber, 1, 1, width);
  const values = rowNumber <= sheet.getLastRow() ? range.getValues()[0] : new Array(width).fill('');
  PRODUCT_COLUMNS.forEach(c => { if (map[c.key]) values[map[c.key] - 1] = cellValue_(c, data[c.key]); });
  range.setValues([values]);
  // The average price shows the market's currency (US $, UK £, AU A$).
  if (map.avg_price) sheet.getRange(rowNumber, map.avg_price).setNumberFormat(moneyFormat_(currency));
}

/** Replaces this Sr No's rows in "Competitors selection" (kept in the same place in the tab). */
function writeCompetitors_(srNo, competitors, currency) {
  const sheet = getTab_(COMPETITOR_TAB, COMPETITOR_COLUMNS);
  const map = headerMap_(sheet, COMPETITOR_COLUMNS);
  const existing = findRows_(sheet, map, srNo);
  const at = existing.length ? existing[0] : sheet.getLastRow() + 1;
  existing.slice().reverse().forEach(r => sheet.deleteRow(r));
  if (!competitors.length) return;
  const width = sheet.getLastColumn();
  if (at <= sheet.getLastRow()) sheet.insertRowsBefore(at, competitors.length);
  const rows = competitors.map(comp => {
    const values = new Array(width).fill('');
    COMPETITOR_COLUMNS.forEach(c => { if (map[c.key]) values[map[c.key] - 1] = cellValue_(c, comp[c.key]); });
    return values;
  });
  sheet.getRange(at, 1, rows.length, width).setValues(rows);
  if (map.price) sheet.getRange(at, map.price, rows.length, 1).setNumberFormat(moneyFormat_(currency));
}

function deleteRows_(sheet, columns, srNo) {
  const map = headerMap_(sheet, columns);
  findRows_(sheet, map, srNo).reverse().forEach(r => sheet.deleteRow(r));
}

function cellValue_(c, v) {
  if (v === undefined || v === null) return '';
  if ((c.type === 'number' || c.type === 'money') && v !== '') {
    const n = Number(String(v).replace(/[,$£\s]/g, ''));
    return isNaN(n) ? '' : n;
  }
  return String(v);
}

function moneyFormat_(currency) {
  const symbol = currency === '£' ? '£' : currency === 'A$' ? '"A$"' : '$';
  return symbol + '#,##0.00';
}


/* =====================================================================
 * Reading
 * ===================================================================== */

/** Every row with a Sr No, as {key: value}. Prices are read as shown ("£19.99"), so the currency comes along. */
function readRows_(sheet, columns) {
  const map = headerMap_(sheet, columns);
  const last = sheet.getLastRow();
  if (!map.sr_no || last < 2) return [];
  const range = sheet.getRange(2, 1, last - 1, sheet.getLastColumn());
  const data = range.getValues();
  const shown = range.getDisplayValues();
  return data.map((row, i) => {
    const obj = {};
    columns.forEach(c => {
      if (map[c.key]) obj[c.key] = c.type === 'money' ? shown[i][map[c.key] - 1] : row[map[c.key] - 1];
    });
    return obj;
  }).filter(o => String(o.sr_no).trim() !== '');
}

/** Row numbers whose Sr No equals srNo. */
function findRows_(sheet, map, srNo) {
  const last = sheet.getLastRow();
  if (!map.sr_no || last < 2) return [];
  const ids = sheet.getRange(2, map.sr_no, last - 1, 1).getValues();
  const rows = [];
  ids.forEach((v, i) => { if (String(v[0]).trim() !== '' && Number(v[0]) === Number(srNo)) rows.push(i + 2); });
  return rows;
}


/* =====================================================================
 * Tabs, headers and styling
 * ===================================================================== */

/** The tab with all its headers (created, or missing columns added at the end). Data is never removed. */
function getTab_(name, columns) {
  const ss = SpreadsheetApp.getActive();
  let sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  if (sheet.getLastRow() === 0 && sheet.getLastColumn() === 0) {
    sheet.getRange(1, 1, 1, columns.length).setValues([columns.map(c => c.header)]);
    formatSheet_(sheet, columns);
    return sheet;
  }
  const map = headerMap_(sheet, columns);
  let added = false;
  columns.forEach(c => {
    if (!map[c.key]) {
      sheet.getRange(1, sheet.getLastColumn() + 1).setValue(c.header);
      added = true;
    }
  });
  if (added) formatSheet_(sheet, columns);
  return sheet;
}

/** Header text → column, ignoring case, spaces and symbols ("Sr. No" = "Sr No"). */
function headerMap_(sheet, columns) {
  const lastCol = sheet.getLastColumn();
  if (lastCol === 0) return {};
  const norm = h => String(h).toLowerCase().replace(/[^a-z0-9]/g, '');
  const headers = sheet.getRange(1, 1, 1, lastCol).getDisplayValues()[0].map(norm);
  const map = {};
  columns.forEach(c => {
    const names = [c.header].concat(c.aliases || []).map(norm);
    const i = headers.findIndex((h, idx) => names.indexOf(h) !== -1 && Object.values(map).indexOf(idx + 1) === -1);
    if (i !== -1) map[c.key] = i + 1;
  });
  return map;
}

/** Bold, wrapped headers (like ma'am's sheet), frozen header row, widths and number formats. Safe to run again. */
function formatSheet_(sheet, columns) {
  const map = headerMap_(sheet, columns);
  if (!map.sr_no) return;
  const rows = Math.max(sheet.getMaxRows() - 1, 1);
  sheet.setFrozenRows(1);
  columns.forEach(c => {
    const col = map[c.key];
    if (!col) return;
    sheet.getRange(1, col).setFontWeight('bold').setWrap(true).setVerticalAlignment('bottom');
    sheet.setColumnWidth(col, STYLE.widthByKey[c.key] || STYLE.widths[c.type] || 120);
    const data = sheet.getRange(2, col, rows, 1);
    if (c.type === 'number' && c.key !== 'sr_no') data.setNumberFormat('#,##0');
    if (c.type === 'url') data.setWrapStrategy(SpreadsheetApp.WrapStrategy.CLIP);
  });
}
