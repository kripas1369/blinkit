import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { pickCompositeFrames } from "../js/composite.js";

describe("pickCompositeFrames", () => {
  it("picks first/middle/last for three clean visits", () => {
    const frames = [
      { png: "epoch0.png", pct_no_value: 0.2 },
      { png: "epoch1.png", pct_no_value: 0.3 },
      { png: "epoch2.png", pct_no_value: 0.1 },
    ];
    const pick = pickCompositeFrames(frames);
    assert.equal(pick.first.png, "epoch0.png");
    assert.equal(pick.middle.png, "epoch1.png");
    assert.equal(pick.last.png, "epoch2.png");
    assert.equal(pick.twoEpoch, false);
  });

  it("uses two-epoch mode when only two usable visits", () => {
    const frames = [
      { png: "epoch0.png", pct_no_value: 1 },
      { png: "epoch1.png", pct_no_value: 2 },
    ];
    const pick = pickCompositeFrames(frames);
    assert.equal(pick.twoEpoch, true);
    assert.equal(pick.first.png, "epoch0.png");
    assert.equal(pick.last.png, "epoch1.png");
  });

  it("skips visits with pct_no_value over 50", () => {
    const frames = [
      { png: "epoch0.png", pct_no_value: 1 },
      { png: "bad.png", pct_no_value: 80 },
      { png: "epoch2.png", pct_no_value: 2 },
    ];
    const pick = pickCompositeFrames(frames);
    assert.equal(pick.twoEpoch, true);
    assert.equal(pick.first.png, "epoch0.png");
    assert.equal(pick.last.png, "epoch2.png");
  });

  it("returns null with fewer than two frames", () => {
    assert.equal(pickCompositeFrames([{ png: "only.png" }]), null);
  });
});
