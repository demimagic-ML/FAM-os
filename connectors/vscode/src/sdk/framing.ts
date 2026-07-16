import { MAX_FRAME_BYTES } from "./types";

export function encodeFrame(value: unknown, maximum = MAX_FRAME_BYTES): Buffer {
  const payload = Buffer.from(canonicalJson(value), "utf8");
  if (payload.length === 0 || payload.length > maximum) throw new Error("frame exceeds limit");
  const header = Buffer.alloc(4);
  header.writeUInt32BE(payload.length, 0);
  return Buffer.concat([header, payload]);
}

export function canonicalJson(value: unknown): string {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("non-finite JSON number");
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (typeof value === "object" && value !== null) {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record).sort().map((key) => {
      if (record[key] === undefined) throw new Error("undefined JSON value");
      return `${JSON.stringify(key)}:${canonicalJson(record[key])}`;
    }).join(",")}}`;
  }
  throw new Error("unsupported JSON value");
}

export class FrameDecoder {
  private buffered = Buffer.alloc(0);

  constructor(private readonly maximum = MAX_FRAME_BYTES) {
    if (maximum <= 0 || maximum > 4_194_304) throw new Error("invalid frame limit");
  }

  push(chunk: Buffer): unknown[] {
    this.buffered = Buffer.concat([this.buffered, chunk]);
    const values: unknown[] = [];
    while (this.buffered.length >= 4) {
      const size = this.buffered.readUInt32BE(0);
      if (size === 0 || size > this.maximum) throw new Error("invalid frame size");
      if (this.buffered.length < size + 4) break;
      const payload = this.buffered.subarray(4, size + 4);
      this.buffered = this.buffered.subarray(size + 4);
      values.push(JSON.parse(payload.toString("utf8")) as unknown);
    }
    return values;
  }

  finish(): void {
    if (this.buffered.length !== 0) throw new Error("transport closed during frame");
  }
}
