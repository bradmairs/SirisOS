/**
 * 12.5: a photo from the phone, ready for SirisTrails: when and where it was taken (from its EXIF), and two JPEGs
 * made here in the browser (2048 px and a 480 px thumbnail), so the server needs no image library and nothing
 * bigger than it needs is uploaded. Safari reads HEIC itself; iPhones hand over JPEG anyway.
 */

export interface PhotoInfo { taken: string | null; lat: number | null; lon: number | null }

const ascii = (v: DataView, at: number, n: number) => { let s = ""; for (let i = 0; i < n; i++) { const c = v.getUint8(at + i); if (!c) break; s += String.fromCharCode(c); } return s; };

/** EXIF from a JPEG or HEIC: the TIFF block after "Exif\0\0" (wherever it is in the file). */
export function readExif(buf: ArrayBuffer): PhotoInfo {
  const none: PhotoInfo = { taken: null, lat: null, lon: null };
  const bytes = new Uint8Array(buf);
  let start = -1;
  for (let i = 0; i < bytes.length - 10; i++) {
    if (bytes[i] === 0x45 && bytes[i + 1] === 0x78 && bytes[i + 2] === 0x69 && bytes[i + 3] === 0x66 && bytes[i + 4] === 0 && bytes[i + 5] === 0) {
      const b = bytes[i + 6];
      if ((b === 0x49 && bytes[i + 7] === 0x49) || (b === 0x4d && bytes[i + 7] === 0x4d)) { start = i + 6; break; }
    }
  }
  if (start < 0) return none;
  const v = new DataView(buf, start);
  const le = v.getUint8(0) === 0x49;
  const u16 = (o: number) => v.getUint16(o, le), u32 = (o: number) => v.getUint32(o, le);
  const tags = (ifd: number): Map<number, { type: number; count: number; at: number }> => {
    const out = new Map<number, { type: number; count: number; at: number }>();
    if (ifd <= 0 || ifd + 2 > v.byteLength) return out;
    const n = u16(ifd);
    for (let k = 0; k < n; k++) {
      const e = ifd + 2 + k * 12;
      if (e + 12 > v.byteLength) break;
      const type = u16(e + 2), count = u32(e + 4);
      const size = ({ 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 10: 8 } as Record<number, number>)[type] ?? 1;
      out.set(u16(e), { type, count, at: size * count > 4 ? u32(e + 8) : e + 8 });
    }
    return out;
  };
  try {
    const ifd0 = tags(u32(4));
    const exif = tags(ifd0.get(0x8769) ? u32(ifd0.get(0x8769)!.at) : 0);
    const gps = tags(ifd0.get(0x8825) ? u32(ifd0.get(0x8825)!.at) : 0);
    const str = (t?: { count: number; at: number }) => (t ? ascii(v, t.at, t.count) : "");
    const raw = str(exif.get(0x9003)) || str(ifd0.get(0x0132));  // DateTimeOriginal, else DateTime
    const offset = str(exif.get(0x9011));                         // OffsetTimeOriginal, "+11:00"
    const m = raw.match(/^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})/);
    const taken = m ? `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}${/^[+-]\d{2}:\d{2}$/.test(offset) ? offset : ""}` : null;
    const deg = (t?: { at: number }) => (t ? [0, 1, 2].map((i) => u32(t.at + i * 8) / (u32(t.at + i * 8 + 4) || 1)).reduce((a, x, i) => a + x / 60 ** i, 0) : null);
    let lat = deg(gps.get(2)), lon = deg(gps.get(4));
    if (lat != null && str(gps.get(1)) === "S") lat = -lat;
    if (lon != null && str(gps.get(3)) === "W") lon = -lon;
    if (lat === 0 && lon === 0) lat = lon = null;
    return { taken, lat: lat != null ? Math.round(lat * 1e6) / 1e6 : null, lon: lon != null ? Math.round(lon * 1e6) / 1e6 : null };
  } catch {
    return none;
  }
}

async function jpeg(bitmap: ImageBitmap, max: number, quality: number): Promise<{ blob: Blob; w: number; h: number }> {
  const scale = Math.min(1, max / Math.max(bitmap.width, bitmap.height));
  const w = Math.round(bitmap.width * scale), h = Math.round(bitmap.height * scale);
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, w, h);
  const blob = await new Promise<Blob | null>((ok) => canvas.toBlob(ok, "image/jpeg", quality));
  if (!blob) throw new Error("Couldn't make a JPEG of that photo.");
  return { blob, w, h };
}

export async function preparePhoto(file: File): Promise<{ full: Blob; thumb: Blob; w: number; h: number; info: PhotoInfo }> {
  const info = readExif(await file.arrayBuffer());
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    throw new Error(`This browser can't open ${file.name}. Add it from your iPhone, which sends it as a JPEG.`);
  }
  const full = await jpeg(bitmap, 2048, 0.85);
  const thumb = await jpeg(bitmap, 480, 0.75);
  bitmap.close();
  return { full: full.blob, thumb: thumb.blob, w: full.w, h: full.h, info };
}
