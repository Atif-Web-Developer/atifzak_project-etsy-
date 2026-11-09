/*
 * eBay Dropshipping – paste parser + profit calculator.
 *
 * This file is the single source for both:
 *   - the Django form (loaded as a static file), and
 *   - the Google Sheets sidebar (Form.html gets this code injected when you download it
 *     from the module's Settings page).
 *
 * The profit formulas here must match ebay_dropshipping/calculations.py and FORMULAS in Code.gs.
 */
var EbayTool = (function () {
    'use strict';

    // Words that can appear above the title on an eBay page and are never the product name.
    var NOT_A_TITLE = /^(share|save|watch|watching|add to watchlist|sponsored|message|condition:?|quantity:?|see all|home|back to .*|listed in category.*|\|)$/i;
    var MD_LINK = /\[([^\]]*)\]\(([^)]*)\)/g;
    var ONLY_MD_LINK = /^\[[^\]]*\]\([^)]*\)$/;

    function stripLinks(s) { return s.replace(MD_LINK, '$1'); }

    function cleanNumber(s) {
        if (s === undefined || s === null) return '';
        var n = String(s).replace(/[,\s]/g, '');
        return /^\d+(\.\d+)?$/.test(n) ? n : '';
    }

    function emptyResult() {
        return {
            item_id: '', product_name: '', seller_name: '', seller_feedback: '', seller_price: '',
            buyer_shipping: '', sold_orders: '', sales_line: '', variation: ''
        };
    }

    /**
     * Reads the text copied from an eBay listing page (with ZIK Analytics data) and returns
     * the fields it can find. Anything not found stays an empty string – it never guesses.
     */
    function parse(raw) {
        var out = emptyResult();
        if (!raw) return out;
        var text = String(raw).replace(/\r/g, '');
        var lines = text.split('\n').map(function (l) { return l.trim(); }).filter(function (l) { return l; });
        var plain = lines.map(function (l) { return stripLinks(l).trim(); });
        var i, m;

        // ---- Item ID: from "item=123…", an /itm/ link or an "Item number" label.
        m = text.match(/[?&]item=(\d{9,15})/i) ||
            text.match(/\/itm\/(?:[^\s\/)\]]+\/)?(\d{9,15})/i) ||
            text.match(/item\s*(?:number|id|no\.?)\s*:?\s*(\d{9,15})/i);
        if (m) out.item_id = m[1];

        // ---- Product name: the first real line (skip labels like "Share" and pure link lines).
        for (i = 0; i < lines.length; i++) {
            if (ONLY_MD_LINK.test(lines[i]) || /^https?:\/\//i.test(lines[i])) continue;
            // Plain-text copies glue ZIK's button to the title: "…TopicalView Sold History".
            var title = plain[i].replace(/\s*View Sold History\s*$/i, '').trim();
            if (NOT_A_TITLE.test(title) || !/[a-z]/i.test(title) || title.length < 3) continue;
            out.product_name = title;
            break;
        }

        // ---- Seller name + feedback count: "(25270)" on its own line, seller on the line before.
        for (i = 1; i < plain.length; i++) {
            m = plain[i].match(/^\((\d[\d,]*)\)$/);
            if (m && plain[i - 1]) {
                out.seller_feedback = cleanNumber(m[1]);
                out.seller_name = plain[i - 1];
                break;
            }
        }
        if (!out.seller_name) {
            // Same-line form: "[SellerName](link) (25270)"
            for (i = 0; i < lines.length; i++) {
                if (lines[i].charAt(0) !== '[') continue;
                m = plain[i].match(/^(.+?)\s*\((\d[\d,]*)\)$/);
                if (m) { out.seller_name = m[1].trim(); out.seller_feedback = cleanNumber(m[2]); break; }
            }
        }

        // ---- Competitor (seller) price: "US $23.99/ea", otherwise a line that is just a price.
        m = text.match(/US\s*\$\s*([\d,]+(?:\.\d{1,2})?)\s*\/\s*ea/i);
        if (m) {
            out.seller_price = cleanNumber(m[1]);
        } else {
            for (i = 0; i < plain.length; i++) {
                m = plain[i].match(/^(?:price\s*:?\s*)?(?:US\s*)?\$\s*([\d,]+\.\d{2})$/i);
                if (m) { out.seller_price = cleanNumber(m[1]); break; }
            }
        }

        // ---- Buyer shipping: "DeliveryUS $35", "Shipping: Free" … (Free = 0).
        for (i = 0; i < plain.length && out.buyer_shipping === ''; i++) {
            m = plain[i].match(/^(?:delivery|shipping|postage)\s*:?\s*(.*)$/i);
            if (!m) continue;
            var rest = m[1] || plain[i + 1] || '';
            if (/^free\b/i.test(rest) || /\bfree (shipping|delivery|postage)\b/i.test(rest)) {
                out.buyer_shipping = '0';
            } else {
                var price = rest.match(/\$\s*([\d,]+(?:\.\d{1,2})?)/);
                if (price) out.buyer_shipping = cleanNumber(price[1]);
            }
        }

        // ---- Sold / orders: "Sold7 sold", falling back to "7 sold" anywhere.
        for (i = 0; i < plain.length; i++) {
            m = plain[i].match(/^sold\s*:?\s*([\d,]+)\s*sold$/i);
            if (m) { out.sold_orders = cleanNumber(m[1]); break; }
        }
        if (out.sold_orders === '') {
            m = text.match(/([\d,]+)\s*sold\b/i);
            if (m) out.sold_orders = cleanNumber(m[1]);
        }

        // ---- Sales line: "24h03d01w02w01m13m2" → split on the fixed labels.
        var salesRe = /24h(\d+)3d(\d+)1w(\d+)2w(\d+)1m(\d+)3m(\d+)/i;
        var sales = null;
        for (i = 0; i < plain.length && !sales; i++) sales = plain[i].replace(/[\s,]+/g, '').match(salesRe);
        if (!sales) {
            // Labels and numbers on separate lines right after "Sold In".
            for (i = 0; i < plain.length; i++) {
                if (/^sold in$/i.test(plain[i])) { sales = plain.slice(i + 1, i + 13).join('').replace(/[\s,]+/g, '').match(salesRe); break; }
            }
        }
        if (sales) {
            out.sales_line = ['24h', '3d', '1w', '2w', '1m', '3m'].map(function (label, k) {
                return label + ': ' + parseInt(sales[k + 1], 10);
            }).join(', ');
        }

        // ---- Variation: "VariationsNo" / "Variations: Yes".
        for (i = 0; i < plain.length; i++) {
            m = plain[i].match(/^variations?\s*:?\s*(yes|no)$/i);
            if (!m && /^variations?\s*:?$/i.test(plain[i]) && plain[i + 1]) m = plain[i + 1].match(/^(yes|no)$/i);
            if (m) { out.variation = m[1].charAt(0).toUpperCase() + m[1].slice(1).toLowerCase(); break; }
        }

        // Without any eBay data the "first line" is just a guess, so don't fill the name.
        var found = Object.keys(out).some(function (k) { return k !== 'product_name' && out[k] !== ''; });
        if (!found) out.product_name = '';

        return out;
    }

    /* =================================================================
     * Supplier page parser (AliExpress, Amazon, CJ Dropshipping, Temu, local/other)
     * Fills supplier_link, supplier_cost and supplier_shipping. Like the eBay parser it
     * never guesses: anything not clearly found stays empty, and `notes` explain why.
     * ================================================================= */
    var SUPPLIERS = [
        { key: 'auto', label: 'Auto-detect' },
        { key: 'aliexpress', label: 'AliExpress', host: /aliexpress\./i, words: /aliexpress/i },
        { key: 'amazon', label: 'Amazon', host: /(amazon\.|amzn\.)/i, words: /\bamazon\b|\bASIN\s*:/i },
        { key: 'cj', label: 'CJ Dropshipping', host: /cjdropshipping\./i, words: /cj ?dropshipping/i },
        { key: 'temu', label: 'Temu', host: /temu\./i, words: /\btemu\b/i },
        { key: 'other', label: 'Local / Other' }
    ];
    var URL_RE = /https?:\/\/[^\s)\]<>"']+/g;
    var AMOUNT_RE = /(?:US\s*\$|USD\s*\$?|\$)\s*([\d,]+(?:\.\d{1,2})?)/i;
    var PRICE_LABEL = /^(?:sale price|price|now|our price|unit price|current price|deal price|special price|your price|sell price|selling price|wholesale price|cost)\b/i;
    var NOT_PRICE = /shipping|delivery|postage|freight|\boff\b|save|coupon|\bwas\b|list price|typical price|original|reviews?|ratings?|\bsold\b|orders?|\bover\b|min\.? order|per month|\/mo\b|subtotal|discount|tax|fee|credit|points|coins|cashback/i;
    var SHIP_WORD = /shipping|delivery|postage|freight/i;
    // Membership adverts ("Enjoy fast, free delivery, exclusive deals … movies") are not the item's shipping.
    var SHIP_ADVERT = /movies|exclusive deals|award-winning|free trial|sign up|join prime|deliver to\b/i;
    var FOREIGN_MONEY = /(?:\bRs\.?|\bPKR|₨|€|£|\bAED|\bINR|₹|\bEUR|\bGBP)\s*[\d,]+/i;

    function supplierLink(urls, key, text) {
        var cfg = SUPPLIERS.filter(function (s) { return s.key === key; })[0] || {};
        var candidates = urls.filter(function (u) { return cfg.host ? cfg.host.test(u) : !/ebay\./i.test(u); });
        var url = candidates[0];
        var m;
        // Amazon tools (SellerSprite, Helium 10 …) copy "ASIN: B0…" instead of the URL.
        if (!url && key === 'amazon' && (m = String(text).match(/\bASIN\s*:?\s*([A-Z0-9]{10})\b/i))) {
            return 'https://www.amazon.com/dp/' + m[1].toUpperCase();
        }
        if (!url) return '';
        if (key === 'aliexpress' && (m = url.match(/aliexpress\.[a-z.]+\/item\/(\d+)\.html/i))) {
            return 'https://www.aliexpress.com/item/' + m[1] + '.html';
        }
        if (key === 'amazon' && (m = url.match(/^(https?:\/\/(?:www\.)?amazon\.[a-z.]+)\/(?:.*?\/)?(?:dp|gp\/product)\/([A-Z0-9]{10})/i))) {
            return m[1] + '/dp/' + m[2].toUpperCase();
        }
        return url.split(/[?#]/)[0];  // drop tracking parameters
    }

    function detectSupplier(text, urls) {
        var hit = SUPPLIERS.filter(function (s) {
            return s.host && urls.some(function (u) { return s.host.test(u); });
        })[0] || SUPPLIERS.filter(function (s) { return s.words && s.words.test(text); })[0];
        return hit ? hit.key : 'other';
    }

    /** True for text copied from an eBay listing (not a supplier page). */
    function looksLikeEbay(raw) {
        var text = String(raw || '');
        var supplierUrl = (text.match(URL_RE) || []).some(function (u) {
            return SUPPLIERS.some(function (s) { return s.host && s.host.test(u); });
        });
        return !supplierUrl && /ebay\.[a-z.]+\/(itm|bin|str|sch|usr)|[?&]item=\d{9,}|View Sold History|US \$[\d.,]+\/ea/i.test(text);
    }

    function parseSupplier(raw, key) {
        var out = { supplier_link: '', supplier_cost: '', supplier_shipping: '', platform: '', notes: [] };
        if (!raw) return out;
        if (looksLikeEbay(raw)) {
            out.platform = 'ebay';
            out.notes.push('This looks like an eBay listing, not a supplier page – paste it in the "Competitor eBay page" tab instead.');
            return out;
        }
        var text = String(raw).replace(/\r/g, '')
            // Amazon sometimes copies a price as "$" / "12" / "99" on separate lines.
            .replace(/\$\s*\n\s*(\d+)\s*\n\s*\.?\s*\n?\s*(\d{2})\b/g, '$$$1.$2');
        var urls = text.match(URL_RE) || [];
        key = (!key || key === 'auto') ? detectSupplier(text, urls) : key;
        out.platform = key;

        var lines = text.split('\n').map(function (l) { return stripLinks(l).trim(); }).filter(function (l) { return l; });
        var i, m;

        out.supplier_link = supplierLink(urls, key, text);
        if (!out.supplier_link) out.notes.push('No supplier link found – paste the page URL at the top of the box (or type it).');

        // ---- Cost: a labelled price first, then the first line that is just a price, then any price.
        for (i = 0; i < lines.length && !out.supplier_cost; i++) {
            if (!PRICE_LABEL.test(lines[i]) || /list price|typical price|original/i.test(lines[i])) continue;
            m = lines[i].match(AMOUNT_RE) || (!AMOUNT_RE.test(lines[i]) && lines[i + 1] ? lines[i + 1].match(AMOUNT_RE) : null);
            if (m) out.supplier_cost = cleanNumber(m[1]);
        }
        for (i = 0; i < lines.length && !out.supplier_cost; i++) {
            if (/^-?\d+%?\s*(?:off)?\s*(?:US\s*\$|USD|\$)\s*[\d,]+(?:\.\d{1,2})?(?:\s*-\s*(?:US\s*\$|\$)?\s*[\d,.]+)?$/i.test(lines[i]) ||
                /^(?:US\s*\$|USD\s*\$?|\$)\s*[\d,]+(?:\.\d{1,2})?(?:\s*-\s*(?:US\s*\$|\$)?\s*[\d,.]+)?$/i.test(lines[i])) {
                if (i > 0 && /list price|typical price|was:?$|original/i.test(lines[i - 1])) continue;
                out.supplier_cost = cleanNumber(lines[i].match(AMOUNT_RE)[1]);
            }
        }
        for (i = 0; i < lines.length && !out.supplier_cost; i++) {
            if (NOT_PRICE.test(lines[i])) continue;
            m = lines[i].match(AMOUNT_RE);
            if (m) out.supplier_cost = cleanNumber(m[1]);
        }

        // ---- Shipping: "Free shipping" = 0; "Shipping: US $1.99" / "+ $1.99 shipping" = the amount.
        for (i = 0; i < lines.length && out.supplier_shipping === ''; i++) {
            if (!SHIP_WORD.test(lines[i]) || SHIP_ADVERT.test(lines[i])) continue;
            var line = lines[i];
            if (/\bfree\b/i.test(line)) {
                // "Free over $35" or "Free with Prime" is a condition, not a price – don't assume 0.
                if (/\b(over|above|orders? of|spend|min(imum)?|prime|members?|membership)\b/i.test(line)) {
                    if (!out.notes.some(function (n) { return /free only/i.test(n); })) {
                        out.notes.push('Shipping is free only with a condition (e.g. over $35 or with Prime) – type 0 if it applies to you, otherwise the real shipping cost.');
                    }
                    continue;
                }
                out.supplier_shipping = '0';
                break;
            }
            m = line.match(AMOUNT_RE);
            if (!m && /^(shipping|delivery|postage|shipping cost|shipping fee)\s*:?$/i.test(line) && lines[i + 1]) {
                if (/^free\b/i.test(lines[i + 1])) { out.supplier_shipping = '0'; break; }
                m = lines[i + 1].match(AMOUNT_RE);
            }
            if (m) out.supplier_shipping = cleanNumber(m[1]);
        }

        // ---- Prices in another currency are not converted (the formulas work in US dollars).
        if (!AMOUNT_RE.test(text) && FOREIGN_MONEY.test(text)) {
            out.supplier_cost = '';
            out.supplier_shipping = '';
            out.notes.push('Prices are not in US dollars (' + text.match(FOREIGN_MONEY)[0] + '). Convert to USD and type them.');
        } else {
            if (!out.supplier_cost) out.notes.push('No price found – please type the supplier cost.');
            if (out.supplier_shipping === '' && !out.notes.some(function (n) { return /shipping/i.test(n); })) {
                out.notes.push('No shipping cost found – please type it (0 if free).');
            }
        }
        return out;
    }

    function supplierLabel(key) {
        if (key === 'ebay') return 'eBay';
        var s = SUPPLIERS.filter(function (x) { return x.key === key; })[0];
        return s ? s.label : key;
    }

    function toNum(v) {
        if (v === undefined || v === null || String(v).trim() === '') return null;
        var n = parseFloat(String(v).replace(/[,$\s]/g, ''));
        return isNaN(n) ? null : n;
    }

    var CALC_KEYS = ['total_sale', 'ebay_fee', 'ad_fee', 'total_cost', 'profit', 'profit_pct', 'break_even', 'roi'];

    /**
     * Profit formulas (same as calculations.py and FORMULAS in Code.gs).
     *   Costs      = supplier cost + supplier shipping + other cost
     *   Total Sale = listed price + my shipping charge
     *   eBay Fee   = Total Sale × (1 + tax%) × fee% + (Total Sale ≤ threshold ? low fixed fee : high fixed fee)
     *   Ad Fee     = Total Sale × ad%
     *   Total Cost = Costs + eBay Fee + Ad Fee     Profit = Total Sale − Total Cost
     *   Profit %   = Profit ÷ Total Sale × 100     ROI % = Profit ÷ Costs × 100
     *   Break-even = (Costs + high fixed fee) ÷ (1 − fee% × (1 + tax%) − ad%) − my shipping
     * Every key is null when it can't be calculated; hasPrice tells whether a listed price was entered.
     */
    function calculate(values, settings) {
        var out = { hasPrice: false };
        CALC_KEYS.forEach(function (k) { out[k] = null; });
        var n = function (v) { return toNum(v) || 0; };
        var feePct = n(settings.ebay_fee_pct) / 100, adPct = n(settings.ad_rate_pct) / 100;
        var tax = 1 + n(settings.sales_tax_pct) / 100;
        var costs = n(values.supplier_cost) + n(values.supplier_shipping) + n(values.other_cost);
        var shipping = n(values.my_shipping);
        var price = toNum(values.listed_price);

        if (price !== null && price !== 0) {
            var totalSale = price + shipping;
            var fixed = totalSale <= n(settings.fixed_fee_threshold) ? n(settings.ebay_fixed_fee) : n(settings.ebay_fixed_fee_high);
            out.hasPrice = true;
            out.total_sale = totalSale;
            out.ebay_fee = totalSale * tax * feePct + fixed;
            out.ad_fee = totalSale * adPct;
            out.total_cost = costs + out.ebay_fee + out.ad_fee;
            out.profit = totalSale - out.total_cost;
            out.profit_pct = out.profit / totalSale * 100;
            out.roi = costs ? out.profit / costs * 100 : null;
        }
        if (toNum(values.supplier_cost) !== null) {
            var divisor = 1 - feePct * tax - adPct;
            if (divisor > 0) out.break_even = (costs + n(settings.ebay_fixed_fee_high)) / divisor - shipping;
        }
        return out;
    }

    /** Rounds a price up to the next ".99" (7.32 → 7.99, 8.00 → 8.99). */
    function roundUp99(x) {
        if (!(x > 0)) return null;
        var p = Math.ceil(x) - 0.01;
        if (p < x - 1e-9) p += 1;
        return Math.round(p * 100) / 100;
    }

    /**
     * Price suggestions for "My Listed Price" (the user may take one or type their own):
     *   target   – lowest ".99" price that reaches `marginPct` profit (profit ÷ Total Sale)
     *   undercut – 1 cent below the competitor's eBay price (eBay Seller Price)
     * Each comes with the profit it would make. null when there's no supplier cost yet.
     */
    function suggestPrices(values, settings, marginPct) {
        if (toNum(values.supplier_cost) === null) return null;
        var n = function (v) { return toNum(v) || 0; };
        var feePct = n(settings.ebay_fee_pct) / 100, adPct = n(settings.ad_rate_pct) / 100;
        var tax = 1 + n(settings.sales_tax_pct) / 100, margin = n(marginPct) / 100;
        var costs = n(values.supplier_cost) + n(values.supplier_shipping) + n(values.other_cost);
        var shipping = n(values.my_shipping);

        function withProfit(price) {
            var copy = {};
            Object.keys(values).forEach(function (k) { copy[k] = values[k]; });
            copy.listed_price = price;
            var r = calculate(copy, settings);
            return { price: price, profit: r.profit, profit_pct: r.profit_pct };
        }
        // Total Sale needed for the margin: (costs + fixed fee) ÷ (1 − fee% × tax − ad% − margin)
        function totalSaleFor(fixed) {
            var d = 1 - feePct * tax - adPct - margin;
            return d > 0 ? (costs + fixed) / d : null;
        }
        var out = { target: null, undercut: null, margin: n(marginPct) };
        var ts = totalSaleFor(n(settings.ebay_fixed_fee));
        if (ts !== null && ts > n(settings.fixed_fee_threshold)) ts = totalSaleFor(n(settings.ebay_fixed_fee_high));
        var target = ts !== null ? roundUp99(ts - shipping) : null;
        if (target) {
            out.target = withProfit(target);
            // Rounding up can cross the fixed-fee threshold ($0.30 → $0.40); then aim again with the higher fee.
            if (out.target.profit_pct < out.margin - 1e-6) {
                var ts2 = totalSaleFor(n(settings.ebay_fixed_fee_high));
                if (ts2 !== null) out.target = withProfit(roundUp99(ts2 - shipping));
            }
        }

        var competitor = toNum(values.seller_price);
        if (competitor && competitor > 0.01) out.undercut = withProfit(Math.round((competitor - 0.01) * 100) / 100);
        return out;
    }

    function money(n) { return (n === null || n === undefined) ? '' : (Math.round((n + Number.EPSILON) * 100) / 100).toFixed(2); }

    /**
     * Competitor eBay page → fields for "Your research". Returns the clean link plus the
     * competitor's feedback and sold count (empty strings when not found).
     */
    function parseCompetitor(raw) {
        var d = parse(raw);
        return {
            link: d.item_id ? 'https://www.ebay.com/itm/' + d.item_id : '',
            competitor_feedbacks: d.seller_feedback,
            competitor_sold: d.sold_orders,
            seller: d.seller_name,
            price: d.seller_price,
            shipping: d.buyer_shipping
        };
    }

    /**
     * Smart competitor paste. Understands:
     *   - a full eBay listing page (ZIK copy)  → one link + that seller's feedback and sold count
     *   - one or many eBay links / item URLs   → all links, numbers left as they are
     *   - a page copied as plain text (no link in it) → the numbers, kind 'page_no_link'
     * kind: 'page' | 'page_no_link' | 'links' | 'none' | 'supplier' (a supplier page pasted in the wrong box)
     */
    function parseCompetitors(raw) {
        var text = String(raw || '');
        var isSupplier = !looksLikeEbay(text) && SUPPLIERS.some(function (s) {
            return (s.host && (text.match(URL_RE) || []).some(function (u) { return s.host.test(u); })) || (s.words && s.words.test(text));
        });
        if (isSupplier) return { kind: 'supplier', links: [], competitor_feedbacks: '', competitor_sold: '', seller: '' };
        var page = parse(text);
        // A competitor page is recognised by the seller's feedback count or the "sold" number (a price alone could be anything).
        var hasPageData = page.seller_feedback !== '' || page.sold_orders !== '';
        if (hasPageData) {
            var one = parseCompetitor(text);
            return { kind: one.link ? 'page' : 'page_no_link', links: one.link ? [one.link] : [],
                     competitor_feedbacks: one.competitor_feedbacks, competitor_sold: one.competitor_sold,
                     seller: one.seller, price: one.price, shipping: one.shipping };
        }
        var ids = [], m, re = /(?:ebay\.[a-z.]+\/itm\/(?:[^\s\/?#)\]]+\/)?|[?&]item=)(\d{9,15})/gi;
        while ((m = re.exec(text)) !== null) if (ids.indexOf(m[1]) === -1) ids.push(m[1]);
        if (ids.length) {
            return { kind: 'links', links: ids.map(function (id) { return 'https://www.ebay.com/itm/' + id; }),
                     competitor_feedbacks: '', competitor_sold: '', seller: '' };
        }
        return { kind: 'none', links: [], competitor_feedbacks: '', competitor_sold: '', seller: '' };
    }

    /** Adds a link to a "one per line" list unless it's already there. */
    function addLine(list, link) {
        var lines = String(list || '').split('\n').map(function (l) { return l.trim(); }).filter(Boolean);
        var exists = lines.indexOf(link) !== -1;
        if (link && !exists) lines.push(link);
        return { value: lines.join('\n'), added: !!link && !exists, count: lines.length };
    }

    /**
     * The competitor numbers keep only the BIGGEST competitor: more sold wins; when sold is equal
     * (or missing on both) more feedback wins. next/current: { sold, feedback }.
     */
    function isBiggerCompetitor(next, current) {
        var n = function (v) { var x = toNum(v); return x === null ? -1 : x; };
        if (n(next.sold) !== n(current.sold)) return n(next.sold) > n(current.sold);
        return n(next.feedback) > n(current.feedback);
    }

    /* =================================================================
     * Competitor / supplier tables (same rules as lists.py):
     *   ★ main competitor = the pinned row, otherwise the biggest (isBiggerCompetitor)
     *   cheapest supplier = lowest cost + shipping (rows with a cost only)
     *   ✓ used supplier   = the pinned row, otherwise the cheapest, otherwise the first
     * Competitor row: {seller, link, price, shipping, sold, feedback, pinned}
     * Supplier row:   {source, link, cost, shipping, pinned}
     * ================================================================= */
    function pinnedIndex(list) {
        for (var i = 0; i < list.length; i++) if (list[i].pinned) return i;
        return -1;
    }

    function biggestCompetitor(list) {
        var best = -1;
        list.forEach(function (c, i) { if (best < 0 || isBiggerCompetitor(c, list[best])) best = i; });
        return best;
    }

    function mainCompetitor(list) {
        var p = pinnedIndex(list);
        return p >= 0 ? p : biggestCompetitor(list);
    }

    function supplierTotal(s) {
        var cost = toNum(s.cost);
        return cost === null ? null : Math.round((cost + (toNum(s.shipping) || 0)) * 100) / 100;
    }

    function cheapestSupplier(list) {
        var best = -1;
        list.forEach(function (s, i) {
            var t = supplierTotal(s);
            if (t !== null && (best < 0 || t < supplierTotal(list[best]))) best = i;
        });
        return best;
    }

    function usedSupplier(list) {
        var p = pinnedIndex(list);
        if (p >= 0) return p;
        var c = cheapestSupplier(list);
        return c >= 0 ? c : (list.length ? 0 : -1);
    }

    /** eBay Item ID inside a link ('' when none) – used to spot the same competitor twice. */
    function itemIdOf(link) {
        var m = String(link || '').match(/(?:\/itm\/(?:[^\s\/?#]+\/)?|[?&]item=)(\d{9,15})/i);
        return m ? m[1] : '';
    }

    /* =================================================================
     * One-click button (bookmarklet): the button reads the open page and sends
     *   { url, host, h: {name, price, currency, shipping, image, seller, feedback, sold}, text }
     * where `h` are values read straight from the page and `text` is the page text.
     * fromCapture() turns that into form fields. Values read from the page win; the
     * paste parsers above fill whatever is missing. Nothing is guessed.
     * ================================================================= */
    var CONDITIONAL_FREE = /\b(over|above|orders? of|spend|min(imum)?|prime|members?|membership|first order)\b/i;
    var NOT_US_SHIPPING = /import fees|international|to pakistan|outside the us/i;

    /** "FREE delivery" → 0, "$5.99 delivery" → 5.99; conditional or foreign shipping stays empty with a note. */
    function shippingFromText(raw) {
        var s = String(raw || '').replace(/\s+/g, ' ').trim();
        if (!s) return { value: '', note: '' };
        if (NOT_US_SHIPPING.test(s)) {
            return { value: '', note: 'The page shows shipping to your own country, not to a US buyer. Set the delivery address to a US ZIP code (e.g. 10001) or type the US shipping.' };
        }
        if (/\bfree\b/i.test(s)) {
            if (CONDITIONAL_FREE.test(s)) return { value: '', note: 'Shipping is free only with a condition (e.g. over $35 or with Prime) – type 0 if it applies to you, otherwise the real shipping cost.' };
            return { value: '0', note: '' };
        }
        if (FOREIGN_MONEY.test(s) && !AMOUNT_RE.test(s)) return { value: '', note: 'Shipping is not in US dollars – convert it and type it.' };
        var m = s.match(AMOUNT_RE);
        return { value: m ? cleanNumber(m[1]) : '', note: '' };
    }

    /** "$23.99", "US $23.99/ea", "23.99", "$12.99 - $15.99" → the (first) number; '' for other currencies. */
    function priceFromText(raw, currency) {
        var s = String(raw || '').trim();
        if (!s) return '';
        if (currency && !/^(USD|US\$|\$)$/i.test(currency)) return '';
        if (FOREIGN_MONEY.test(s) && !AMOUNT_RE.test(s)) return '';
        var m = s.match(AMOUNT_RE) || s.match(/^([\d,]+(?:\.\d{1,2})?)$/);
        return m ? cleanNumber(m[1]) : '';
    }

    function fromCapture(payload) {
        var p = payload || {};
        var url = String(p.url || ''), h = p.h || {}, text = String(p.text || '');
        var host = String(p.host || (url.match(/^https?:\/\/([^\/?#]+)/i) || [])[1] || '');
        var out = { role: 'none', platform: '', fields: {}, notes: [] };
        var foreign = h.currency && !/^(USD|US\$|\$)$/i.test(h.currency);
        var ship;

        if (/(^|\.)ebay\./i.test(host)) {
            var id = (url.match(/\/itm\/(?:[^\/?#]+\/)?(\d{9,15})/i) || [])[1] || cleanNumber(h.itemId);
            if (!id) { out.notes.push('Open one eBay listing (its address has /itm/ in it), then click the button.'); return out; }
            var d = parse(url + '\n' + text);
            ship = shippingFromText(h.shipping);
            out.role = 'ebay';
            out.platform = 'ebay';
            out.fields = {
                item_id: id,
                product_name: String(h.name || '').trim() || d.product_name,
                seller_name: String(h.seller || '').trim() || d.seller_name,
                seller_feedback: cleanNumber(h.feedback) || d.seller_feedback,
                seller_price: foreign ? '' : (priceFromText(h.price, h.currency) || d.seller_price),
                buyer_shipping: foreign ? '' : (ship.value !== '' ? ship.value : d.buyer_shipping),
                sold_orders: cleanNumber(h.sold) || d.sold_orders,
                sales_line: d.sales_line,
                variation: d.variation,
                image_url: /^https?:\/\//i.test(h.image || '') ? h.image : ''
            };
            if (foreign) out.notes.push('Prices are in ' + h.currency + ', not US dollars – switch eBay to US $ or type the prices.');
            else if (ship.note && out.fields.buyer_shipping === '') out.notes.push(ship.note);
            return out;
        }

        // Any other site is a supplier (AliExpress, Amazon, CJ, Temu – or a local shop = "other").
        var key = detectSupplier('', [url]);
        var s = parseSupplier(url + '\n' + text, key);
        ship = shippingFromText(h.shipping);
        var cost = foreign ? '' : (priceFromText(h.price, h.currency) || s.supplier_cost);
        var shipping = foreign ? '' : (ship.value !== '' ? ship.value : (ship.note ? '' : s.supplier_shipping));
        out.role = 'supplier';
        out.platform = key;
        out.fields = {
            supplier_link: s.supplier_link || url.split(/[?#]/)[0],
            supplier_cost: cost,
            supplier_shipping: shipping,
            image_url: /^https?:\/\//i.test(h.image || '') ? h.image : ''
        };
        if (foreign) {
            out.notes.push('Prices are in ' + h.currency + ', not US dollars – change the site currency to USD or convert and type them.');
        } else {
            if (ship.note) out.notes.push(ship.note);
            s.notes.forEach(function (n) {
                if (/no supplier link/i.test(n) && out.fields.supplier_link) return;
                if (/price/i.test(n) && !/shipping/i.test(n) && cost) return;
                if (/shipping/i.test(n) && (shipping !== '' || ship.note)) return;
                out.notes.push(n);
            });
        }
        return out;
    }

    return {
        parse: parse, calculate: calculate, money: money, CALC_KEYS: CALC_KEYS, suggestPrices: suggestPrices,
        SUPPLIERS: SUPPLIERS, parseSupplier: parseSupplier, supplierLabel: supplierLabel,
        parseCompetitor: parseCompetitor, parseCompetitors: parseCompetitors, addLine: addLine,
        looksLikeEbay: looksLikeEbay, isBiggerCompetitor: isBiggerCompetitor,
        mainCompetitor: mainCompetitor, biggestCompetitor: biggestCompetitor, supplierTotal: supplierTotal,
        cheapestSupplier: cheapestSupplier, usedSupplier: usedSupplier, itemIdOf: itemIdOf,
        shippingFromText: shippingFromText, fromCapture: fromCapture
    };
})();
