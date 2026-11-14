import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { matchCatalog } from "../js/catalog.js";

const catalog = JSON.parse(
  readFileSync(new URL("../data/catalog.json", import.meta.url))
);

test("catalog has 50 suggested objects including the 5 official targets", () => {
  assert.equal(catalog.length, 50);
  assert.equal(catalog.filter((e) => e.official).length, 5);
});

test("empty query shows official targets first in suggestions", () => {
  const hits = matchCatalog(catalog, "", 8);
  assert.equal(hits.length, 5);
  assert.ok(hits.every((e) => e.official));
  assert.ok(hits.some((e) => e.label.includes("Barnard")));
});

test("typing matches name, alias and category", () => {
  assert.equal(matchCatalog(catalog, "m42", 3)[0].label, "Orion Nebula");
  assert.equal(matchCatalog(catalog, "mira", 3)[0].label, "Mira");
  assert.equal(matchCatalog(catalog, "brown dwarf", 5).length >= 3, true);
  assert.equal(matchCatalog(catalog, "0855", 3)[0].label, "WISE 0855");
});