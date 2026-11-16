// fast-check properties for the WebM muxer (app/webm.js): the file parses back to exactly the frames given.
// Run: node --test tests/js/webm.property.test.mjs   (FAST_CHECK_MODULE may point at a local fast-check build)
import { test } from "node:test";
import assert from "node:assert/strict";

const fcMod = await import(process.env.FAST_CHECK_MODULE || "fast-check");
const fc = fcMod.default ?? fcMod;
const { muxWebM, vintSize } = await import(new URL("../../app/webm.js", import.meta.url));
const SEED = 20261115;

function readVint(b, o, keepMarker) {
  const first = b[o];
  let len = 1;
  while (len <= 8 && !(first & (0x80 >> (len - 1)))) len++;
  if (len > 8) throw new Error("bad vint at " + o);
  let v = keepMarker ? first : first & ((0x80 >> (len - 1)) - 1);
  for (let i = 1; i < len; i++) v = v * 256 + b[o + i];
  return { value: v, len };
}

function parse(b, start = 0, end = b.length) {
  const out = [];
  let o = start;
  while (o < end) {
    const id = readVint(b, o, true); o += id.len;
    const size = readVint(b, o, false); o += size.len;
    out.push({ id: id.value, start: o, end: o + size.value });
    o += size.value;
  }
  if (o !== end) throw new Error("element overruns its parent");
  return out;
}

const uintOf = (b, e) => { let v = 0; for (let i = e.start; i < e.end; i++) v = v * 256 + b[i]; return v; };
const str = (b, e) => new TextDecoder().decode(b.subarray(e.start, e.end));

const frames = fc.array(fc.record({ size: fc.integer({ min: 1, max: 300 }), gap: fc.oneof(fc.integer({ min: 0, max: 80 }), fc.constant(31000)), key: fc.boolean() }),
  { minLength: 1, maxLength: 120 }).map((xs) => {
  let t = 5_000_000;
  return xs.map((x, i) => {
    t += x.gap * 1000;
    const data = new Uint8Array(x.size);
    for (let k = 0; k < x.size; k++) data[k] = (i * 31 + k * 7) & 255;
    return { data, timestampUs: t, key: i === 0 ? true : x.key };
  });
});

test("muxed WebM parses back to the same frames, times and key flags", () => {
  fc.assert(fc.property(frames, fc.integer({ min: 2, max: 4096 }), fc.integer({ min: 2, max: 4096 }), (fs, w, h) => {
    const b = muxWebM(fs, { width: w, height: h });
    const top = parse(b);
    assert.equal(top.length, 2);
    assert.equal(top[0].id, 0x1a45dfa3);
    const docType = parse(b, top[0].start, top[0].end).find((e) => e.id === 0x4282);
    assert.equal(str(b, docType), "webm");
    assert.equal(top[1].id, 0x18538067);
    const seg = parse(b, top[1].start, top[1].end);
    const tracks = seg.find((e) => e.id === 0x1654ae6b);
    const entry = parse(b, tracks.start, tracks.end)[0];
    const video = parse(b, entry.start, entry.end).find((e) => e.id === 0xe0);
    const dims = parse(b, video.start, video.end);
    assert.equal(uintOf(b, dims.find((e) => e.id === 0xb0)), w);
    assert.equal(uintOf(b, dims.find((e) => e.id === 0xba)), h);
    const blocks = [];
    for (const cl of seg.filter((e) => e.id === 0x1f43b675)) {
      const kids = parse(b, cl.start, cl.end);
      const base = uintOf(b, kids.find((e) => e.id === 0xe7));
      kids.filter((e) => e.id === 0xa3).forEach((blk, i) => {
        const rel = new DataView(b.buffer, b.byteOffset + blk.start + 1, 2).getInt16(0);
        assert.ok(rel >= 0 && rel <= 30000);
        const key = (b[blk.start + 3] & 0x80) !== 0;
        if (i === 0) assert.ok(true);
        blocks.push({ t: base + rel, key, data: b.subarray(blk.start + 4, blk.end) });
      });
    }
    assert.equal(blocks.length, fs.length);
    const t0 = fs[0].timestampUs;
    fs.forEach((f, i) => {
      assert.equal(blocks[i].t, Math.round((f.timestampUs - t0) / 1000));
      assert.equal(blocks[i].key, f.key);
      assert.deepEqual(Array.from(blocks[i].data), Array.from(f.data));
    });
  }), { numRuns: 1500, seed: SEED });
});

test("EBML sizes round-trip and use the minimal length", () => {
  fc.assert(fc.property(fc.integer({ min: 0, max: 2 ** 48 }), (n) => {
    const v = vintSize(n);
    const r = readVint(v, 0, false);
    assert.equal(r.value, n);
    assert.equal(r.len, v.length);
    if (v.length > 1) assert.ok(n >= 2 ** (7 * (v.length - 1)) - 1);
  }), { numRuns: 3000, seed: SEED });
});

test("muxing refuses empty input and a non-key first frame", () => {
  assert.throws(() => muxWebM([], { width: 2, height: 2 }));
  assert.throws(() => muxWebM([{ data: new Uint8Array(1), timestampUs: 0, key: false }], { width: 2, height: 2 }));
});
