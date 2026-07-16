import { createHash } from "node:crypto";

export function sha256(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

export function documentRevision(version: number, content: string): string {
  if (!Number.isSafeInteger(version) || version < 1) throw new Error("invalid document version");
  return `vscode-document:${version}:${sha256(content)}`;
}
