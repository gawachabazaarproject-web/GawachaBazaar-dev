# Admin Product Management — UX Research and Redesign

> **Status:** Proposal; Phase 1 and most of Phase 2 are now implemented (2026-10-26, uncommitted) - see [PRODUCT_INVENTORY_SIMPLIFICATION_AUDIT](PRODUCT_INVENTORY_SIMPLIFICATION_AUDIT.md) and [KNOWN_ISSUES](KNOWN_ISSUES.md) UX-1..9. Original note: **Phase 1 partly implemented in the Admin on 2026-10-26 (uncommitted, type-checked only, not tried in a browser or against an API):** Add product form (size chips, per-kg fill, opening stock, Save & publish / draft, progress list with retry, duplicate-name warning, remembered category and sizes, non-Latin slug fix, `?from=` duplicate), merged "Sizes, prices and stock" table with inline price edit + Undo, product-level low-stock alert, Advanced section, list status tabs and row actions, default warehouse in Add stock. **Not done:** composite backend endpoint, bulk grid/CSV, list "Low stock" tab, one-save-model on the product page. **Date:** 2026-10-26.
> **Evidence base:** the Admin source (`Admin/app/(admin)/products/*`, `inventory/*`, `components/ReceiveStockForm.tsx`, `lib/permissions.ts`), the backend (`backend/app/services/catalog.py`, `inventory.py`, `cart.py`, `order.py`), and [`CATALOG.md`](../05-domains/CATALOG.md) / [`INVENTORY.md`](../05-domains/INVENTORY.md). Nothing was run in a browser; screen behaviour is read from code.
> **Not measured:** all time figures below are estimates from counting inputs and clicks. They must be validated by timing real staff (plan in §8).
> **Goal:** less work for the operator. Every proposal is justified against that, not against "more features".

---

## 0. Summary of the recommendation

One sentence: **make "Add product" a single, remembered, auto-filled form that also takes the first stock and publishes in one save (backed by one transactional endpoint), make the product page one table of "Sizes, prices and stock", and push lots, batches, SKUs, slugs and history behind an Advanced drawer and the Inventory module.**

| Action | Items |
|---|---|
| **Remove from the primary workflow** | SKU, slug, status dropdown, "Also show in", publish checkbox, per-row unit dropdowns, warehouse choice, share/"unassigned stock" concept, Merchandising and Reviews placeholders, Activity feed, delete button on list rows, confirm dialogs for price changes |
| **Combine** | Product + sizes + prices + first stock + publish into one screen and one save. "Variants & Pricing" and "Inventory" into one table |
| **Automate** | SKU, slug (unique), size labels, per-kg price pre-fill, default warehouse, default category and size set, low-stock alert conversion to kg, draft→live transition |
| **Hide (Advanced)** | SKU/slug, price history, reserve per size, share of stock per size, lots and batches, reservations, transfers, waste, packaging, audit |
| **Redesign** | Product detail page, Products list (tabs + quick actions), error recovery, receive-stock form |
| **Keep** | Variants as the sellable unit, prices per variant with preserved history, shared stock pool, reservations, status model, audit log, permission checks |
| **Add** | Bulk sheet (paste/CSV), duplicate product, size-set presets, inline price edit with undo, product-level low-stock alert in kg, duplicate-name warning, resumable drafts |

---

## 1. Current system map

```
Category ──< Product ──< Variant (a pack size: 250 G, 1 KG, 1 DOZEN)  ──< Price (history, one current)
                │              └──< InventoryLot (variant + warehouse + Batch) ──< StockMovement (ledger)
                ├──< Image (one primary)
                └──< extra category links
Status: Product DRAFT/ACTIVE/INACTIVE/ARCHIVED; Variant ACTIVE/INACTIVE/ARCHIVED
Reservation (30 min, FIFO across lots) is created at checkout and never seen at product creation.
```

### A. Concepts the operator must understand (keep visible)

| Operator word | Backend entity | Why they need it |
|---|---|---|
| Product (Tomato) | `products` | The thing they think of |
| Category | `categories` | Where customers find it |
| Photo | `product_images` (primary) | Sells the product |
| **Size** (250 g pack) | `product_variants` | What customers actually buy |
| **Price** (of that size) | `prices` (current) | Money |
| **Stock** (50 kg) | pool of `inventory_lots` | Can it be sold |
| **Low-stock alert** | `reserve_level` | Know when to reorder |
| **Live / Hidden / Draft / Archived** | `status` | Is the customer seeing it |
| Warehouse | `inventory_locations` | Only if more than one exists |

### B. Concepts to hide (Advanced, or never shown)

IDs, SKU, slug, batch, lot, stock movement, share lot / unassigned stock, price history rows, reservation, `INACTIVE` vs `ARCHIVED` nuance, extra-category links, `reserved_quantity`, unit-family pooling rules.

### How the current "add a product" actually runs (from code)

1. `/products/new`: name, category, extra categories, photo, N rows of (size, unit, price), description, publish checkbox, advanced (slug, SKUs).
2. On save, sequentially: `POST product (DRAFT)` → upload photo → for each size `POST variant` then `POST price` → `PATCH status ACTIVE`. A failure leaves a partial draft.
3. Redirect to `/products/[id]`. Stock is **not** part of creation ("Add stock afterwards from Inventory").
4. Staff then scroll to Inventory → "+ Add stock to sizes" → choose warehouse → total + unit → optionally divide between sizes → Save. That is `receiveStock` then `setStockShares`, again two calls.

---

## 2. UX problems (Problem → Why it wastes time → Solution → Benefit)

| # | Problem (evidence) | Why it wastes time / causes errors | Solution | Benefit |
|---|---|---|---|---|
| 1 | Stock is not part of creation; staff must open a second place to add it (`new/page.tsx` hint text; `[id]/page.tsx` Inventory section). | A product can go live with 0 stock; staff must remember a second task; two screens. | "Opening stock" field in the Add form (total + unit). | −1 screen, −7 to 10 interactions, no forgotten stock. |
| 2 | Each size row has a number box **and** a unit dropdown that defaults to `KG` (`emptyVariant`). 250 g and 500 g need a dropdown change every time. | 2 extra clicks per gram-size; wrong unit (kg vs g) = 1000× price error. | One-tap size chips (250 g / 500 g / 1 kg) from a preset, plus a text parser ("250g", "1 kg", "12 pcs"). Show the readable label back. | ~8 fewer interactions for 3 sizes; fewer unit mistakes. |
| 3 | Price is typed per pack; the per-kg rate appears only afterwards. Staff usually think "₹60 a kg". | Mental arithmetic for every size; rounding mistakes. | "Price per kg" quick-fill that proposes pack prices (editable); show per-kg rate beside each price. | 1 entry instead of 3; fewer wrong prices. |
| 4 | Category is required and unremembered; "Also show in" checklist is always shown. | Repeated selection for a batch of vegetables; rare feature takes space. | Remember last category (chips of recent ones); put "Also show in" under Advanced. | −2 to 3 interactions per product. |
| 5 | Slug/SKU rules: `slugify` keeps only `a-z0-9`; a Devanagari/Marathi name gives an **empty slug** and a SKU like `-250-G`. A repeated name returns 409 *after* the draft was created. (Read from `slugify` in `new/page.tsx`; **not run**.) | Hard-to-diagnose failure; partial product left behind. | Server generates slug/SKU with transliteration fallback and `-2` suffix on collision; duplicate-name warning before saving. | No SKU/slug thinking; no partial failure from collisions. |
| 6 | Publishing is a checkbox plus a separate `PATCH` after creation; detail page has a 4-value status dropdown (`DRAFT/ACTIVE/INACTIVE/ARCHIVED`). | `INACTIVE` vs `ARCHIVED` is unclear to non-technical staff; "ACTIVE" is not a staff word. | Buttons **Save & publish** / **Save as draft**; statuses shown as **Live / Hidden / Draft / Archived**; one segmented Live/Hidden switch. | Fewer decisions, no ambiguity. |
| 7 | Creation is up to 2 + 2×N + 2 requests; failure shows e.g. "…The product was created as a draft - finish it from its page." | Staff do not know what exists; retry creates duplicates. | One transactional endpoint (backend) and, until then, a progress checklist with Resume (frontend). See §11. | No partial products; clear recovery. |
| 8 | Product page shows each size twice: **Variants & Pricing** (price) and **Inventory** (stock + reserve). | Scrolling and mental joining; two places to "fix a size". | One table: Size \| Price \| In stock \| Alert \| Live. | Everything about a size in one row. |
| 9 | Changing a price opens a confirm dialog with text "creates a new price effective immediately… history". | Three clicks and jargon for the most common edit. | Edit in place; save on Enter; **Undo** toast (undo writes the previous price as a new row, history kept). | 1 field + Enter instead of dialog; reversible. |
| 10 | Mixed save models: General needs **Save changes**, but price/size/photo/status actions save immediately; only General warns on leaving. | Staff believe edits are saved when they are not (or the reverse). | Everything saves per field with visible "Saved ✓", or one sticky Save bar for the whole page — pick one (proposal: per-field/per-row save, no General Save button except for the text block). | Fewer lost edits. |
| 11 | Failures swallowed: `updateVariant(...).catch(() => undefined)`, `updateImage(...)`, `deleteImage(...)` in `[id]/page.tsx`. | A failed Deactivate/Set primary looks like nothing happened. | Show an inline error and revert the control. | Fewer silent errors. |
| 12 | Reserve level is per size, **in packs**, default 10 (`stock_levels.py`). 10 × 250 g = 2.5 kg but 10 × 1 kg = 10 kg for the same pool. | Staff must compute; alerts are inconsistent between sizes. | Single product-level "Low-stock alert" in kg (or pieces); UI converts to each size's pack count. | Intuitive alert; no backend change needed to start. |
| 13 | Receive-stock form: choose warehouse every time; total + unit; optional "Divide between sizes" with "Unassigned/shared" wording; Notes; review box. | Share/lot concepts leak; the warehouse is almost always the same one. | Default warehouse (single or last-used or packing point); total only; "Reserve part of this for one size" under Advanced; notes under Advanced. | 3 fields → 2; no jargon. |
| 14 | `receiveStock` then `setStockShares` run as separate calls; failure shows "Stock received… but dividing it failed". | Partial state to explain to staff. | Do both in one backend call when the divide option is used (§11). | No half-done receipts. |
| 15 | List: stock column uses a fixed `< 10` rule (`LOW_STOCK_THRESHOLD`) with no unit; real alert is per-size reserve. | List says "OK" while Inventory says "low" (or reverse). | Use the product-level alert; show unit ("34 kg"). | One truth for "low". |
| 16 | List rows have Delete next to a clickable row; deleting is rarely valid (history blocks it). | Dangerous action in the main path; confirm dialog fatigue. | Move Delete into the row overflow, ADMIN only; recommend Archive. | Fewer mistakes. |
| 17 | List has no quick actions; changing a price or adding stock means opening the product. | Navigate away and back for one number. | Row actions: **+ Stock**, **Price**, **Live/Hidden** inline. | Common edits in 1–2 clicks, no navigation. |
| 18 | Placeholders on every product page: Merchandising, Reviews (no backend). Activity always loaded. | Noise; asks nothing of the operator. | Remove placeholders; Activity moves to a "History" drawer for ADMIN. | Cleaner page. |
| 19 | No duplicate-name check, no "duplicate product", no bulk anything. | Each product costs the full workflow. | Duplicate action, duplicate warning, bulk sheet (§10). | Large time saving for catalogue loads. |
| 20 | Photo is optional with no nudge. | Products go live without pictures (the app shows a placeholder). | "Missing photo" tag on list; do not block publishing. | Quality without friction. |
| 21 | Permissions: `products.*` exist only for `ADMIN`; `OPERATIONS` and `HUB_STAFF` have `inventory.*` and no product permissions (`Admin/lib/permissions.ts`). | Warehouse staff who receive goods cannot add the missing product; they ask an admin. | Business decision for the client: grant OPERATIONS create/update/price/media (without delete). Do not change without approval. | Fewer hand-offs. |
| 22 | Inventory page leads with seven metrics ("SKUs", "On hand", "Reserved"…) and an **Add warehouse** button. | Jargon on the page staff open most. | Default tab "Stock by product" with Low/Out counts; warehouse setup in Settings/Advanced. | Faster scanning. |

---

## 3. Research: how other systems do it

Sources are linked. **Reliability note:** primary vendor pages were fetched for Shopify and NN/g; other vendors were read from search results (some third-party), BigCommerce, Lightspeed, Toast and quick-commerce admins were **not** retrievable, so nothing below claims their behaviour.

| Question | Finding | Source |
|---|---|---|
| Show the essentials first | "Defer advanced or rarely used features to a secondary screen"; keep the initial list short; make the path to advanced visible; more than two levels hurt usability; staged wizards fail when steps are interdependent. | [NN/g — Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/) |
| Variants live inside the product page | Shopify: click a variant to change options, pricing, inventory; select variants with checkboxes and use **Bulk edit**; limit of three options. | [Shopify — Edit variants](https://help.shopify.com/manual/products/variants/edit-variants) |
| Variant list needs scanning aids | Filters and search appear once a list exceeds 10 option values; variant images added. | [Shopify changelog — improved variant display](https://changelog.shopify.com/posts/improved-variant-display) |
| Drafts | Draft is a holding state while preparing; Active makes a product available; Archived for discontinued. New products default to draft to avoid accidental publishing (community report). | [Shopify changelog — statuses](https://changelog.shopify.com/posts/manage-your-products-with-statuses), [Shopify community](https://community.shopify.com/t/default-product-status-when-adding-new-product/23157/1) |
| Inventory editing | Spreadsheet-style editor; enter the **total** wanted, not a delta; "Inventory mismatch" dialog if numbers changed meanwhile; the quick editor records no movement trail — use the adjustment flow when tracking matters. | [Shopify — bulk editing inventory](https://help.shopify.com/manual/products/inventory/managing-inventory-quantities/bulk-editing-inventory) |
| Bulk edit / import | Square: bulk-edit up to 250 variations from the Item Library; import via .xlsx/.csv; export a copy first; variations need unique SKUs. | [Square — bulk edit](https://squareup.com/help/gb/en/article/8228-bulk-edit-items-in-square-dashboard), [Square — basic inventory](https://square.com/help/us/en/article/5228) |
| Quick create for small catalogues | Square offers a quick-create path for small libraries (≤10 items) (secondary summary). | search result summarising [Square help](https://square.com/help/us/en/article/5228) |
| Template-driven uploads with validation | Amazon: generate a template, fill it, "Check your file", upload, read the processing report for failed rows. | [Amazon Seller Central — FBA bulk](https://sellercentral.amazon.com/gp/help/external/200327780), [Linnworks guide (third party)](https://www.linnworks.com/blog/bulk-listings-amazon/) |
| Import pitfalls | WooCommerce variation imports break when parent/child IDs or attribute columns misalign; core importer lacks "update existing only" by SKU (third-party). | [WP Sheet Editor](https://wpsheeteditor.com/woocommerce-import-variable-products-variations/) |
| Mapping on import | Zoho: upload CSV/TSV, auto-map fields, fix the unmapped ones manually. | [Zoho Inventory — item creation/import](https://zstatic.zohostatic.com/in/inventory/help/items/item-creation.html) |
| Reorder points | Odoo: minimum triggers replenishment, orders up to the maximum, rules per variant (v14 docs). Ordoro: thresholds per product and warehouse, bulk-settable by CSV. | [Odoo reordering](https://www.odoo.com/documentation/user/14.0/uk/purchase/products/reordering.html), [Ordoro](https://support.ordoro.com/how-to-set-up-the-low-stock-threshold/) |

### Principles extracted (not copied)

1. **One page, essentials first, advanced on demand** (NN/g, Shopify). Not a wizard: product, sizes, price and stock are interdependent.
2. **Variants are rows in a table**, editable inline, with bulk edit (Shopify, Square).
3. **Draft by default, explicit publish** (Shopify). We make "Save & publish" the primary button because Gawacha staff publish most products immediately.
4. **Set totals, not deltas** for counts (Shopify), but keep a movement trail for receive/adjust (Gawacha already has a ledger; keep it).
5. **Validate before commit and report per row** (Amazon "Check your file"; Woo failures show what to avoid: all-or-nothing imports with cryptic errors).
6. **Preview import in an editable grid**, not a file-only black box (Zoho mapping, Shopify bulk editor).
7. **Alerts in the staff member's unit** (kg) and per product — the Gawacha default of 10 *packs* contradicts this.

---

## 4. Ideal creation flow (what the operator thinks)

"I want to sell tomatoes."

```
Name: Tomato        Category: Vegetables ▾ (last used)        Photo: [drop]
Sizes: (250 g) (500 g) (1 kg)  + other          ← tap chips, preset remembered
Price: [₹20] [₹35] [₹60]   (₹80/kg · ₹70/kg · ₹60/kg)     or "Rate per kg ₹60 → fill"
Opening stock: [50] [kg ▾]     → "Stored in Main warehouse"
[Save & publish]   [Save as draft]        ▸ Advanced
```

Everything else (SKU `TOMATO-250G`, slug `tomato`, status transitions, batch `ADMIN-xxxx`, lot, `RECEIPT` movement, low-stock alert default) is generated.

---

## 5. Smart defaults and memory

| Value | Default | Where it comes from |
|---|---|---|
| Status | **Live** when "Save & publish"; **Draft** otherwise | Button choice |
| Slug | slugified name; transliteration for Devanagari; `-2` if taken | Server |
| SKU | `SLUG-SIZE`, e.g. `TOMATO-250G`; `-2` if taken | Server |
| Size label | generated from amount + unit (already `sizeLabel`) | Client/Server |
| Unit | taken from the size text; chips avoid the dropdown | Client |
| Size set | last used for that category; presets "Veg: 250 g/500 g/1 kg", "Fruit: 500 g/1 kg", "Eggs: 6/12/30 pcs" (editable per shop) | Remembered per operator (browser storage in MVP; server-side per user later) |
| Category | last used; recent chips | Remembered |
| Pack price | from "rate per kg" if used; otherwise empty (never guess money) | Client pre-fill, always editable |
| Warehouse | the only active one, else last used, else packing point | Client |
| Opening stock unit | the unit family of the sizes (kg for weight) | Client |
| Low-stock alert | product-level, default **10 kg** (or **10 pcs**), converted per size | Client/Server |
| Default image | none; placeholder; "Missing photo" tag | — |
| Description | empty (optional) | — |
| Currency | INR | existing |
| Reserve per size | derived from the product alert; editable under Advanced | — |

Backend rule kept: the entered prices go to the server explicitly; the pre-fill is only a convenience in the form. Customer totals, fees and discounts remain backend-computed.

---

## 6. Hiding backend complexity

Never in the primary screen: IDs, SKUs, slugs, lots, batches, movements, price history, status transitions, relationships.

**Advanced settings** (a collapsed section on Add, a drawer on the product page) contain:
- Product code (SKU) per size, web address (slug), "Also show in" categories.
- Low-stock alert per size (instead of the product value).
- Reserve part of the stock for one size (share).
- Price history, valid-from date for a future price.
- History (audit) — `audit`/ADMIN only.

Only one level of "Advanced" (NN/g warns that three or more levels lose users).

Terminology mapping used throughout the UI:

| Today | Staff word |
|---|---|
| Variant | Size |
| SKU | Product code |
| Slug | Web address |
| Receive stock | Add stock |
| Reserve level | Low-stock alert |
| Reconcile | Stock count |
| Remove stock / DAMAGE / WASTE | Remove stock (reason: damaged, wasted, correction) |
| Unassigned stock | Shared by all sizes |
| ACTIVE / INACTIVE | Live / Hidden |
| DRAFT / ARCHIVED | Draft / Archived |

---

## 7. Inventory: simple mode vs advanced

### Simple mode (product page and list)

- **In stock:** `50 kg` (the pool total), with a per-size readout on hover/expand: "≈ 200 × 250 g, 100 × 500 g, 50 × 1 kg".
- **Low-stock alert:** `10 kg`.
- Actions: **+ Add stock** (amount, unit, warehouse already chosen), **Stock count** (set the real total; difference recorded as an adjustment with a reason), **Remove** (reason: damaged / wasted / correction).
- Status chip: OK / Low / Out (computed from the existing stock-level rules).

### Advanced mode (Inventory module, ADMIN/OPERATIONS/HUB_STAFF per permission)

Unchanged capabilities: lots, batches, expiry, reservations, share per size, transfers, waste, damage, packaging, reconciliation, warehouses. Reached by:
- the Inventory sidebar item (keeps today's pages), and
- "Advanced stock ▸" from a product (deep link filtered to that product).

### Why both Products → Inventory and Inventory → Products

- Staff **start from the product** ("how many tomatoes?"), so Products shows stock and the three common actions.
- Operations staff **start from the delivery or warehouse**, so Inventory stays a first-class module with a product-first default tab ("By product", already built).
- Same data, two entry points; the only rule: lots and batches never appear in the simple views.

---

## 8. Time and effort comparison (estimates)

Scenario: new product "Tomato", 3 sizes (250 g / 500 g / 1 kg), prices ₹20 / ₹35 / ₹60, 50 kg stock, photo, published, one warehouse.

Counting from `new/page.tsx`, `[id]/page.tsx`, `ReceiveStockForm.tsx`. "Interactions" = clicks + typed fields + selections.

| Metric | Current | Proposed |
|---|---|---|
| Screens | 2 (Add page → product page with stock form) | 1 (list → Add; stays on the product page after save) |
| Form fields / controls | ~15 on Add (name, category, extra categories, photo, 3 × (size, unit, price), description, publish) + ~5 for stock (warehouse, total, unit, optional 3 shares, notes) | 7 visible (name, category, photo, size chips, 3 prices, stock amount) |
| Manual inputs | ~13 typed/selected values | ~6 (name, 3 prices or 1 rate, stock) + category/photo |
| Interactions (clicks + typing steps) | ≈ 28–32 | ≈ 10–13 |
| Technical concepts exposed | SKU, slug, unit dropdown, "also show in", publish status, stock share/unassigned, warehouse | None in the primary form |
| Steps (decisions) | create → add sizes → price → publish → navigate → warehouse → stock | name → sizes → price → stock → publish |
| Backend requests per save | 2 + 2×3 + 2 + 1…2 ≈ 11–12 | 1 (composite) + optional photo |
| Error opportunities | wrong unit per row ×3, slug/SKU collision, partial failure, forgotten stock, forgotten publish, wrong warehouse | wrong price typo (checked by per-kg display), photo failure (non-blocking) |
| Estimated completion time | 4–7 min for a new operator, 2–4 min for an experienced one | 1–2 min, ≈30–60 s repeat product with remembered sizes |

**How to validate:** time 3 staff × 5 products on the current Admin (baseline), then on a build of Phase 1; record time, interactions, errors and "needed help". Success target: median ≤ 90 s for a three-size product and zero partial products. I cannot justify a firmer number without that measurement.

---

## 9. Pricing flow

- **Create:** per-size price boxes, or "Rate per kg" that pre-fills (editable). Display `₹60 / kg` next to every price (the existing `ratePerBaseUnit` logic). Reject price ≤ 0 (existing rule).
- **Change a price:** click the price in the table, type, Enter. Toast: "Tomato 1 kg ₹60 → ₹65 · Undo". Backend: a new `prices` row (`POST /catalog/admin/variants/{id}/prices`), history preserved, audit entry written. Undo posts the old value as a new row.
- **Change all sizes by a rate:** "Set rate per kg" or "+10%" on the product (applies to every size, shows a preview table before saving; writes one new price per size).
- **Future price (advanced):** valid-from date under Advanced; keep out of the primary flow.
- **Price history:** drawer for ADMIN/`products.manage_pricing` only.

---

## 10. Bulk product entry

### MVP (Phase 2)

**Add many** screen: an editable grid, one row per product, and a paste target.

| Product | Category | Sizes | Prices | Stock | Photo | Status |
|---|---|---|---|---|---|---|
| Tomato | Vegetables | 250g, 500g, 1kg | 20, 35, 60 | 50 kg | – | Ready |
| Potato | Vegetables | 500g, 1kg, 2kg | 20, 35, 60 | 80 kg | – | Ready |
| Onion | Vegetables | *(set preset)* | 25 /kg | 100 kg | – | Needs prices |

- **Paste from a spreadsheet** (tab-separated) directly into the grid — covers CSV without a file picker.
- **CSV upload** populates the same grid so the operator reviews before creating (Zoho/Shopify pattern); a downloadable template with the columns above.
- **Fill down / apply preset to selected rows**: category, size set, rate per kg.
- Row states: Ready / Needs fix (reason in the cell) / Created ✓ / Failed (reason + retry).
- **Create all**: each row is its own atomic request (composite endpoint), results shown per row; failed rows stay editable. This avoids a Woo-style all-or-nothing failure.
- **Duplicate product**: opens Add prefilled (sizes and prices) with the name cleared.
- **Duplicate-name warning** inside the grid.

### Phase 2 additions on existing products
- Select rows on the Products list → **Bulk price** (set, +%, +₹ with preview), **Bulk hide/publish**, **Bulk stock count** (enter total per product, set not delta — Shopify's rule; ledger still written as adjustment/reconcile).

### Later (Phase 3)
- Server-side CSV import with dry-run and an error CSV; per-category templates stored on the server; image bulk matching by filename; scheduled prices.

### Explicitly not MVP
Barcodes, multi-option matrices (colour × size), image zip import, product bundles — none reduce today's operator work for a fresh-food catalogue.

---

## 11. Error handling

### UX (frontend only, Phase 1)

- **Validate before sending:** required fields, size and price > 0, duplicate sizes, over-stock mismatch, duplicate product name — all inline.
- **Progress checklist** instead of a spinner: ☑ Product saved ☑ Photo ☑ 250 g ☐ 500 g (failed) ☐ 1 kg ☐ Stock ☐ Published. One button: **Retry remaining steps**.
- **Resumable:** remember the created product id in `sessionStorage`; on retry, read the product, skip sizes that already exist, create the rest. Never re-`POST` a product that exists.
- **Safe auto-retry:** only network errors on idempotent calls; never auto-retry a `POST` that may have succeeded.
- **Where drafts show up:** the Drafts tab flags **Incomplete** (no size, no price, or no stock) with a "Finish" action.
- **Non-blocking photo:** a failed upload shows "Photo not saved — retry" and does not block publishing.
- **No silent failures** (see problem 11).

### Backend (separate work item)

New endpoint (name to be decided): `POST /catalog/admin/products/quick-create` that, in **one DB transaction**: creates the product, extra categories, variants (auto SKU, unique), prices, optional image URL, optional opening stock through the inventory service (get-or-create lot + `RECEIPT`, no commit inside, lock order unchanged), and sets the final status (`ACTIVE` only if at least one active size has a price). Returns the full product. Requirements and constraints:
- additive (installed mobile apps are untouched; no field removed or renamed);
- permission check for each part (`products.create`, `products.manage_pricing`, `products.manage_media` when an image is given, `inventory.receive` when stock is given);
- one audit entry per created resource, like today;
- `authz_golden.json` reviewed and regenerated deliberately;
- tests: success, slug/SKU collision, price ≤ 0, stock without a warehouse, failure rolls back everything;
- Cloudinary stays outside the transaction (upload first, pass the URL; or attach the photo after).
- Optional `POST /inventory/admin/receive` extension to accept `shares` so "receive + divide" is atomic.

---

## 12. Product detail page: chosen layout

| Option | Verdict |
|---|---|
| A. Single long page | Good for edits (everything visible) but too much (placeholders, history). |
| B. Tabs | Rejected: size, price and stock are interdependent; tabs make staff go back and forth (NN/g: staged/hierarchical disclosure fails for interdependent items). |
| C. Step editor | Rejected for editing; also rejected for creation (it is one short form). |
| D. Drawers for everything | Rejected for primary data; good for secondary actions. |
| **E. Hybrid (chosen)** | **One short page with three cards + drawers for rare actions.** |

Sections (top to bottom):
1. **Header:** photo, name, category, status switch (Live/Hidden), `⋯` menu (Duplicate, Archive, ADMIN: Delete).
2. **Sizes, prices and stock** — the main table, one row per size (`Size | Price | In stock | Live`), inline edit, `+ Add size`, stock total line with **+ Add stock**, **Stock count**, **Low-stock alert**.
3. **Details** — photos (multiple, set primary), description, category.
4. **Advanced** (button, opens a drawer): SKU, web address, also show in, per-size alert, reserve part for a size, price history, activity history.
Removed from the page: Merchandising, Reviews (placeholders), standalone Inventory section, always-loaded Activity.

---

## 13. Information architecture

```
Products
├── All products      (tabs: All · Live · Drafts (n) · Low stock (n) · Hidden · Archived)
├── + Add product     (primary button)       + Add many  (secondary)
└── Categories        (existing)
Inventory (operations)
├── By product        (default, existing)
├── Lots & warehouses (advanced, existing "By lot" view)
├── Alerts            (existing)
└── Warehouses setup  (moved out of the main toolbar)
```

Tabs are filters on one list (`status`, plus new `stock_state` and `incomplete` filters), not separate pages. Counts on Drafts and Low stock are the operator's to-do list.

---

## 14. Role-based UX

Current code mapping (`Admin/lib/permissions.ts`; the backend re-checks every call): **ADMIN** has everything; **OPERATIONS** and **HUB_STAFF** have inventory permissions but **no** `products.*`; DELIVERY_PARTNER and SUPPORT see no catalogue.

| Capability / permission | Sees |
|---|---|
| `products.read/create/update` | Products list, Add product, Add many, sizes, descriptions, Duplicate |
| `products.manage_pricing` | Inline price edit, rate-per-kg fill, bulk price, price history (Advanced) |
| `products.manage_media` | Photo upload/remove |
| `products.delete` | Delete in the `⋯` menu only (and recommend Archive first) |
| `inventory.receive` | + Add stock (product page, list, Add form's opening stock) |
| `inventory.adjust / reconcile / transfer` | Stock count, Remove, Reserve part, Transfer (Advanced) |
| `audit.read` | History drawer |
| none of the above | Controls are not rendered (hide, not disabled, except where the hidden control would confuse a colleague) |

**Decision for the client:** today only ADMIN can create products. If warehouse staff should add products, grant OPERATIONS `products.read/create/update/manage_media/manage_pricing` (not delete). This is an access-policy change and must be approved; the UI should follow the permission model either way.

---

## 15. Wireframes

### 15.1 Products list
```
Products                                                     [+ Add many] [+ Add product]
[All 214] [Live 190] [Drafts 6 ●] [Low stock 9 ●] [Hidden 5] [Archived 4]
[ Search name…        ] [Category ▾]                                      [Select ▢]
------------------------------------------------------------------------------------
 ▢ [img] Tomato           Vegetables   ₹20 · ₹35 · ₹60    34 kg   ◯ Live   [+Stock][Price]  ⋯
 ▢ [img] Potato           Vegetables   ₹20 · ₹35 · ₹60    LOW 6 kg ◯ Live  [+Stock][Price]  ⋯
 ▢ [ ! ] Onion  Draft·Incomplete: no price   Vegetables    —        Draft   [Finish]          ⋯
------------------------------------------------------------------------------------
Bulk bar (when rows selected): [Set price ▾] [Hide] [Publish] [Stock count] [Cancel]
Row ⋯ : Open · Duplicate · Archive · (ADMIN) Delete
```
Behaviour: row click opens the product; **+Stock** opens a small popover (amount, unit); **Price** opens inline price edit; Live toggle PATCHes status; stock text shows unit and Low/Out chip from the product alert.

### 15.2 Add product
```
< Products     Add product
 Name *        [ Tomato                         ]   ⚠ "Tomato" already exists — Open it
 Category *    [ Vegetables ▾ ]  recent: (Vegetables) (Fruits) (Dairy)
 Photo         [ drop image / click ]  (optional)
 Sizes *       (250 g ✓) (500 g ✓) (1 kg ✓) (2 kg) (1 dozen) [+ other: ______ ]
 Prices *      250 g  ₹[ 20 ] ₹80/kg      500 g ₹[ 35 ] ₹70/kg      1 kg ₹[ 60 ] ₹60/kg
               ( ) Fill from rate: ₹[ 60 ] per kg  [Fill]
 Opening stock [ 50 ] [kg ▾]   in Main warehouse  [change]
 Description   [                                   ]
 ▸ Advanced    (product codes, web address, also show in, low-stock alert [10 kg], reserve part for a size)
 [ Save & publish ]  [ Save as draft ]
 Saving…  ☑ Product ☑ 250 g ☐ 500 g ✖ failed: <reason>  [Retry remaining steps]
```
Validation: name, category, ≥1 size, price > 0 per chosen size. Stock optional; if empty and "Save & publish", confirm inline text "No stock yet — customers will see Out of stock" (not a blocking dialog). Keyboard: Tab order follows the visual order; Enter on the last field saves.

### 15.3 Product detail
```
< Products
[img] Tomato   Vegetables                [ Live ● | Hidden ]       ⋯ (Duplicate · Archive · Delete*)
-------------------------------------------------------------------------------------------
Sizes, prices and stock                                                        [+ Add size]
 Size     Price (click to edit)    Stock (shared)            Status
 250 g    ₹20   ₹80/kg             ≈ 200 packs               Live ●
 500 g    ₹35   ₹70/kg             ≈ 100 packs               Live ●
 1 kg     ₹60   ₹60/kg             ≈  50 packs               Live ●
 In stock: 50 kg   Low-stock alert: 10 kg [edit]   [+ Add stock] [Stock count] [Remove]
-------------------------------------------------------------------------------------------
Details   Photos [img][img] [+ Add] (set primary / remove)    Description […]    Category […]
-------------------------------------------------------------------------------------------
[ Advanced ▸ ]  → drawer: Product codes · Web address · Also show in · Alert per size ·
                  Reserve part for a size · Price history · History
```
Editing: each cell saves on blur/Enter with "Saved ✓" or an inline error; price shows an Undo toast; Deactivate turns the row grey with a "Hidden" chip.

### 15.4 Inventory (By product, default)
```
Inventory                                   [Low 9] [Out 3]      [ Receive stock ]  Advanced ▾
[ Search ] [Category ▾] [Warehouse ▾]
 ▾ Tomato     Vegetables   34 kg    alert 10 kg   OK
     250 g ≈ 136 packs · 500 g ≈ 68 packs · 1 kg ≈ 34 packs     [+ Add stock] [Count] [Remove]
 ▸ Potato     Vegetables   6 kg     alert 10 kg   LOW
Advanced ▾: Lots & batches · Reservations · Transfers · Damage/waste · Packaging · Warehouses
```
"Receive stock" = pick product, amount, unit; warehouse defaulted; notes and "reserve part for a size" under Advanced.

### 15.5 Bulk product creation (Add many)
```
Add many products           [Download template] [Upload CSV] [Paste from sheet]
 Apply to selected rows: Category [▾]  Size set [250g/500g/1kg ▾]  Rate per kg [__] [Apply]
 ▢ # Product      Category     Sizes             Prices        Stock     Photo   Status
 ▢ 1 Tomato       Vegetables   250g,500g,1kg     20,35,60      50 kg     –       ✓ Ready
 ▢ 2 Potato       Vegetables   500g,1kg,2kg      20,35,60      80 kg     –       ✓ Ready
 ▢ 3 Onion        Vegetables   (preset)          25/kg         100 kg    –       ⚠ Prices missing (1)
 [+ Row]  [Duplicate row]
 Summary: 2 ready · 1 needs fix              [ Create 2 products ]  → per-row results, failures stay in the grid
```
Rules: row validated live; each row created atomically; created rows turn into links; "Publish immediately" toggle at the bottom (default on).

---

## 16. Implementation plan (existing frontend, no rebuild)

Legend: **Backend?** = backend change required. Complexity S/M/L (relative, not hours).

### Phase 1 — highest impact, frontend only (no new API)
| # | Component / page | UI change | API impact | DB | Backend? | Priority | Complexity |
|---|---|---|---|---|---|---|---|
| 1.1 | `products/new/page.tsx` | Size chips + text parser, remove per-row unit dropdown, rate-per-kg fill, remembered category and size set, opening stock + default warehouse, Save & publish / Save as draft, Advanced section (slug/SKU/also-show-in) | uses existing endpoints (`receiveStock` after variants) | none | No | P0 | M |
| 1.2 | Same page | Progress checklist + Resume (skip existing sizes), non-blocking photo, no silent failures | existing | none | No | P0 | M |
| 1.3 | `lib/products.ts` `slugify` | Support non-Latin names (fallback e.g. `product-<timestamp>`), unique-retry on 409 | existing | none | No | P0 | S |
| 1.4 | `products/[id]/page.tsx` | Merge Variants & Pricing and Inventory into one table; inline price edit + Undo toast; remove Merchandising/Reviews; Activity and SKU/slug into an Advanced drawer; one save model; surface swallowed errors | existing | none | No | P0 | M |
| 1.5 | Low-stock alert | Product-level alert in kg/pieces converted to each size's `reserve_level` (via existing `ReserveLevelEditor` logic/endpoint) | existing | none | No | P1 | S |
| 1.6 | `products/page.tsx` | Row actions (+Stock, Price, Live toggle), delete into `⋯`, stock with unit | existing | none | No | P1 | M |
| 1.7 | Duplicate-name warning | Debounced `q` search on the name | existing list endpoint | none | No | P1 | S |
| 1.8 | Duplicate product | Prefilled Add form from an existing product | existing detail endpoint | none | No | P1 | S |
| 1.9 | Status labels | Live/Hidden/Draft/Archived wording | none | none | No | P1 | S |
| 1.10 | `ReceiveStockForm` / dialog | Default warehouse, notes and "share per size" under Advanced | existing | none | No | P1 | S |

### Phase 2 — workflow improvements
| # | Component | UI change | API impact | DB | Backend? | Priority | Complexity |
|---|---|---|---|---|---|---|---|
| 2.1 | Composite create | Add form uses one request | new additive `POST …/products/quick-create` (+ tests, `authz_golden.json`, docs regen) | none | **Yes** | P0 | L |
| 2.2 | Products list tabs | Drafts / Low stock / Incomplete filters and counts | add `stock_state` and `incomplete` query params and counts to the admin list | none (computed) | **Yes** (small) | P1 | M |
| 2.3 | Add many (grid) | Paste/CSV into grid, presets, per-row create using 2.1 | uses 2.1 | none | After 2.1 | P0 | L |
| 2.4 | Bulk price / publish / hide | Select rows, preview, apply | loop over existing endpoints or one bulk endpoint | none | Optional | P2 | M |
| 2.5 | Atomic receive + divide | One call for receive and shares | extend receive payload with `shares` | none | **Yes** | P2 | M |
| 2.6 | Server-side presets | Size sets and last choices per user | small preferences endpoint | optional small table + Alembic revision | **Yes** (optional) | P3 | M |

### Phase 3 — advanced
| # | Component | Change | Backend? | Priority | Complexity |
|---|---|---|---|---|---|
| 3.1 | Server CSV import | Dry-run, error CSV, template | Yes | P3 | L |
| 3.2 | Image bulk matching | Filename-to-product mapping | Yes | P4 | M |
| 3.3 | Scheduled prices UI | valid-from picker in Advanced (backend supports it) | No | P4 | S |
| 3.4 | Inventory page cleanup | Product-first default tab, warehouse setup out of toolbar | No | P3 | S |
| 3.5 | Role changes | Grant OPERATIONS product permissions (client decision) | Yes (permissions + tests) | Decision | S |

### Rules for implementation
- No removal or renaming of fields used by installed mobile apps; new endpoints are additive.
- Every new route gets an explicit auth gate and a reviewed `authz_golden.json`; run `alembic check` only if a model changes; regenerate `API_REFERENCE` after routes change; update `AI_STATUS.md`.
- Tests: backend unit/integration for the composite endpoint (including rollback); there are no frontend tests, so Phase 1 needs a manual script (§8) and, if the client agrees, a small Playwright smoke test.
- UI changes are not covered by tests; verify in a browser per screen and per role.

---

## 17. What each feature is judged against

Every item above answers "does this reduce time, cognitive load, errors, or repeated work?" Things deliberately **not** added to the primary workflow: wizard steps, tabs on the product page, barcode, option matrices, scheduled pricing, reviews/merchandising, reservations, warehouses, batches. They stay available under Advanced or the Inventory module.

## 18. Open questions for the client

1. Should warehouse staff (OPERATIONS/HUB_STAFF) be allowed to create and price products?
2. How many warehouses are in daily use? (If one, the warehouse field disappears entirely.)
3. Which size sets are standard per category? (Seed the presets.)
4. Should "Save & publish" with 0 stock be allowed silently (current behaviour is allowed) or warned?
5. Rounding rule for per-kg price fill (nearest ₹1 or ₹5)?
