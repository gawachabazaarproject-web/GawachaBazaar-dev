// Plain-node checks for src/theme/textStyle.ts (the mobile app has no test runner).
//   cd mobile && node scripts/check-text-style.mjs
import assert from "node:assert/strict";
import { fixTextStyle } from "../src/theme/textStyle.ts";

const A = { android: true };
const J = (w) => `PlusJakartaSans_${w}`;

// 1. stacked bold: weight moves into the family file and fontWeight is dropped
let r = fixTextStyle({ fontFamily: J("500Medium"), fontWeight: "600", fontSize: 14, lineHeight: 21 }, A);
assert.equal(r.fontFamily, "PlusJakartaSans_600SemiBold"); assert.equal(r.fontWeight, undefined);
r = fixTextStyle({ fontFamily: J("400Regular"), fontWeight: "800" }, A);
assert.equal(r.fontFamily, "PlusJakartaSans_800ExtraBold");
r = fixTextStyle({ fontFamily: J("600SemiBold"), fontWeight: "bold" }, A);
assert.equal(r.fontFamily, "PlusJakartaSans_700Bold");
r = fixTextStyle({ fontFamily: J("400Regular"), fontWeight: "500" }, A);
assert.equal(r.fontFamily, "PlusJakartaSans_500Medium");
// family with fewer weights: nearest, heavier on a tie (Lora has 600/700 only)
r = fixTextStyle({ fontFamily: "Lora_700Bold", fontWeight: "800" }, A);
assert.equal(r.fontFamily, "Lora_700Bold");
r = fixTextStyle({ fontFamily: "Lora_600SemiBold", fontWeight: "650" }, A);
assert.equal(r.fontFamily, "Lora_700Bold");
// italic / script faces: just drop fontWeight, keep the face
r = fixTextStyle({ fontFamily: "InstrumentSerif_400Regular_Italic", fontWeight: "700" }, A);
assert.equal(r.fontFamily, "InstrumentSerif_400Regular_Italic"); assert.equal(r.fontWeight, undefined);
// system font (no custom family) keeps its fontWeight - Android handles that natively
r = fixTextStyle({ fontWeight: "700", fontSize: 14 }, A);
assert.equal(r.fontWeight, "700");
// no fontWeight -> family untouched
r = fixTextStyle({ fontFamily: J("700Bold"), fontSize: 14, lineHeight: 21 }, A);
assert.equal(r.fontFamily, "PlusJakartaSans_700Bold");

// 2. clipping: only ever RAISE a too-small lineHeight
r = fixTextStyle({ fontFamily: "Baloo2_600SemiBold", fontSize: 17, lineHeight: 23 }, A);
assert.equal(r.lineHeight, 26); // ceil(17 * 1.5)
r = fixTextStyle({ fontFamily: "Baloo2_600SemiBold", fontSize: 17, lineHeight: 30 }, A);
assert.equal(r.lineHeight, 30); // already roomy: untouched
r = fixTextStyle({ fontFamily: "BodoniModa_700Bold", fontSize: 50, lineHeight: 52 }, A);
assert.equal(r.lineHeight, 55); // ceil(50 * 1.1)
r = fixTextStyle({ fontFamily: "BodoniModa_700Bold", fontSize: 34, lineHeight: 39 }, A);
assert.equal(r.lineHeight, 39); // 1.15x already fine
r = fixTextStyle({ fontFamily: J("400Regular"), fontSize: 14, lineHeight: 21 }, A);
assert.equal(r.lineHeight, 21);

// 3. includeFontPadding is Android-only
assert.equal(fixTextStyle({ fontSize: 14 }, { android: true }).includeFontPadding, false);
assert.equal("includeFontPadding" in fixTextStyle({ fontSize: 14 }, { android: false }), false);

// pure: input object is not mutated
const input = { fontFamily: J("400Regular"), fontWeight: "700" };
fixTextStyle(input, A);
assert.deepEqual(input, { fontFamily: J("400Regular"), fontWeight: "700" });

// 4. small-screen scale: identity for >=360dp, proportional below, floored at 0.85
import { smallScreenScale, scaled } from "../src/utils/responsive.ts";
assert.equal(smallScreenScale(360), 1);
assert.equal(smallScreenScale(411), 1);
assert.equal(smallScreenScale(393), 1);
assert.ok(Math.abs(smallScreenScale(320) - 320 / 360) < 1e-9);
assert.equal(smallScreenScale(200), 0.85);
assert.equal(smallScreenScale(0), 1);
assert.equal(smallScreenScale(NaN), 1);
assert.equal(scaled(165, 1), 165);
assert.equal(scaled(165, smallScreenScale(320)), 147);

console.log("text-style + responsive checks: all passed");
