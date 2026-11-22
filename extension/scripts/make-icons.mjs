// Generates simple PNG icons (pink disc with a white shield) without external deps.
import { deflateSync } from "node:zlib";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const outDir = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "icons");
mkdirSync(outDir, { recursive: true });

const crcTable = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(td));
  return Buffer.concat([len, td, crc]);
}

// Shield outline in a unit square (x, y in 0..1): top flat, sides to a rounded point.
function insideShield(x, y) {
  const cx = x - 0.5;
  if (y < 0.24 || y > 0.8) return false;
  const half = y < 0.5 ? 0.24 : 0.24 * Math.max(0, 1 - (y - 0.5) / 0.3) ** 0.8;
  return Math.abs(cx) <= half;
}
function insideCheck(x, y) {
  // Check mark: two segments.
  const seg = (ax, ay, bx, by, w) => {
    const dx = bx - ax, dy = by - ay;
    const t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)));
    return Math.hypot(x - (ax + t * dx), y - (ay + t * dy)) <= w;
  };
  return seg(0.39, 0.5, 0.47, 0.58, 0.028) || seg(0.47, 0.58, 0.62, 0.41, 0.028);
}

function render(size) {
  const ss = 4; // supersampling
  const raw = Buffer.alloc((size * 4 + 1) * size);
  for (let py = 0; py < size; py++) {
    raw[py * (size * 4 + 1)] = 0;
    for (let px = 0; px < size; px++) {
      let r = 0, g = 0, b = 0, a = 0;
      for (let sy = 0; sy < ss; sy++) {
        for (let sx = 0; sx < ss; sx++) {
          const x = (px + (sx + 0.5) / ss) / size;
          const y = (py + (sy + 0.5) / ss) / size;
          const d = Math.hypot(x - 0.5, y - 0.5);
          if (d > 0.5) continue;
          a += 1;
          // pink -> fuchsia diagonal gradient
          const t = (x + y) / 2;
          let cr = 236 + (192 - 236) * t, cg = 72 + (38 - 72) * t, cb = 153 + (211 - 153) * t;
          if (insideShield(x, y)) {
            if (insideCheck(x, y)) { cr = 190; cg = 24; cb = 93; } else { cr = 255; cg = 255; cb = 255; }
          }
          r += cr; g += cg; b += cb;
        }
      }
      const o = py * (size * 4 + 1) + 1 + px * 4;
      const n = ss * ss;
      if (a > 0) {
        raw[o] = Math.round(r / a); raw[o + 1] = Math.round(g / a); raw[o + 2] = Math.round(b / a);
        raw[o + 3] = Math.round((a / n) * 255);
      }
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; ihdr[9] = 6; // 8-bit RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

for (const size of [16, 32, 48, 128]) {
  writeFileSync(join(outDir, `icon-${size}.png`), render(size));
  console.log(`icon-${size}.png`);
}