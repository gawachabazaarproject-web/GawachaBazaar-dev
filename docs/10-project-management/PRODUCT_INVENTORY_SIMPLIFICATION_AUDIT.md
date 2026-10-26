# Admin Product and Inventory — Final Simplification Audit

> **Status:** Implemented and validated in a browser on 2026-10-26 (uncommitted); validation findings and fixes are KNOWN_ISSUES VAL-1..10. Original status: Proposal. Builds on [`PRODUCT_UX_REDESIGN.md`](PRODUCT_UX_REDESIGN.md), whose Phase 1 is partly implemented (uncommitted, type-checked only). **Date:** 2026-10-26.
> **Evidence:** Admin source (`Admin/app/(admin)/{products,inventory}`, `components/*Stock*`, `AdminShell.tsx`, `lib/permissions.ts`), backend schemas and services (`schemas/admin_inventory.py`, `services/inventory.py`, `catalog.py`, `packaging.py`), `INVENTORY.md`. Nothing was run in a browser; no new research was done beyond the sources in the earlier report.
> **Estimates:** all clicks and seconds below are counted from the screens, not measured. Validate with the acceptance tests in §13.

Rule used throughout: **if the operator does not need the concept to finish the task, it is not on the screen.** Every item is tagged **REMOVE / HIDE / AUTOMATE / COMBINE / KEEP**.

---

## 1. Executive verdict

The system is hard to use because it shows its **database** instead of the **job**:

1. **Stock is per lot** (size + warehouse + batch) but staff think per product ("how many tomatoes?"). Correct, remove and move all start from a lot.
2. **Quantities are in packs** ("200 packs") while staff count in kg.
3. **Too many decisions per task**: warehouse, batch, unit, "divide between sizes", movement type, reason, notes.
4. **Technical words**: lot, batch, reconcile, adjust, reserve, on hand, SKU, slug, variant.
5. **Work is scattered** across Products, Inventory, a lot page and dialogs; the product page cannot tell you whether the product is ready to sell.
6. **Mixed save behaviour** and silent failures (partly fixed in Phase 1).
7. **No role-shaped interface**: product staff do not exist as a role; warehouse staff cannot touch products; admins see everything.

Remaining complexity even in our own Phase 1 (audit of the current proposal):

| Where | Still too complex | Verdict |
|---|---|---|
| Add product | Two buttons (Save & publish / Save as draft) | **COMBINE** into one **Save** + "Make available to customers" checkbox (default on) |
| Add product | "Fill from rate" box always visible | **HIDE** behind a link "Set prices by rate per kg" |
| Add product | Description, Advanced always on screen | **HIDE** Description under "More details" with Advanced |
| Receive stock form | "Divide between sizes", "Unassigned", Notes, pack counts | **HIDE** all under "Advanced"; **AUTOMATE** the size breakdown as a read-only preview |
| Receive stock | Product picker dialog from Inventory | **COMBINE**: Add stock is a button on each product card, no picker |
| Product page | Low-stock alert editor on the main table | **HIDE** (Operations layer, in Inventory) |
| Product page | Four row actions (Hide, Edit, Delete + price) | **COMBINE** Edit/Hide/Delete into a row menu; price stays inline |
| Product page | Pack counts ("100 packs") per size | **REMOVE** from the main table; show kg total, packs only in Receive preview |
| Inventory | Seven metric tiles, two-view toggle, warehouse button | **REMOVE** tiles → count chips; **HIDE** "By lot / warehouse" and warehouse setup (Operations/Advanced) |
| Inventory | Remove/Adjust/Reconcile/Transfer on a lot page | **COMBINE** into four plain actions on the product card |
| Everywhere | SKU, slug, "Also show in", batch codes | **HIDE** (Advanced, admin only) |

---

## 2. Primary users

| User | Role today | Needs | Gets |
|---|---|---|---|
| **A. Product staff** | none (only ADMIN has `products.*`) | add/edit products, prices, publish, see stock | Products screen; stock number and **Add stock** if they hold `inventory.receive` |
| **B. Warehouse staff** | OPERATIONS, HUB_STAFF (inventory permissions only) | receive, correct, remove, move stock | Inventory screen (product-first); no price, no delete, no SKU |
| **C. Administrator** | ADMIN | everything, audit, configuration | Both, plus Advanced layer |

**Decision for the client:** create a **Catalogue staff** role (products.read/create/update/manage_media/manage_pricing, no delete) or grant those to OPERATIONS. The Admin permission copy and `core/permissions.py` change together (small backend change, needs tests).

---

## 3. The 5-minute test

New employee, no training. Counts are from the proposed screens; "interactions" = clicks + typed fields.

| Task | Screens | Interactions | Required fields | Automatic | Hidden | Confirmation | Time |
|---|---|---|---|---|---|---|---|
| 1. Create product (3 sizes, stock) | 1 | ~10 | name, 3 prices, stock amount (category and sizes remembered) | slug, product codes, size labels, unit, warehouse, batch, opening movement, status | SKU, slug, "also show in", description, alerts | none | 60–90 s |
| 2. Add 50 kg | 0 extra (card on Inventory or product) | 3 (Add stock → type 50 → Save) | amount | warehouse, unit (kg), batch, pack split | expiry (optional dropdown), notes, per-size assignment | none; preview "200 × 250 g · 100 × 500 g · 50 × 1 kg" | 10–15 s |
| 3. Correct after count | 0 extra | 3 (Correct stock → type 43 → Save) | counted amount | difference (−7 kg), reason ("Physical count"), movement type | lot, batch | inline note only if change is large (>25% or to zero); no dialog | 15 s |
| 4. Remove 2 kg damaged | 0 extra | 3 (Remove → 2 → Remove) | amount, reason (default "Damaged") | lot choice (oldest first, never below reserved), movement type | lot | none; **Undo** for 10 s | 10–15 s |
| 5. Move to another warehouse | 0 extra | 4–5 (Move → To → amount → Move) | destination, amount | source (default warehouse), lots, two linked movements | lots, batch | none | 20 s |
| 6. Change price | 0 extra | 2–3 (click price → type → Enter) | new price | audit entry, price history row | history | none; **Undo** | 5 s |

"Move stock" appears only when more than one active warehouse exists.

---

## 4. Product creation (improved from your sketch)

Your layout is close to optimal. Changes:

```
ADD PRODUCT
Product name          [ Tomato                ]   (warning if the name already exists)
Category              [ Vegetables ▼ ]            remembered
Photo                 [ Add photo ]               optional, never blocks
Selling sizes         (250 g)(500 g)(1 kg)(2 kg) [+ other]
                      250 g  ₹[ 20 ]   500 g  ₹[ 35 ]   1 kg  ₹[ 60 ]
                      Set prices by rate per kg ▸             (hidden link)
Opening stock         [ 50 ] [ kg ▼ ]   in Main warehouse     (warehouse text only if >1)
☑ Make available to customers
                                      [ Save ]
More details ▸        (description, web address, product codes, also show in)
```

| Item | Decision |
|---|---|
| **Required** | name, category, ≥1 size with a price above 0 |
| **Optional** | photo, opening stock, description |
| **Generated** | slug, product codes, size labels, units for stock, warehouse, batch, the receipt entry, status |
| **Hidden** | slug, product codes, extra categories, description, rate fill |
| **Advanced** | slug/product-code overrides, per-size alerts, assigning stock to one size |
| **Deferred** | stock alert level, expiry, supplier, merchandising |
| **Button** | one **Save**; the checkbox decides Live or Draft (REMOVE the second button) |
| **Publishing without stock** | allowed, with an inline line "No stock yet — customers will see Out of stock" (no dialog) |
| **Publishing without price** | not possible: the price is required |

---

## 5. Product readiness

Computed in the Admin from data it already receives (detail: sizes, prices, stock, images; list: price, stock, image, variant count).

| Check | Rule | Blocks "Ready"? |
|---|---|---|
| Product information | name + category | yes |
| Selling sizes | ≥1 active size | yes |
| Prices | every active size has a current price | yes |
| Stock | available stock > 0 | yes (shows "Needs stock") |
| Photo | has an image | no (shown as a suggestion) |
| Live | status is Live | separate chip |

```
Tomato                                  READY TO SELL
✓ Information ✓ Sizes ✓ Prices ✓ Stock ✓ Photo

Potato                                  2 THINGS NEED ATTENTION
✓ Information ✓ Sizes ✕ Price for 500 g ✕ Stock          [ Fix now ]
```

- **Fix now** jumps to the missing item: opens the price box, or the Add stock box, in place.
- Products list: a **Needs attention (n)** tab. The list can compute an approximation (no price, no stock, no photo); exact per-size price checks need the detail data, so the exact version is a small backend field on the list item.
- A hidden/draft product that is ready shows **Publish**.

---

## 6. Inventory: the default answers "What do we have?"

Product-first, one card per product, no tiles:

```
INVENTORY                                              [ + Receive stock ]
[ Search products… ]      All 214 · Low 9 · Out 3 · Expiring 2 · Needs attention
┌────────────────────────────────────────────────────────────┐
│ Tomato                              50 kg available · 5 kg reserved
│ 250 g · 500 g · 1 kg                 [Add stock] [Correct] [Remove] [Move]*
├────────────────────────────────────────────────────────────┤
│ Potato   LOW 8 kg                    [Add stock]            (alert is actionable)
│ Onion    OUT OF STOCK                [Add stock]
└────────────────────────────────────────────────────────────┘
* Move appears only when there is more than one warehouse.
More ▾ (admin/operations): Stock by warehouse & batch · Movement history · Warehouses · Low-stock levels
```

- **REMOVE** the SKUs / On hand / Reserved / Available tiles. "Reserved" appears once, on the card, as "5 kg reserved for orders".
- **HIDE** "By lot / warehouse" (Layer 2), lot page (Layer 3).
- **COMBINE** alerts into this page: the sidebar badge opens the **Low** chip filter; the separate alerts page remains reachable but is not needed.

---

## 7. Human actions and how they map to the backend

| Staff action | What it does for them | Backend mapping today | Gap |
|---|---|---|---|
| **Receive stock** | add what arrived | `POST /inventory/admin/receive` (find or create lot + `RECEIPT`; auto batch) | none for kg; expiry needs a field (see §10) |
| **Correct stock count** | "I counted 43 kg" | `POST /inventory/admin/lots/{id}/reconcile` per lot, takes a counted number and computes the difference | works per lot only; product-level needs a **small backend change** |
| **Remove damaged / wasted stock** | take stock out with a reason | `POST /inventory/admin/lots/{id}/remove` (never below reserved) | per lot only; product-level removal across lots (oldest first) is a **small backend change** |
| **Move stock** | to another warehouse | `POST /inventory/admin/transfer` per source lot, quantity in packs | per lot; product-level move is a **small backend change** |
| **Repack stock** | — | packaging operations API exists; **no Admin screen exists** | **REMOVE from the normal UI.** Sizes of one product already share one pool (1 kg received sells as 4 × 250 g), so repacking a product into its own sizes needs no action. Keep packaging in the API for admins; confirm with the client whether any real repack case (e.g. one product into another) exists before building a screen. |
| Dispatch / receipt entries | — | system movements | never shown as actions |

Rule for the product-level correct/remove/move: the backend does it in **one transaction**, taking lots in id order (the existing lock order), oldest stock first, never below the reserved amount, and returns the lots touched so the Admin can offer Undo. Doing this in the Admin by looping over lots would not be atomic, so it is not recommended.

---

## 8. Smart stock entry

```
RECEIVE STOCK — Tomato                     
Amount        [ 50 ] [ kg ▼ ]                     warehouse: Main warehouse (automatic)
Customers can buy:  250 g → 200 packs · 500 g → 100 packs · 1 kg → 50 packs
Stock is shared by all sizes.
More ▸ expiry · notes · reserve part for one size
                              [ Add stock ]
```

- The preview uses the same conversion the server applies (`amountToPacks`, rounded down); the server stays the authority.
- Manual assignment to a size ("reserve part for one size") stays, under **More**, for operations and admin.

---

## 9. Warehouse handling

| Case | Behaviour | Needs backend? |
|---|---|---|
| One active warehouse | auto-selected, shown as text only | no (done in Phase 1) |
| Several | dropdown, last used preselected | no (done in Phase 1) |
| User assigned to one warehouse | auto-selected, selector hidden | **yes** (architectural): the backend has no user-to-warehouse link today; needs a column/table, enforcement on every inventory call, and migrations. Not recommended until the client confirms the need. |
| None | message "Add a warehouse first" with a link (admin) | no (done) |

---

## 10. Batch and expiry

- **Normal receipt:** batch is auto-generated and invisible. Today the auto-batch has **no expiry**, so normal receipts never produce expiry alerts.
- Add one optional control in **More**: **Expiry: No expiry ▾ / in 2 / 3 / 5 / 7 days / pick a date**, remembered per category. Fresh produce is perishable, so the client should decide the default per category.
- **Backend (small):** let `POST /inventory/admin/receive` accept `expiry_date` (and optionally `supplier_id`, `harvest_date`) when it creates the auto batch.
- **Advanced (admin/operations):** batch number, supplier, harvest date, expiry — in the lot view and on the receive form's Advanced section.
- **Never show** `ADMIN-XXXX` codes outside the Advanced layer.

---

## 11. Stock correction

```
CORRECT STOCK — Tomato
System says 50 kg
You counted    [ 43 ] kg
Difference     −7 kg          (calculated, not typed)
Reason         [ Physical count ▾ ]  (default)
                         [ Save correction ]
```

- The counted number goes to the backend, which computes the movement (the existing reconcile already does this per lot).
- Safeguard: if the change is large (>25% or to zero), show a one-line inline note ("This removes 7 kg — check your count"), no extra dialog.
- It cannot go below reserved stock (the backend refuses); the message explains: "5 kg is reserved for orders; the lowest you can set is 5 kg."

## 12. Damage and waste

```
REMOVE STOCK — Tomato        Available: 45 kg
How much?   [ 2 ] kg                           
Why?        (•) Damaged  ( ) Spoiled  ( ) Wasted  ( ) Other [ note ]
                                   [ Remove stock ]     → toast: "Removed 2 kg · Undo"
```

Reasons map to the existing reason list; the movement type is chosen by the backend. **Undo** posts a compensating adjustment (the ledger stays complete). The old "Remove all" is available as a link "Remove all available".

## 13a. Move stock

```
MOVE STOCK — Tomato
From   [ Main warehouse ▾ ] (default)     To   [ Warehouse 2 ▾ ]
Amount [ 10 ] kg
                                   [ Move stock ]
```

Both movements are created by one backend call. Hidden entirely when there is a single warehouse.

---

## 14. Alerts are actions

| Alert | Card shows | Actions |
|---|---|---|
| Low stock | "8 kg left — low" | **Add stock** |
| Out of stock | "Out of stock" | **Add stock** · **Hide product** |
| Expiring (batch within 7 days) | "2 kg expires in 4 days" | **Remove stock** · **View stock** |
| Expired | "3 kg expired" | **Remove stock** (reason preset "Expired") |
| Price missing | "No price for 500 g" | **Set price** (inline) |

---

## 15. Three layers

| Layer | Audience | Contains |
|---|---|---|
| **1 Simple** | everyone | product, price, stock, availability, readiness, Add/Correct/Remove stock, Move (if >1 warehouse), publish/hide |
| **2 Operations** | warehouse/ops | stock by warehouse, batches and expiry, low-stock levels, movement history, reservations list, per-size assignment, warehouses |
| **3 Advanced** | admin | SKU, slug, extra categories, price history, audit, packaging operations, permissions, delete |

Classification of current items:

| Item | Layer |
|---|---|
| Name, category, photo, sizes, prices, opening stock, publish | 1 |
| Add / Correct / Remove stock, kg totals, readiness, alerts | 1 |
| Move stock | 1 (shown only if >1 warehouse) |
| Low-stock level, expiry, notes, size assignment, warehouse list | 2 |
| Lots, batches, movement history, reservations, orders that reserve a lot | 2 |
| SKU, slug, also-show-in, description override | 3 ("More details") |
| Price history, audit/activity, delete product/size, packaging, warehouse delete, packing point | 3 |

---

## 16. Terminology

| Current | Use | Hide? | Reason |
|---|---|---|---|
| Variant | **Size** | no | what customers choose |
| SKU | Product code | yes (Advanced) | internal |
| Slug | Web address | yes (Advanced) | internal |
| Lot | (none) / "stock in warehouse" | yes (Layer 2: "Stock batch") | database concept |
| Batch | **Delivery** (Layer 2) | yes in Layer 1 | needed only for expiry/supplier |
| Stock movement | History | Layer 2 | ledger |
| Receive stock / Receipt | **Add stock** | action kept | plain |
| Reconcile / Adjust | **Correct stock count** | actions merged | one human intent |
| Remove stock / Damage / Waste | **Remove stock** (reason: Damaged, Spoiled, Wasted, Other) | no | plain |
| Transfer | **Move stock** | no | plain |
| Reserve (stock reserved) | **Reserved for orders** | keep, short | customers have bought it |
| Reserve level / reserve | **Low-stock level** | Layer 2 | purpose is clear |
| On hand | **In stock** | no | plain |
| Available | **Available to customers** (card: "available") | keep | differs from in stock when reserved; do **not** merge, else staff cannot explain why shop shows less |
| Dispatch | (system) | yes | happens at delivery |
| INACTIVE | **Hidden** | no | |
| ACTIVE | **Live** | no | |
| Unassigned stock | **Shared by all sizes** | Layer 2 | |
| Packing point | **Packing warehouse** | Layer 3 | |

Exception kept as-is: **Available** and **Reserved** must stay distinct words; collapsing them would hide why a product shows out of stock while "50 kg is in the warehouse".

---

## 17. Navigation (final)

Sidebar, current → final:

```
Dashboard
Sell        Orders · Delivery · Payments · Customers
Catalogue   Products · Categories · Inventory           ← keep
Marketing   Promotions · Home slides · Ads
Administration  Staff · Settings
(Coming soon items hidden from non-admins)
```

**One recommendation:** keep **Products** and **Inventory** as two sidebar entries, because product staff and warehouse staff are different people; but make them **two doors into the same cards**:

- Products opens into a product list; each product's page has the stock number and **Add stock / Correct / Remove** as small dialogs (no navigation to Inventory).
- Inventory opens into the product-level stock cards (default), not lots.
- Lot detail is secondary (More ▾), reached from "Stock by warehouse & batch".
- Alerts live inside Inventory as the **Low / Out / Expiring** chips; the sidebar badge deep-links to **Low**.
- Product editing stays one page.
- Remove "Coming soon" items from users who cannot act on them.

---

## 18. No page hopping

| Task | Where it happens now | Final |
|---|---|---|
| Change price | inline on the product page and list | inline everywhere (list: small popover) |
| Add stock | dialog from card, list row, product page | same dialog everywhere |
| Hide / Publish | list row, product page | inline toggle |
| Edit a size | row menu | small dialog |
| Correct / Remove / Move | lot page | dialogs on the product card (no lot page) |
| See why stock is lower | lot page → Related orders | "5 kg reserved for orders" expands to the orders (Layer 2) |

The loop Product → Inventory → Product disappears: both screens open the same small dialogs.

---

## 19. Preventing mistakes

| Dangerous action | Safeguard | Confirmation dialog? |
|---|---|---|
| Delete product | row menu, admin only; server blocks with history; message recommends Archive | yes (already) |
| Delete size | only shown if allowed; otherwise "Hide" | yes (existing) |
| Remove too much stock | cannot exceed available; inline "max 45 kg"; Undo | no |
| Large correction | inline note when change >25% or to zero | no |
| Publish without price | impossible (price required) | no |
| Publish without stock | inline notice, readiness shows "Needs stock" | no |
| Change size with order history | amount/unit edit warned: "Past orders keep the old size name"; prefer Hide + new size | inline note |
| Change a price | Undo for the last change; history kept | no |
| Move stock | cannot exceed available; reserved stock stays; preview "Main 40 → 30, Warehouse 2 0 → 10" | no |
| Duplicate product name | warning with link | no |
| Leaving a form with unsaved changes | browser warning only on forms with a Save button | existing |

---

## 20. Speed features

| Feature | Verdict |
|---|---|
| Duplicate product | **MVP** (done in Phase 1) |
| Recently used category, sizes, warehouse | **MVP** (done in Phase 1) |
| Inline price editing with Undo | **MVP** (done on the product page; add to list in Phase 2) |
| Size presets per category | **Phase 2** |
| Keyboard: Enter saves, Tab order, `/` focuses search | **MVP** (cheap) |
| Bulk grid with paste from a spreadsheet | **Phase 2** |
| CSV import with preview | **Phase 2** (after the composite create endpoint) |
| Bulk price update (set, +%, +₹ with preview) | **Phase 2** |
| Bulk stock count | **Phase 2** (set totals, not deltas) |
| Product templates | **Not needed** (size presets and duplicate cover it) |
| Barcodes, option matrices, image zip import | **Not needed** |

---

## 21. Bulk import

```
IMPORT PRODUCTS      [ Download template ]  [ Choose file ]  or  paste from Excel
Preview — 100 rows
 ✓ 94 ready     ⚠ 4 missing prices     ✕ 2 unknown category
 Row  Product   Category     Sizes           Prices      Stock   Problem
 12   Onion     Vegetables   250g,500g,1kg   20,35       50 kg   ⚠ price missing for 1 kg
 31   Mango     Fruitz       …                                   ✕ no such category  [ Choose ▾ ]
 [ Fix 6 issues ]            [ Import 94 ready products ]
```

- Errors are found **before** any save, row by row, in an editable grid (fix in place).
- Each product is created in its own transaction; one bad row never blocks the others; a result list shows created / failed with the reason and a "Download failed rows" file.
- Needs the **composite create endpoint** (small backend) so each row is atomic; without it a bulk import would leave half-created drafts.

---

## 22. Backend vs frontend

| Change | Type |
|---|---|
| One-save Add product with remembered choices, readiness checks, list tabs, inline edits, dialogs, terminology, hiding fields, default warehouse | **UX-only** (done or doable now) |
| Product-level Correct / Remove / Move (atomic, oldest first, respects reserved, returns lots touched for Undo) | **Small backend change** (new routes, tests, `authz_golden.json`) |
| Composite create product (+ sizes, prices, optional stock) in one transaction | **Small backend change** |
| Receive accepts `expiry_date` (+ optional supplier, harvest date) | **Small backend change** |
| Readiness and "Low / Out / Expiring" counts and filters on the list/cards | **Small backend change** (computed, no migration) |
| Bulk validate / import endpoints | **Small backend change** |
| New "Catalogue staff" role or permissions for OPERATIONS | **Small backend change** + client decision |
| Per-user warehouse access | **Architectural** (new table, enforcement everywhere) — only if the client needs it |
| Category default shelf life | **Architectural-light** (one column + Alembic revision) — only if the client wants automatic expiry |
| Anything touching reservations, FIFO, lock order, price history, audit | **Do not change** |

---

## 23. Business rules preserved

Status model, sellable sizes, per-size prices and history, lots, shared pool, reservations and FIFO, movements as the only way to change quantity, warehouses, batch/expiry, audit entries, permissions checked by the backend, history blocking deletes, inventory constraints (`reserved ≤ quantity`). New product-level operations call the existing inventory service methods (no commits inside, lot locks in id order); nothing writes quantities directly.

---

## 24. Final deliverable

### 2. Top 20 UX problems (ranked)

1. Stock actions are per lot, not per product (correct/remove/move).
2. Quantities in packs, not kg.
3. Stock is separate from product creation; products go live with no stock.
4. No readiness view; staff must remember what a product needs.
5. Receive form asks warehouse, divide, unassigned, notes.
6. Two views and seven tiles on Inventory; the default is not "What do we have?".
7. Alerts without actions.
8. Four stock operations with technical names (adjust, reconcile, remove, transfer).
9. Mixed save models and (partly fixed) silent failures.
10. Batch/expiry hidden: normal receipts never get an expiry, so expiry alerts do not work.
11. Product page splits one size across two sections (fixed in Phase 1).
12. SKU/slug/"also show in" on the main form (hidden in Phase 1).
13. Two publish buttons; draft/live semantics unclear.
14. Roles do not match jobs; product staff cannot exist.
15. Delete beside normal actions.
16. Reserve level in packs, default 10 packs, inconsistent across sizes.
17. Navigation hops Product ↔ Inventory ↔ Lot.
18. "Coming soon" entries and placeholders add noise.
19. No duplicate/bulk workflow.
20. Jargon (Variant, SKU, Reconcile, Reserve, On hand).

### 3. Final information architecture
See §17.

### 4. Product workflow: Add Product → Price → Stock → Publish
One screen (§4). Name → category → sizes/prices → stock → Save. Readiness card appears on the product page afterwards.

### 5. Inventory workflow
Receive, Correct, Remove, Move as dialogs from the card (§§8, 11–13a). Repack: not in the UI (§7).

### 6. Final Product page

```
< Products
[photo] Tomato · Vegetables              [ Live ● | Hidden ]        ⋯ (Duplicate · Archive · Delete*)
READY TO SELL  ✓ Info ✓ Sizes ✓ Prices ✓ Stock ✓ Photo           (or: 2 things need attention [Fix now])
Sizes, prices and stock                                              [ + Add size ]
  250 g   ₹20  [click]      In stock: 50 kg (shared)     [ Add stock ] [ Correct ] [ Remove ]
  500 g   ₹35  [click]                                                    ⋯ per size (Edit · Hide · Delete*)
  1 kg    ₹60  [click]
Details     photos · description · category · also show in
More ▸     web address · product codes · low-stock level · price history · history     (admin)
```

Stock totals are in kg; per-size pack counts are not shown here.

### 7. Final Inventory page
See §6; plus **Stock by warehouse & batch** (Layer 2) with lot rows and the lot page.

### 8. Role interfaces

| | Product staff | Warehouse staff | Admin |
|---|---|---|---|
| Sidebar | Products, Categories (read) | Inventory | all |
| Product page | full, readiness, price, publish | read-only if allowed; no price | full + More |
| Stock actions | Add stock if `inventory.receive` | Add, Correct, Remove, Move (by permission) | all |
| Hidden from them | delete, history, SKU, lots | prices, SKU, delete | nothing |
| Advanced | no | warehouses, batches, low-stock levels | yes |

### 10. Before vs After

| Metric | Current (before Phase 1) | After Phase 1 (now) | Final |
|---|---|---|---|
| Add product + stock + publish | 2 screens, ~28–32 interactions, ~11 requests | 1 screen, ~10–13 interactions, ~11 requests | 1 screen, ~10 interactions, 1 request |
| Add 50 kg | picker + warehouse + unit + divide (~8) | ~5 | 3 |
| Correct stock | lot page → Reconcile dialog, computing packs (~7) | same | 3, no arithmetic |
| Remove 2 kg | lot row → dialog (~5, packs) | same | 3, kg, Undo |
| Move stock | lot page → dialog (~6, packs) | same | 4–5, kg, hidden if one warehouse |
| Technical concepts shown | SKU, slug, lot, batch, packs, reserve, movement types | fewer | none in Layer 1 |
| Decisions per stock task | warehouse, unit, divide, notes, reason, type | warehouse default | amount (+ reason) |
| Error opportunities | wrong unit/pack count, partial creation, forgotten stock/publish | retry, resume | readiness card, atomic create, Undo |
| Time (estimate) | 4–7 min product; 1–2 min per stock task | 1–3 min | ≤90 s product; ≤20 s per stock task |

### 11. Wireframes
Included above: Add product (§4), Inventory (§6), Receive (§8), Correct (§11), Remove (§12), Move (§13a), Bulk import (§21), Product details (§24.6). **Products list:**

```
Products                                  [ Import ]  [ + Add product ]
[ All ] [ Live ] [ Needs attention 6 ● ] [ Drafts ] [ Hidden ] [ Archived ]     [ Search ]
 [img] Tomato   Vegetables   ₹20 · ₹35 · ₹60    50 kg    READY      [Add stock][Price] ⋯
 [ ! ] Potato   Vegetables   missing price      0 kg     2 things  [ Fix now ]
```

### 12. Implementation plan (ordered)

| # | Item | Frontend | Backend / DB / API | Priority | Complexity |
|---|---|---|---|---|---|
| 1 | One **Save** + checkbox on Add product; hide description/rate fill | Add product page | none | P0 | S |
| 2 | Readiness card and "Needs attention" tab | product page + list | none (approximate list); exact flag later | P0 | M |
| 3 | Receive dialog simplification: preview of pack split, hide divide/unassigned/notes under More; Add stock from each card | `ReceiveStockForm`, Inventory cards | none | P0 | M |
| 4 | Inventory default page: chips with counts, cards with actions; move "By lot" and warehouse setup into More | `inventory/page.tsx`, `ProductStockView` | none (counts from existing dashboard/alerts) | P0 | M |
| 5 | Plain terminology across screens | all | none | P0 | S |
| 6 | Product page: row menu, hide pack counts, move alert editor to Inventory | product page | none | P1 | S |
| 7 | Product-level **Correct / Remove / Move** (atomic) + Undo | new dialogs on cards | new routes `…/admin/products/{id}/correct|remove|move`; reuse inventory service; tests; `authz_golden.json`; docs regen | P0 | L |
| 8 | **Composite create product** | Add product | new route `…/products/quick-create`; no DB change | P0 | L |
| 9 | Receive with **expiry** (and optional supplier) | More ▸ dropdown | extend receive schema; no DB change | P1 | S |
| 10 | Actionable alerts on cards (Add / Remove / Hide) | Inventory | none | P1 | S |
| 11 | Roles: Catalogue staff or OPERATIONS product permissions | Admin permission copy | `core/permissions.py`, role seed/migration if a new role, tests | P1 | M (decision first) |
| 12 | Bulk grid + CSV import with preview | new page | validate + create-many routes | P2 | L |
| 13 | Bulk price / stock count | list/cards | bulk routes (optional) | P2 | M |
| 14 | Per-category shelf life | Receive | one column + Alembic revision | P3 | M |
| 15 | Per-user warehouse access | all inventory | table + enforcement | P4 | XL (only if requested) |

### 13. Acceptance criteria

1. A new employee adds a standard 3-size product with stock and publishes it, without documentation, in ≤90 s median and ≤12 interactions (timed with 3 people × 5 products).
2. A standard stock receipt needs only the amount (and optional expiry); no lot, batch, warehouse (single-warehouse shops), unit conversion or pack arithmetic is shown or required.
3. A stock correction needs only the counted amount; the difference is shown, never typed.
4. Remove and Correct complete in ≤3 interactions and offer Undo; the ledger still records both.
5. The six tasks in §3 are completed without leaving the product or inventory card they start from (Move excepted for the destination choice).
6. Readiness shows exactly which items are missing and "Fix now" opens the right control.
7. Lots, batches, history, SKU, slug, packaging and audit remain available to authorized users in Layer 2/3.
8. No regression: backend tests for catalog, inventory, reservations and concurrency still pass; new routes have tests (including rollback on failure, reserved stock never removed, oldest-first removal) and a reviewed `authz_golden.json`.
9. Role check: a warehouse user cannot see price or delete controls; a product user without `inventory.receive` cannot see Add stock; the backend still returns 403 for direct calls.
10. Zero partial products from Add product after the composite endpoint ships.

---

## 25. Open questions for the client

1. Should product staff be a separate role, or should OPERATIONS get product permissions?
2. How many warehouses are in daily use? Do users need to be limited to one?
3. Is "repack" a real task (which products, why)? Today it has no Admin screen.
4. Default shelf life per category, so expiry alerts work without anyone typing a date?
5. Is it acceptable that "Correct stock count" reduces the **oldest** lot first and adds to the **newest**?
