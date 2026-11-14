import assert from "node:assert/strict";
import { test } from "node:test";

import { flagLegendHtml } from "../js/flags_legend.js";
import { wiseSources } from "../js/flipbook.js";

test("wise.json sources are read from the spherex-blink-wise/1 shape", () => {
  const xy = [[1, 2], [1.1, 2.1]];
  assert.equal(wiseSources({ sources: [{ source_name: "J1", xy }] })[0].source_name, "J1");
  assert.deepEqual(wiseSources(null), []);
});

test("flag legend lists counts and marks SOURCE as a label", () => {
  const html = flagLegendHtml({ SOURCE: 120, HOT: 3 });
  assert.match(html, /SOURCE/);
  assert.match(html, /label, not a defect/);
  assert.match(html, /120 px/);
  assert.match(html, /HOT/);
  assert.equal(flagLegendHtml({}), "");
});