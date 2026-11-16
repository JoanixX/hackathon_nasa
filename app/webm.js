// Minimal WebM (Matroska) muxer for WebCodecs output: one video track, SimpleBlocks in clusters.
// No dependency. Written for the 3D view recordings; it does not write Cues (seeking falls back to a scan).
// Spec: https://www.matroska.org/technical/elements.html (EBML, Segment, Info, Tracks, Cluster).

const enc = new TextEncoder();

/** EBML variable-length size (minimal length, 1..8 bytes). */
export function vintSize(n) {
  if (!Number.isSafeInteger(n) || n < 0) throw new RangeError("bad EBML size");
  for (let len = 1; len <= 8; len++) {
    if (n < 2 ** (7 * len) - 1) {
      const out = new Uint8Array(len);
      let v = n;
      for (let i = len - 1; i >= 0; i--) { out[i] = v % 256; v = Math.floor(v / 256); }
      out[0] |= 1 << (8 - len);
      return out;
    }
  }
  throw new RangeError("EBML size too large");
}

function idBytes(id) {
  const out = [];
  for (let v = id; v > 0; v = Math.floor(v / 256)) out.unshift(v % 256);
  return Uint8Array.from(out);
}

function uint(n) {
  const out = [];
  let v = n;
  do { out.unshift(v % 256); v = Math.floor(v / 256); } while (v > 0);
  return Uint8Array.from(out);
}

function float64(x) { const b = new Uint8Array(8); new DataView(b.buffer).setFloat64(0, x); return b; }

function concat(parts) {
  const total = parts.reduce((a, p) => a + p.length, 0);
  const out = new Uint8Array(total);
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

function el(id, payload) {
  const body = payload instanceof Uint8Array ? payload : concat(payload);
  return concat([idBytes(id), vintSize(body.length), body]);
}

const ID = {
  EBML: 0x1a45dfa3, EBMLVersion: 0x4286, EBMLReadVersion: 0x42f7, EBMLMaxIDLength: 0x42f2, EBMLMaxSizeLength: 0x42f3,
  DocType: 0x4282, DocTypeVersion: 0x4287, DocTypeReadVersion: 0x4285,
  Segment: 0x18538067, Info: 0x1549a966, TimecodeScale: 0x2ad7b1, Duration: 0x4489, MuxingApp: 0x4d80, WritingApp: 0x5741,
  Tracks: 0x1654ae6b, TrackEntry: 0xae, TrackNumber: 0xd7, TrackUID: 0x73c5, TrackType: 0x83, CodecID: 0x86, FlagLacing: 0x9c,
  Video: 0xe0, PixelWidth: 0xb0, PixelHeight: 0xba, Cluster: 0x1f43b675, Timecode: 0xe7, SimpleBlock: 0xa3,
};

/**
 * Build a WebM file from encoded frames.
 * @param {{data: Uint8Array, timestampUs: number, key: boolean}[]} frames in decode order, first must be a key frame
 * @param {{width: number, height: number, codecId?: string}} opts
 * @returns {Uint8Array}
 */
export function muxWebM(frames, { width, height, codecId = "V_VP8", frameMs = 33 }) {
  if (!frames.length) throw new Error("no frames to mux");
  if (!frames[0].key) throw new Error("the first frame must be a key frame");
  const t0 = frames[0].timestampUs;
  const ms = (f) => Math.max(0, Math.round((f.timestampUs - t0) / 1000));
  const header = el(ID.EBML, [
    el(ID.EBMLVersion, uint(1)), el(ID.EBMLReadVersion, uint(1)), el(ID.EBMLMaxIDLength, uint(4)), el(ID.EBMLMaxSizeLength, uint(8)),
    el(ID.DocType, enc.encode("webm")), el(ID.DocTypeVersion, uint(2)), el(ID.DocTypeReadVersion, uint(2)),
  ]);
  const last = frames[frames.length - 1];
  const info = el(ID.Info, [el(ID.TimecodeScale, uint(1000000)), el(ID.Duration, float64(ms(last) + frameMs)),
    el(ID.MuxingApp, enc.encode("raiz-webm")), el(ID.WritingApp, enc.encode("RAIZ-SAR AI"))]);
  const tracks = el(ID.Tracks, [el(ID.TrackEntry, [
    el(ID.TrackNumber, uint(1)), el(ID.TrackUID, uint(1)), el(ID.TrackType, uint(1)), el(ID.FlagLacing, uint(0)),
    el(ID.CodecID, enc.encode(codecId)), el(ID.Video, [el(ID.PixelWidth, uint(width)), el(ID.PixelHeight, uint(height))]),
  ])]);
  // A new cluster at each key frame, or before the 16-bit relative timecode would overflow.
  const clusters = [];
  let cur = null;
  for (const f of frames) {
    const t = ms(f);
    if (!cur || f.key || t - cur.time > 30000) { cur = { time: t, blocks: [] }; clusters.push(cur); }
    const rel = t - cur.time;
    const head = new Uint8Array(4);
    head[0] = 0x81; // track number 1 as a vint
    new DataView(head.buffer).setInt16(1, rel);
    head[3] = f.key ? 0x80 : 0x00;
    cur.blocks.push(el(ID.SimpleBlock, [head, f.data]));
  }
  const body = clusters.map((c) => el(ID.Cluster, [el(ID.Timecode, uint(c.time)), ...c.blocks]));
  return concat([header, el(ID.Segment, [info, tracks, ...body])]);
}
