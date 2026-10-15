/**
 * The text a PDF shows, read in Node with no new dependency (issue #280), so
 * the quilter journey can check what the downloaded pattern says.
 *
 * It reads the PDFs reportlab writes: content streams filtered by
 * ASCII85Decode and FlateDecode (qrep/export/pattern/render.py sets
 * pageCompression=1) and text in the built-in Helvetica, shown with Tj, TJ,
 * ' and " from literal or hex strings. Each shown string becomes one piece,
 * and the pieces join with single spaces, so a table cell or a wrapped line
 * reads as its words in drawing order. Bytes decode as Latin-1, which
 * matches WinAnsiEncoding everywhere outside 0x80 to 0x9F; the checks read
 * ASCII text only. A stream with any other filter, or an image, is skipped.
 */
import { inflateSync } from "node:zlib";

const STREAM = /<<((?:(?!>>\s*stream)[\s\S])*?)>>\s*stream\r?\n/g;
const SHOW_OPERATORS = new Set(["Tj", "TJ", "'", '"']);
const DELIMITERS = new Set(["(", ")", "<", ">", "[", "]", "{", "}", "/", "%"]);

function isSpace(ch: string): boolean {
  return ch === " " || ch === "\n" || ch === "\r" || ch === "\t" || ch === "\f" || ch === "\0";
}

function ascii85(data: Buffer): Buffer {
  let text = data.toString("latin1").replace(/\s+/g, "");
  if (text.startsWith("<~")) text = text.slice(2);
  const end = text.indexOf("~>");
  if (end >= 0) text = text.slice(0, end);
  const out: number[] = [];
  let group: number[] = [];
  const flush = (count: number) => {
    let value = 0;
    for (const digit of group) value = value * 85 + digit;
    const bytes = [
      Math.floor(value / 16777216) % 256,
      Math.floor(value / 65536) % 256,
      Math.floor(value / 256) % 256,
      value % 256,
    ];
    out.push(...bytes.slice(0, count));
    group = [];
  };
  for (const ch of text) {
    if (ch === "z" && group.length === 0) {
      out.push(0, 0, 0, 0);
      continue;
    }
    const digit = ch.charCodeAt(0) - 33;
    if (digit < 0 || digit > 84) throw new Error(`not ASCII85: ${JSON.stringify(ch)}`);
    group.push(digit);
    if (group.length === 5) flush(4);
  }
  if (group.length > 0) {
    const count = group.length - 1;
    while (group.length < 5) group.push(84);
    flush(count);
  }
  return Buffer.from(out);
}

function filters(dict: string): string[] | null {
  const match = /\/Filter\s*(\[[^\]]*\]|\/[A-Za-z0-9]+)/.exec(dict);
  if (!match) return [];
  const names = match[1].match(/\/[A-Za-z0-9]+/g) ?? [];
  const known = names.map((name) => name.slice(1));
  return known.every((name) => name === "ASCII85Decode" || name === "FlateDecode") ? known : null;
}

function decode(data: Buffer, chain: string[]): Buffer {
  let bytes = data;
  for (const name of chain) bytes = name === "ASCII85Decode" ? ascii85(bytes) : inflateSync(bytes);
  return bytes;
}

/** A literal string from its opening parenthesis: the text and the index after it. */
function literal(content: string, start: number): [string, number] {
  let depth = 1;
  let text = "";
  let i = start + 1;
  while (i < content.length && depth > 0) {
    const ch = content[i];
    if (ch === "\\") {
      const next = content[i + 1] ?? "";
      const escapes: Record<string, string> = { n: "\n", r: "\r", t: "\t", b: "\b", f: "\f" };
      if (next in escapes) {
        text += escapes[next];
        i += 2;
      } else if (/[0-7]/.test(next)) {
        const octal = /^[0-7]{1,3}/.exec(content.slice(i + 1, i + 4))?.[0] ?? next;
        text += String.fromCharCode(parseInt(octal, 8));
        i += 1 + octal.length;
      } else if (next === "\r" || next === "\n") {
        i += next === "\r" && content[i + 2] === "\n" ? 3 : 2;
      } else {
        text += next;
        i += 2;
      }
      continue;
    }
    if (ch === "(") depth += 1;
    if (ch === ")") depth -= 1;
    if (depth > 0) text += ch;
    i += 1;
  }
  return [text, i];
}

function hex(content: string, start: number): [string, number] {
  const end = content.indexOf(">", start);
  const close = end < 0 ? content.length : end;
  let digits = content.slice(start + 1, close).replace(/\s+/g, "");
  if (digits.length % 2 === 1) digits += "0";
  return [Buffer.from(digits, "hex").toString("latin1"), close + 1];
}

/** The strings one content stream shows, one piece per show operator. */
function shown(content: string): string[] {
  const pieces: string[] = [];
  let pending: string[] = [];
  let i = 0;
  while (i < content.length) {
    const ch = content[i];
    if (ch === "(") {
      const [text, next] = literal(content, i);
      pending.push(text);
      i = next;
    } else if ((ch === "<" || ch === ">") && content[i + 1] === ch) {
      // A dictionary bracket, such as a marked-content property list.
      i += 2;
    } else if (ch === "<") {
      const [text, next] = hex(content, i);
      pending.push(text);
      i = next;
    } else if (ch === "%") {
      while (i < content.length && content[i] !== "\n" && content[i] !== "\r") i += 1;
    } else if (isSpace(ch) || DELIMITERS.has(ch)) {
      i += 1;
    } else {
      let end = i;
      while (end < content.length && !isSpace(content[end]) && !DELIMITERS.has(content[end])) end += 1;
      const token = content.slice(i, end);
      i = end;
      if (SHOW_OPERATORS.has(token)) {
        pieces.push(pending.join(""));
        pending = [];
      } else if (token === "ID") {
        // Inline image data is binary: skip to its EI.
        const stop = content.slice(i).search(/\sEI(?=\s|$)/);
        i = stop < 0 ? content.length : i + stop + 3;
        pending = [];
      } else if (/^[A-Za-z*]/.test(token)) {
        pending = [];
      }
    }
  }
  return pieces;
}

/** Every string the PDF's content streams show, joined by single spaces. */
export function pdfText(bytes: Buffer): string {
  const file = bytes.toString("latin1");
  const pieces: string[] = [];
  for (const match of file.matchAll(STREAM)) {
    const dict = match[1];
    if (/\/Subtype\s*\/Image/.test(dict)) continue;
    const chain = filters(dict);
    if (chain === null) continue;
    const start = (match.index ?? 0) + match[0].length;
    const length = /\/Length\s+(\d+)(?!\s+\d+\s+R)/.exec(dict);
    const end = length ? start + Number(length[1]) : file.indexOf("endstream", start);
    let content: string;
    try {
      content = decode(bytes.subarray(start, end), chain).toString("latin1");
    } catch {
      continue;
    }
    pieces.push(...shown(content));
  }
  return pieces.join(" ").replace(/\s+/g, " ").trim();
}
