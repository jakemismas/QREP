/**
 * The page shows a photo's pixels as the file stores them (PR #247 review of
 * 0b7e9a3, major 4). Corpus annotations index the stored pixels, the way a
 * decoder that ignores orientation reads them (scripts/eval/corpus_screen.py
 * _open), but browsers turn a JPEG by its EXIF Orientation tag when they draw
 * it, and engines disagree on whether CSS image-orientation: none also
 * changes naturalWidth and canvas drawImage. So the page shows a copy whose
 * tag reads 1, which every engine draws as stored, and hashes the original.
 *
 * Only JPEG is handled: its EXIF sits in APP1 segments before the image data.
 * Layouts: a JPEG segment is FF, a marker byte and a two-byte big-endian
 * length that counts itself; an EXIF APP1 body is "Exif" 00 00 and a TIFF
 * header (II little-endian or MM big-endian, 42, IFD0's offset); an IFD is a
 * two-byte entry count, twelve-byte entries (tag, type, count, value) and a
 * next offset. Orientation is tag 0x0112, one SHORT.
 */

const ORIENTATION_TAG = 0x0112;
const SHORT = 3;

interface Entry {
  /** Where the SHORT value starts. */
  at: number;
  little: boolean;
  value: number;
}

function read16(bytes: Uint8Array, at: number, little: boolean): number {
  return little ? bytes[at] | (bytes[at + 1] << 8) : (bytes[at] << 8) | bytes[at + 1];
}

function read32(bytes: Uint8Array, at: number, little: boolean): number {
  const [a, b, c, d] = little ? [at + 3, at + 2, at + 1, at] : [at, at + 1, at + 2, at + 3];
  return ((bytes[a] << 24) >>> 0) + (bytes[b] << 16) + (bytes[c] << 8) + bytes[d];
}

/** The Orientation entry in IFD0 of the TIFF data from tiff to limit, or null. */
function orientationInTiff(bytes: Uint8Array, tiff: number, limit: number): Entry | null {
  if (tiff + 8 > limit) return null;
  const order = String.fromCharCode(bytes[tiff], bytes[tiff + 1]);
  if (order !== "II" && order !== "MM") return null;
  const little = order === "II";
  if (read16(bytes, tiff + 2, little) !== 42) return null;
  const ifd = tiff + read32(bytes, tiff + 4, little);
  if (ifd + 2 > limit) return null;
  const count = read16(bytes, ifd, little);
  for (let i = 0; i < count; i++) {
    const entry = ifd + 2 + 12 * i;
    if (entry + 12 > limit) return null;
    const tag = read16(bytes, entry, little);
    if (tag === ORIENTATION_TAG && read16(bytes, entry + 2, little) === SHORT && read32(bytes, entry + 4, little) === 1) {
      return { at: entry + 8, little, value: read16(bytes, entry + 8, little) };
    }
  }
  return null;
}

/**
 * "Exif" 00. The id's sixth byte is meant to be 00, but writers vary, so any
 * value passes: a tag the page missed would still turn the photo.
 */
const EXIF_ID = [0x45, 0x78, 0x69, 0x66, 0x00];
const EXIF_ID_LENGTH = 6;

/** Every Orientation entry in the file's EXIF segments, in file order. */
function orientationEntries(bytes: Uint8Array): Entry[] {
  const found: Entry[] = [];
  if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) return found;
  let pos = 2;
  while (pos + 4 <= bytes.length && bytes[pos] === 0xff) {
    const marker = bytes[pos + 1];
    // A fill byte before the marker.
    if (marker === 0xff) {
      pos += 1;
      continue;
    }
    // TEM and RST0 to RST7 carry no length.
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) {
      pos += 2;
      continue;
    }
    // EOI, or SOS: the image data starts, and EXIF comes before it.
    if (marker === 0xd9 || marker === 0xda) break;
    const length = (bytes[pos + 2] << 8) | bytes[pos + 3];
    if (length < 2) break;
    const body = pos + 4;
    const end = Math.min(pos + 2 + length, bytes.length);
    if (marker === 0xe1 && EXIF_ID.every((byte, i) => bytes[body + i] === byte)) {
      const entry = orientationInTiff(bytes, body + EXIF_ID_LENGTH, end);
      if (entry) found.push(entry);
    }
    pos = pos + 2 + length;
  }
  return found;
}

/** The JPEG's EXIF orientation (1 to 8), or null when it has none. */
export function readOrientation(bytes: Uint8Array): number | null {
  return orientationEntries(bytes)[0]?.value ?? null;
}

/**
 * A copy of the file with every EXIF orientation set to 1, or the same array
 * when there is none to change. The input is never written, so its sha256
 * stays the file's.
 */
export function withoutOrientation(bytes: Uint8Array<ArrayBuffer>): Uint8Array<ArrayBuffer> {
  const turned = orientationEntries(bytes).filter((entry) => entry.value !== 1);
  if (turned.length === 0) return bytes;
  const copy = bytes.slice();
  for (const { at, little } of turned) {
    copy[at] = little ? 1 : 0;
    copy[at + 1] = little ? 0 : 1;
  }
  return copy;
}
