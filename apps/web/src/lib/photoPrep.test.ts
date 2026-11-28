import { describe, expect, it } from "vitest";
import { readExif } from "./photoPrep";
import { fit, gpxPoints } from "./shareCard";

/** A little-endian TIFF/EXIF block like an iPhone's: DateTimeOriginal, OffsetTimeOriginal and GPS. */
function exifJpeg(): ArrayBuffer {
  const b = new ArrayBuffer(400), v = new DataView(b), u8 = new Uint8Array(b);
  const head = [0xff, 0xd8, 0xff, 0xe1, 0x01, 0x80, 0x45, 0x78, 0x69, 0x66, 0, 0];
  u8.set(head, 0);
  const T = 12;  // the TIFF block starts here
  const w16 = (o: number, x: number) => v.setUint16(T + o, x, true), w32 = (o: number, x: number) => v.setUint32(T + o, x, true);
  const str = (o: number, s: string) => { for (let i = 0; i < s.length; i++) u8[T + o + i] = s.charCodeAt(i); };
  u8.set([0x49, 0x49], T); w16(2, 42); w32(4, 8);
  // IFD0: ExifIFD pointer, GPS pointer
  w16(8, 2);
  w16(10, 0x8769); w16(12, 4); w32(14, 1); w32(18, 50);
  w16(22, 0x8825); w16(24, 4); w32(26, 1); w32(30, 120);
  w32(34, 0);
  // Exif IFD at 50: DateTimeOriginal (20 bytes at 200), OffsetTimeOriginal (7 bytes at 230)
  w16(50, 2);
  w16(52, 0x9003); w16(54, 2); w32(56, 20); w32(60, 200);
  w16(64, 0x9011); w16(66, 2); w32(68, 7); w32(72, 230);
  str(200, "2025:10:09 10:41:05\0"); str(230, "+08:00\0");
  // GPS IFD at 120: S, lat, E, lon
  w16(120, 4);
  w16(122, 1); w16(124, 2); w32(126, 2); str(130, "N\0");
  w16(134, 2); w16(136, 5); w32(138, 3); w32(142, 250);
  w16(146, 3); w16(148, 2); w32(150, 2); str(154, "E\0");
  w16(158, 4); w16(160, 5); w32(162, 3); w32(166, 300);
  const rat = (o: number, vals: [number, number][]) => vals.forEach(([n, d], i) => { w32(o + i * 8, n); w32(o + i * 8 + 4, d); });
  rat(250, [[22, 1], [20, 1], [3000, 100]]);   // 22° 20' 30" N
  rat(300, [[114, 1], [11, 1], [0, 1]]);       // 114° 11' E
  return b;
}

describe("photos and the share card (12.5)", () => {
  it("reads when and where a photo was taken", () => {
    expect(readExif(exifJpeg())).toEqual({ taken: "2025-10-09T10:41:05+08:00", lat: 22.341667, lon: 114.183333 });
    expect(readExif(new Uint8Array([0xff, 0xd8, 1, 2, 3]).buffer)).toEqual({ taken: null, lat: null, lon: null });
  });

  it("draws the route from a GPX, north up and in proportion", () => {
    const pts = gpxPoints('<trkpt lat="-37.8" lon="145.0"><ele>1</ele></trkpt><trkpt lat="-37.79" lon="145.0"></trkpt><trkpt lat="-37.79" lon="145.01"></trkpt>');
    expect(pts).toEqual([[-37.8, 145], [-37.79, 145], [-37.79, 145.01]]);
    const xy = fit(pts, 100, 100);
    expect(xy[0][1]).toBeGreaterThan(xy[1][1]);              // south is lower on the picture
    expect(xy[2][0]).toBeGreaterThan(xy[1][0]);              // east is to the right
    expect(Math.abs(xy[0][1] - xy[1][1]) / Math.abs(xy[2][0] - xy[1][0])).toBeCloseTo(1 / Math.cos((37.79 * Math.PI) / 180), 1);
  });
});
