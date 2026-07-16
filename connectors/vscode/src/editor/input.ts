import { JsonObject, JsonValue } from "../sdk/types";
import { EditorPosition, EditorRange, EditorTextEdit } from "./types";

export function workspaceEdits(parameters: JsonObject): EditorTextEdit[] {
  exact(parameters, ["document_uri", "edits"]);
  if (typeof parameters.document_uri !== "string") {
    throw new Error("document_uri must be text");
  }
  const value = parameters.edits;
  if (!Array.isArray(value)) throw new Error("workspace edit requires edits");
  return value.map((item) => edit(item));
}

export function reversalToken(parameters: JsonObject): string {
  exact(parameters, ["reversal_token"]);
  if (typeof parameters.reversal_token !== "string" || parameters.reversal_token.length === 0) {
    throw new Error("reversal_token must be text");
  }
  return parameters.reversal_token;
}

function edit(value: JsonValue): EditorTextEdit {
  const item = object(value, "edit");
  exact(item, ["range", "new_text"]);
  if (typeof item.new_text !== "string") throw new Error("new_text must be text");
  return { range: range(item.range), new_text: item.new_text };
}

function range(value: JsonValue): EditorRange {
  const item = object(value, "range");
  exact(item, ["start", "end"]);
  return { start: position(item.start), end: position(item.end) };
}

function position(value: JsonValue): EditorPosition {
  const item = object(value, "position");
  exact(item, ["line", "character"]);
  if (!Number.isSafeInteger(item.line) || !Number.isSafeInteger(item.character)) {
    throw new Error("position values must be integers");
  }
  return { line: item.line as number, character: item.character as number };
}

function object(value: JsonValue, name: string): JsonObject {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${name} must be an object`);
  }
  return value;
}

function exact(value: JsonObject, fields: string[]): void {
  const actual = Object.keys(value).sort();
  const expected = [...fields].sort();
  if (actual.length !== expected.length || actual.some((item, index) => item !== expected[index])) {
    throw new Error("input fields are invalid");
  }
}
