import assert from "node:assert/strict";
import { test } from "node:test";
import { convertAmount, expiryPhrase, InventoryApiError, plain, stockErrorMessage } from "../lib/inventory.ts";

test("expiry is worded the way staff say it", () => {
  assert.equal(expiryPhrase(0), "Expires today");
  assert.equal(expiryPhrase(1), "Expires tomorrow");
  assert.equal(expiryPhrase(3), "Expires in 3 days");
  assert.equal(expiryPhrase(-1), "Expired yesterday");
  assert.equal(expiryPhrase(-4), "Expired 4 days ago");
});

test("every failure says what happened and whether stock changed", () => {
  const refused = stockErrorMessage(new InventoryApiError(422, "Only 12 kg is available to remove right now."), "remove stock");
  assert.match(refused, /Couldn't remove stock\./);
  assert.match(refused, /Only 12 kg/);
  assert.match(refused, /Your stock was not changed\./);

  assert.match(stockErrorMessage(new InventoryApiError(500, "boom"), "add stock"), /server had a problem.*not changed/);
  assert.match(stockErrorMessage(new TypeError("Failed to fetch"), "add stock"), /connection failed.*not changed/);
  assert.match(stockErrorMessage(new InventoryApiError(403, "no"), "move stock"), /don't have permission to move stock/);
  assert.doesNotMatch(stockErrorMessage(new Error("x"), "add stock"), /Something went wrong/);
});

test("units convert within a family and numbers print without trailing zeros", () => {
  assert.equal(convertAmount(2, "KG", "G", "MASS"), 2000);
  assert.equal(convertAmount(500, "G", "KG", "MASS"), 0.5);
  assert.equal(plain("50.000"), "50");
  assert.equal(plain(2.5), "2.5");
});
