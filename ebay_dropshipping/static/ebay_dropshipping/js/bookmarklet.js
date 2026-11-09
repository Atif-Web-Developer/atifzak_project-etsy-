/*
 * One-click button ("bookmarklet") for the eBay Dropshipping tool.
 *
 * It runs on the page you have open (an eBay listing, or a supplier page on Amazon,
 * AliExpress, Temu, CJ or any shop), reads the product details and opens the tool's
 * capture page, which hands them to your open "Add product" form (or opens a new one).
 *
 * The Settings page turns this file into the button: __TOOL__ is replaced with the
 * tool's address (e.g. http://127.0.0.1:8000) and the code is put in a javascript: link.
 * Only plain ES5 here – it runs inside other websites.
 */
(function () {
    var TOOL = '__TOOL__';
    var MAX_TEXT = 80000;

    function q(sel) {
        try { return document.querySelector(sel); } catch (e) { return null; }
    }
    function txt(sel) {
        var list = sel.split('||');
        for (var i = 0; i < list.length; i++) {
            var el = q(list[i]);
            var t = el && (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
            if (t) return t;
        }
        return '';
    }
    function attr(sel, names) {
        var el = q(sel);
        if (!el) return '';
        for (var i = 0; i < names.length; i++) {
            var v = el.getAttribute(names[i]);
            if (v && !/^data:/i.test(v)) return v;
        }
        return '';
    }
    function meta(prop) {
        var el = q('meta[property="' + prop + '"]') || q('meta[name="' + prop + '"]');
        return el ? (el.getAttribute('content') || '') : '';
    }
    function abs(u) {
        if (!u) return '';
        try { return new URL(u, location.href).href; } catch (e) { return ''; }
    }

    /* JSON-LD "Product" data – many shops (eBay too) publish name, price and picture this way. */
    function ldProduct() {
        var found = null;
        var scripts = document.querySelectorAll('script[type="application/ld+json"]');
        function visit(o) {
            if (!o || found || typeof o !== 'object') return;
            if (Object.prototype.toString.call(o) === '[object Array]') { for (var i = 0; i < o.length; i++) visit(o[i]); return; }
            var t = o['@type'];
            if (t === 'Product' || (t && t.indexOf && t.indexOf('Product') !== -1)) { found = o; return; }
            if (o['@graph']) visit(o['@graph']);
        }
        for (var i = 0; i < scripts.length && !found; i++) {
            try { visit(JSON.parse(scripts[i].textContent)); } catch (e) {}
        }
        if (!found) return {};
        var offer = found.offers || {};
        if (Object.prototype.toString.call(offer) === '[object Array]') offer = offer[0] || {};
        var img = found.image;
        if (img && typeof img === 'object') img = img.url || img[0];
        if (img && typeof img === 'object') img = img.url || '';
        var rate = offer.shippingDetails && offer.shippingDetails.shippingRate;
        return {
            name: found.name || '',
            price: String(offer.price || offer.lowPrice || ''),
            currency: offer.priceCurrency || '',
            image: img || '',
            shipping: rate && rate.value !== undefined ? (Number(rate.value) === 0 ? 'Free shipping' : '$' + rate.value) : ''
        };
    }

    var host = location.hostname;
    var ld = ldProduct();
    var h = {
        name: ld.name || meta('og:title') || txt('h1'),
        price: ld.price, currency: ld.currency,
        image: ld.image || meta('og:image'),
        shipping: ld.shipping
    };

    if (/(^|\.)ebay\./i.test(host)) {
        h.name = txt('h1.x-item-title__mainTitle||.x-item-title__mainTitle||h1') || h.name;
        h.price = txt('.x-price-primary||[itemprop="price"]') || h.price;
        h.shipping = txt('.ux-labels-values--shipping .ux-labels-values__values||[data-testid="ux-labels-values--shipping"]||.ux-labels-values--shipping') || h.shipping;
        h.image = attr('.ux-image-carousel-item.active img', ['data-zoom-src', 'src', 'data-src']) || h.image;
        var card = txt('.x-sellercard-atf__info__about-seller||[data-testid="x-sellercard-atf"]||.x-sellercard-atf');
        var sm = card.match(/^(.+?)\s*\((\d[\d,]*)\)/);
        if (sm) { h.seller = sm[1].trim(); h.feedback = sm[2]; }
        var sold = (txt('.x-quantity__availability||.d-quantity__availability') + ' ' + txt('[data-testid="x-ebay-signal"]')).match(/([\d,]+)\s+sold/i);
        if (sold) h.sold = sold[1];
        var idm = location.pathname.match(/\/itm\/(?:[^\/]+\/)?(\d{9,15})/);
        if (idm) h.itemId = idm[1];
    } else if (/(^|\.)(amazon|amzn)\./i.test(host)) {
        h.name = txt('#productTitle') || h.name;
        h.price = txt('#corePrice_feature_div .a-offscreen||#corePriceDisplay_desktop_feature_div .priceToPay .a-offscreen||' +
            '#apex_desktop .a-price .a-offscreen||#price_inside_buybox||#priceblock_ourprice||#priceblock_dealprice||.a-price .a-offscreen') || h.price;
        h.shipping = txt('#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE||#mir-layout-DELIVERY_BLOCK||#deliveryBlockMessage') || h.shipping;
        h.image = attr('#landingImage', ['data-old-hires', 'src']) || attr('#imgTagWrapperId img', ['data-old-hires', 'src']) || h.image;
    } else if (/(^|\.)aliexpress\./i.test(host)) {
        h.name = txt('[data-pl="product-title"]||h1') || h.name;
        h.price = txt('[class*="price--currentPriceText"]||[class*="price-default--current"]||.product-price-current||[class*="currentPrice"]||.uniform-banner-box-price') || h.price;
        h.shipping = txt('[class*="dynamic-shipping-titleLayout"]||[class*="dynamic-shipping"]||[class*="shipping--wrap"]') || h.shipping;
        h.image = attr('[class*="magnifier--image"]', ['src']) || h.image;
    } else if (/(^|\.)temu\./i.test(host)) {
        h.price = h.price || txt('[class*="goods-price"]||[aria-label*="price" i]');
    }
    h.image = abs(h.image);

    var body = document.body ? (document.body.innerText || '') : '';
    var payload = { v: 1, url: location.href, host: host, title: document.title, h: h, text: body.slice(0, MAX_TEXT) };
    var w = window.open(TOOL + '/static/ebay_dropshipping/capture.html#' + encodeURIComponent(JSON.stringify(payload)), '_blank');
    if (!w) alert('eBay Tool: the browser blocked the new tab. Allow pop-ups for this site and click the button again.');
})();
