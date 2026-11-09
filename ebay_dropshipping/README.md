# eBay Dropshipping module – guide

Ye module eBay product research ke liye hai: eBay listing ka text paste karo, fields khud bhar jati hain,
apni research likho, profit calculate hota hai, aur record **website + Google Sheet dono** mein save hota hai.

---

## 1. Rozana ka kaam (kaise use karein)

1. Sidebar → **eBay Dropshipping** → **Add product**.
2. **Save into sheet tab**: tab chunein. Pehli dafa **➕ Create new tab…** chunein aur naam likhein (maslan `eBay Products`).
   Agla waqt yehi tab khud select hoga.
3. eBay listing page par `Ctrl+A`, `Ctrl+C` → paste box mein `Ctrl+V` → **Auto Fill**.
4. Bharay hue fields check karein (hara blink = khud bhara gaya). Khaali field ka matlab: text mein nahi mila.
5. **Your research** bharein: supplier link/cost, competitor links (har line mein ek), **My Listed Price**, Status.
6. Right side par profit live dikhta hai. **Submit** → SweetAlert popup → form agle product ke liye khaali.

List page par: search, tab/status filter, aur har product ke saamne sheet ka nishan
(✔ sheet mein hai, ⏱ sync ka intezar, ⚠ error – mouse rakhne par wajah).

---

## 2. Data kahan rehta hai aur sync kaise hota hai

| Jagah | Kya |
|---|---|
| Website database (`db.sqlite3`) | Har product ka asal record |
| Google Sheet – aapka banaya tab | Har product ki ek row, calculated columns asli formulas ke saath |
| Google Sheet – `eBay Settings` tab | Fee settings (formulas yahin se value lete hain) – **delete na karein** |

- Website par save → foran sheet mein likha jata hai. Internet na ho to "pending" rehta hai aur agle sync par chala jata hai.
- Sheet mein row add/edit → **Sync now** (ya list page kholne par har 2 minute baad khud) → website par aa jata hai.
- Sheet se row delete ho jaye → agle sync par wapas likh di jati hai (record kabhi ghayab nahi hota).
- Website se **Delete** → dono jagah se delete.
- Jis tab mein pehle se **aapka doosra data** ho (maslan purane `US`, `Uk` tabs) us mein tool kabhi nahi likhta.

---

## 3. Files – kya kahan hai

| File | Kaam |
|---|---|
| `columns.py` | **Columns ki list** (sheet headers aur form labels yahin se) |
| `calculations.py` | **Profit formulas** (website ki taraf) |
| `static/ebay_dropshipping/js/ebay-tool.js` | **Paste parser** (Auto Fill) + live calculator – website aur sheet sidebar dono yahi istemal karte hain |
| `models.py` | Database tables: `Product`, `DropshipSettings` (fees + sheet URL), `UserTabPreference` (aakhri tab) |
| `forms.py` | Form validation (tab naam, Item ID sirf digits, waghera) |
| `views.py` | Pages: list, add/edit, delete, sync, settings, script download |
| `sheets.py` | Google Sheet se baat-cheet aur two-way sync ke qawaid |
| `lists.py` | **Competitor / Supplier tables** ke qawaid (★ Main, sab se sasta, ✓ Use) aur sheet ka text format |
| `templates/ebay_dropshipping/` | Pages ka design (`product_form.html`, `product_list.html`, `settings.html`) |
| `google_apps_script/Code.gs` | Sheet ki taraf ka code: menu, formulas, columns, sync API |
| `google_apps_script/Form.html` | Sheet ke andar wala sidebar form |
| `static/ebay_dropshipping/js/bookmarklet.js` | **One-click button** ka code (page se data padhta hai) – Settings page isi se button banata hai |
| `static/ebay_dropshipping/capture.html` | Button ka data aapke khule form tak pohanchata hai (ya naya form kholta hai) |
| `tests.py` | Automatic tests – har change ke baad chalaein |

---

## 4. Aam changes kaise karein

**Har change ke baad:**
```powershell
python manage.py test ebay_dropshipping
```
Aur agar `Code.gs`/`Form.html` ya `ebay-tool.js` badla ho to sheet mein update karein (neeche section 5).

### Naya column add karna (maslan "Notes")
1. `models.py` → `Product` mein field: `notes = models.TextField(blank=True)`
2. `python manage.py makemigrations ebay_dropshipping` phir `python manage.py migrate`
3. `columns.py` → sahi jagah: `Column('notes', 'Notes', 'manual', 'multiline'),`
4. `Code.gs` → `COLUMNS` mein wahi key: `{ key: 'notes', header: 'Notes', group: 'manual', type: 'textarea' },`
5. `templates/ebay_dropshipping/product_form.html` → "Your research" card mein:
   `<div class="col-12">{% include 'partials/field.html' with field=form.notes %}</div>`
   (Sheet ka sidebar form khud ban jata hai – wahan kuch nahi karna.)
6. Sheet update karein (section 5). Purane tabs mein naya header khud aakhir mein jud jata hai.

### Formula badalna
Teen jagah ek jaisa change karein:
- `calculations.py` → `calculate()`
- `static/ebay_dropshipping/js/ebay-tool.js` → `calculate()`
- `Code.gs` → `FORMULAS`

`tests.py` mein `test_example_from_spec` ki expected values bhi update karein.

### Status options badalna
- `models.py` → `STATUS_CHOICES` (aur rang ke liye `STATUS_COLORS`) → `makemigrations` + `migrate`
- `Code.gs` → `STATUS_OPTIONS`

### Default fees
Website: **eBay Dropshipping → Settings → Fees** (code badalne ki zaroorat nahi).

### Auto Fill kisi field ko sahi nahi pakar raha
`ebay-tool.js` → `parse()` mein har field ka apna chhota hissa hai (comment `// ---- Seller name …` waghera).
Naya text sample ho to mujhe bhejein ya wahan regex theek karein.

---

## 5. Google Sheet ka code update karna

Jab bhi `Code.gs`, `Form.html` ya `ebay-tool.js` badle:
1. Website → eBay Dropshipping → **Settings** → **Code.gs → Copy code**.
2. Sheet → Extensions → Apps Script → `Code.gs` mein sab select karke paste. Isi tarah `Form` file mein **Form.html** paste.
3. Save (`Ctrl+S`).
4. **Deploy → Manage deployments → ✏ (Edit) → Version: New version → Deploy.**
   (Nayi deployment mat banayein, warna URL badal jayega.)
5. Sheet ko refresh karein, phir menu **eBay Dropshipping → Update formulas in all rows**.
   Isse purani rows mein bhi naye formulas lag jate hain (naye columns khud aakhir mein jud jate hain,
   aur purane naam wale headers – jaise "Minimum Listing Price" – khud naye naam mein badal jate hain).

6. Styling ke liye menu **eBay Dropshipping → Format headers** (neeche section 6).

---

## 6. Sheet ki styling (Format headers)

Naya tab banne par ye styling khud lagti hai. Purane tabs par lagane ke liye menu
**eBay Dropshipping → Format headers** chalayein – jitni baar chahein, kuch kharab nahi hota.
Sirf formatting badalti hai: data aur formulas nahi chhede jate, aur jin tabs mein tool ka "ID" column nahi
(aapke apne purane tabs) unhe bilkul nahi chhoota jata.

| Kya | Kaisa |
|---|---|
| Header (row 1) | Freeze, bold safed text size 10, wrap, center, height 45 px, har column par filter button |
| 🔵 Dark blue `#1F4E78` | Auto Fill columns (ID … Variation) |
| 🟢 Dark green `#38761D` | Manual columns (Supplier Link … Status) |
| ⚫ Dark grey `#434343` | Calculated columns – data cells halke grey `#F3F3F3`, haath na lagayein |
| Header note | Mouse rakhne par column ka matlab |
| Paise | `$#,##0.00`, manfi laal |
| Profit %, ROI % | `0.00%`, manfi laal |
| Rows | Har doosri row halki shade (banding) |
| Links | Ek line mein clip, limited width |

Rang, widths, notes aur formats badalne hon to `Code.gs` mein **`SHEET_STYLE`** aur **`COLUMN_NOTES`** dekhein.
Note: Format headers is tab ki purani alternate-colour (banding) settings hata kar nayi lagata hai.

---

## 7. Profit ke qawaid (Nov 2026)

| Column | Formula |
|---|---|
| Total Sale | My Listed Price + My Buyer Shipping |
| eBay Fee | Total Sale × (1 + Sales Tax %) × 13.6% + ($0.30 agar Total Sale ≤ $10, warna $0.40) |
| Ad Fee | Total Sale × Ad Rate % |
| Total Cost | Supplier Cost + Supplier Shipping + Other Cost + eBay Fee + Ad Fee |
| Profit | Total Sale − Total Cost |
| Profit % | Profit ÷ Total Sale × 100 |
| Break-even Price | (Costs + $0.40) ÷ (1 − 13.6% × (1 + Tax %) − Ad %) − My Buyer Shipping |
| ROI % | Profit ÷ (Supplier Cost + Supplier Shipping + Other Cost) × 100 |

- **My Buyer Shipping** woh shipping hai jo *aap* apne buyer se lete hain (0 = free shipping) – formulas isi se chalte hain.
  **Competitor Shipping** (Auto Fill) competitor ki shipping hai – sirf muqable ke liye, hisaab mein shamil nahi.
- Rates settings mein editable hain. eBay rates badalta rehta hai – pehli sale ke baad Seller Hub mein asal fee se milayein.

---

## 8. One-click button (bookmarklet) aur Image

**Lagana (sirf ek dafa):** Settings → *One-click button* → hara **eBay Tool** button bookmarks bar par drag karein
(bar nazar na aaye to `Ctrl + Shift + B`). Chrome, Edge aur Firefox teeno mein chalta hai.

**Istemal:**
1. Ek tab mein *Add product* khula rakhein.
2. **eBay listing** khol kar button dabayein → pehli dafa product ki fields bharti hain (ID khali ho to).
   Agli eBay listings **competitor** ban kar Competitor Links mein judti hain.
3. **Supplier page** (Amazon, AliExpress, Temu, CJ, koi bhi shop) par button → Supplier Link, Cost, Shipping aur Image.
4. Form check kar ke **Submit** – button khud kuch save nahi karta.

**Qawaid:**
- Har competitor aur supplier **table ki apni row** banta hai (section 9).
- Jo cheez page par na mile woh khali rehti hai aur note aata hai – andaza nahi lagaya jata.
- US $ ke ilawa currency (Rs, PKR, €) convert nahi hoti – site ko USD / US delivery address par karein.
- Amazon par "Deliver to Pakistan" wali shipping US buyer ki nahi hoti – US ZIP (maslan 10001) set karein.
- Tool hamesha **ek hi address** se kholein (button `127.0.0.1:8000` ke liye bana ho to `localhost:8000` par nahi chalega).
- Website ka koi selector badal jaye (eBay/Amazon design change) to `bookmarklet.js` mein `txt('…')` wali lines theek karein,
  phir Settings se button dobara drag karein.

**Image:** `Image` column mein tasveer ka link save hota hai. Google Sheet mein ye `=IMAGE("link")` ban kar tasveer dikhata hai
(bari dekhne ke liye row ki height barha dein). Sheet mein koi saada link likhe to sync par woh bhi website mein aa jata hai.
Purane tabs mein `Image` column aakhir mein add hota hai.

---

## 9. Competitor aur Supplier tables

Form mein **Suppliers** aur **Competitors** do tables hain – har ek ki apni row, delete button ke saath.
Rows paste box, one-click button ya **Add** button se banti hain; har cell mein seedha likh bhi sakte hain.
Same eBay listing / same supplier link dobara aaye to nayi row nahi banti, purani update hoti hai.

| | Qaida |
|---|---|
| **★ Main competitor** | Khud: sab se bara (zyada sold, phir zyada feedback). *Main competitor* dropdown ya ★ par click se badlein. Is ke Sold/Feedback sheet ke single columns mein jaate hain. |
| **Green supplier** | Sab se sasta (Cost + Shipping). |
| **✓ Use for profit** | Khud: sab se sasta. *Use for profit* dropdown ya ✓ par click se koi aur chunein (maslan tez shipping wala). Profit, Break-even aur sheet ke Supplier Link/Cost/Shipping isi se. |

**Google Sheet:** do naye columns – **All Suppliers** aur **All Competitors** – har row ek line:
```
✓ AliExpress | $3.10 | ship $0.71 | https://www.aliexpress.com/item/…
★ BigSeller | $21.50 | ship $1.00 | sold 50 | fb 9000 | https://www.ebay.com/itm/…
```
Sheet mein in lines ko badlein to sync par table bhi badal jaata hai. Sheet ke single columns (Supplier Cost,
Competitor Solds…) badlein to woh ✓ / ★ wali row mein chale jaate hain. Purane products ki tables unke single
fields se khud ban gayi hain (migration 0007).

