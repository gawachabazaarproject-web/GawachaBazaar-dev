import assert from "node:assert/strict";
import { test } from "node:test";
import { parseSize, priceFromRate, slugify, statusLabel } from "../lib/product-form.ts";

test("sizes can be typed the way people write them", () => {
  assert.deepEqual(parseSize("250g"), { quantity: "250", unit: "G" });
  assert.deepEqual(parseSize("1.5 Kg"), { quantity: "1.5", unit: "KG" });
  assert.deepEqual(parseSize("12 pcs"), { quantity: "12", unit: "UNIT" });
  assert.deepEqual(parseSize("1 dozen"), { quantity: "1", unit: "DOZEN" });
  assert.equal(parseSize("dozen"), null);
  assert.equal(parseSize("abc"), null);
  assert.equal(parseSize("0 kg"), null);
});

test("a rate per kg fills pack prices, rounded to the rupee", () => {
  assert.equal(priceFromRate(60, "250", "G"), "15");
  assert.equal(priceFromRate(60, "500", "G"), "30");
  assert.equal(priceFromRate(60, "1", "KG"), "60");
  assert.equal(priceFromRate(5, "1", "DOZEN"), "60");
  assert.equal(priceFromRate(0, "1", "KG"), "");
});

test("names with no Latin letters still get a web address", () => {
  assert.equal(slugify("Fresh Tomatoes"), "fresh-tomatoes");
  assert.match(slugify("टोमॅटो"), /^product-/);
});

test("statuses are shown in staff words", () => {
  assert.equal(statusLabel("ACTIVE"), "Live");
  assert.equal(statusLabel("INACTIVE"), "Hidden");
});
