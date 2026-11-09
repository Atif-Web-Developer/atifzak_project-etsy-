# Stock Hunting module – guide

White label stock ke liye product hunting, ma'am ke 11 steps ke mutabiq. Poora manual website par hai:
**Stock Hunting → Manual** (`/stock/guide/`).

## Rozana ka kaam
1. **New hunt** → form mein sirf ma'am ki sheet wale fields hain, do hisson mein:
   - **Product selection:** Sr. No (khud), Main Keyword, Sales Trend, 2 Sellers with 100 above sales {Yes/no},
     Avg sales price {USD/POUND}, Total Sellers, seller listing link.
   - **Competitors selection:** har competitor ki ek row – Listing link, Seller Feedback, Sales price, 30 Days sales,
     pack/colour variation. Sr No aur Main Keywords har row mein khud lagte hain.
2. "2 Sellers…", "Avg sales price" aur "seller listing link" competitor rows se **khud bharte hain** (seller listing link =
   sab se zyada 30-din sales wali listing). Khud likh dein to aap ka likha rehta hai; "competitors se lein" se wapas auto.
3. Right side ka **Check** card: 🟢 Source karein / 🟡 Test karein / 🔴 Chhod dein / ⚪ Data poora karein.
4. **Save** → website par, aur Google Sheet ke dono tabs mein bhi.

## Qawaid (rules.py)
| | Shart |
|---|---|
| Zaroori | avg price 13–35 (market currency) · 2 sellers ki 30 din mein 100+ sales · 1+ seller ke feedback 2000 se kam · Sales Trend "Down" nahi |
| Achha ho to behtar | Total sellers 50 tak |

Numbers **Settings → Hunting rules** mein badalte hain. Manual (`/stock/guide/`) poora 11-step tareeqa yaad dilane ke liye hai.

## Google Sheet
- Apni sheet (ma'am ki "stock sheet" ki copy) → Extensions → Apps Script → Settings page se `Code.gs` copy/paste → Deploy as web app (Me / Anyone) → URL Settings mein paste.
- Sirf ma'am ke columns likhe jaate hain – koi extra column nahi. Header naam se pehchane jaate hain ("Slaes" spelling samet).
- Avg price ki currency ($ / £ / A$) cell ke format mein jaati hai, aur sync par wahin se wapas aati hai.
- Sync safety: sheet mein koi hunt ya us ke competitor rows mit jayein to website unhein wapas likh deti hai; sheet ki khali cell website ka data kabhi nahi mitati.

## Files
| File | Kaam |
|---|---|
| `models.py` | `Hunt` (ma'am ke columns + competitors), `StockSettings` (rules + sheet connection), `MARKETS` ($ / £ / A$) |
| `rules.py` | **Saare checks aur faisla** |
| `sheets.py` | Google Sheet sync |
| `google_apps_script/Code.gs` | Sheet ki taraf ka code (columns, ma'am ke headers) |
| `templates/stock_hunting/` | list, form (sheet ke fields), guide (manual), settings |
| `tests.py` | `python manage.py test stock_hunting` |
