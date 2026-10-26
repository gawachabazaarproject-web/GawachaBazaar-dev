import assert from "node:assert/strict";
import { test } from "node:test";
import { checkListReadiness, checkReadiness, fixQuery } from "../lib/readiness.ts";

const base = { name: "Tomato", hasCategory: true, imageCount: 1, hasStock: true };

test("a product with sizes, prices and stock is ready to sell", () => {
  const r = checkReadiness({ ...base, variants: [{ id: 1, label: "1 kg", status: "ACTIVE", hasPrice: true }] });
  assert.equal(r.ready, true);
  assert.deepEqual(r.problems, []);
});

test("a missing price names the size and points at it", () => {
  const r = checkReadiness({
    ...base,
    variants: [
      { id: 1, label: "500 g", status: "ACTIVE", hasPrice: true },
      { id: 2, label: "1 kg", status: "ACTIVE", hasPrice: false },
    ],
  });
  assert.equal(r.ready, false);
  assert.deepEqual(r.problems.map((p) => p.text), ["Price missing for 1 kg"]);
  assert.equal(fixQuery(r.problems[0].fix), "price=2");
});

test("hidden sizes do not need a price, and no sizes means not ready", () => {
  const hidden = checkReadiness({ ...base, variants: [{ id: 1, label: "1 kg", status: "INACTIVE", hasPrice: false }] });
  assert.deepEqual(hidden.problems.map((p) => p.key), ["sizes"]);
  const none = checkReadiness({ ...base, variants: [] });
  assert.equal(none.ready, false);
});

test("no stock needs attention but a missing photo does not", () => {
  const r = checkReadiness({ ...base, imageCount: 0, hasStock: false, variants: [{ id: 1, label: "1 kg", status: "ACTIVE", hasPrice: true }] });
  assert.deepEqual(r.problems.map((p) => p.key), ["stock"]);
  assert.equal(r.checks.find((c) => c.key === "photo").advisory, true);
  const photoOnly = checkReadiness({ ...base, imageCount: 0, variants: [{ id: 1, label: "1 kg", status: "ACTIVE", hasPrice: true }] });
  assert.equal(photoOnly.ready, true);
});

test("list rows use the counts they carry", () => {
  const row = { name: "Potato", primary_image_url: null, active_variant_count: 3, priced_variant_count: 2, total_available_stock: "0" };
  const r = checkListReadiness(row);
  assert.equal(r.ready, false);
  assert.deepEqual(r.problems.map((p) => p.key), ["prices", "stock"]);
  assert.equal(checkListReadiness({ ...row, priced_variant_count: 3, total_available_stock: "12" }).ready, true);
});

test("with no size yet, prices wait instead of counting as a second problem", () => {
  const r = checkReadiness({ ...base, variants: [] });
  const prices = r.checks.find((c) => c.key === "prices");
  assert.equal(prices.waiting, true);
  assert.deepEqual(r.problems.map((p) => p.key), ["sizes"]);
});
