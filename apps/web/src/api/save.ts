/**
 * Saving a file from SirisOS (11.8.0, for receipts).
 *
 * On iPhone, a download link in an app added to the Home Screen opens the file in a viewer with no way back, so it
 * offers the share sheet instead (Save to Files, AirDrop, Mail). iOS only opens the share sheet straight after a tap,
 * so when fetching the file took too long, `save` returns "tap" and the caller shows a button that calls `share` again.
 * Elsewhere it's an ordinary download.
 */

export type Saved = "saved" | "tap" | "cancelled";

type Sharing = Navigator & { canShare?: (d: { files: File[] }) => boolean; share?: (d: { files: File[]; title?: string }) => Promise<void> };

function iOS(): boolean {
  return typeof navigator !== "undefined" && (/iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1));
}

/** The file name from a Content-Disposition header (the UTF-8 one first). */
export function nameFrom(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (star) { try { return decodeURIComponent(star[1].trim()); } catch { /* fall through */ } }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : fallback;
}

export async function share(file: File): Promise<Saved> {
  const nav = navigator as Sharing;
  try {
    await nav.share!({ files: [file], title: file.name });
    return "saved";
  } catch (e) {
    const name = (e as { name?: string })?.name;
    if (name === "AbortError") return "cancelled";
    if (name === "NotAllowedError") return "tap";  // the tap was too long ago
    throw e;
  }
}

export async function save(blob: Blob, name: string): Promise<Saved> {
  const file = new File([blob], name, { type: blob.type || "application/octet-stream" });
  const nav = navigator as Sharing;
  if (iOS() && typeof nav.share === "function" && nav.canShare?.({ files: [file] })) return share(file);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return "saved";
}
