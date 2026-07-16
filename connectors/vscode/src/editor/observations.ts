import * as vscode from "vscode";
import { documentRevision } from "./revision";
import { JsonObject, ObservationRequest } from "../sdk/types";

export async function observeEditor(
  request: ObservationRequest,
  maximumCharacters: number,
  signal: AbortSignal,
): Promise<JsonObject> {
  if (signal.aborted) return cancelled(request.request_id);
  const editor = vscode.window.activeTextEditor;
  if (editor === undefined) return unavailable(request.request_id);
  if (request.resource_uri !== null && request.resource_uri !== editor.document.uri.toString()) {
    return unavailable(request.request_id);
  }
  const document = editor.document;
  const revision = boundedRevision(document);
  let payload: JsonObject;
  if (request.capability_id === "vscode.editor.active") {
    requireParameterFields(request.parameters, []);
    payload = activePayload(editor);
  } else if (request.capability_id === "vscode.editor.selection") {
    requireParameterFields(request.parameters, ["maximum_characters"]);
    payload = selectionPayload(editor, observationLimit(request.parameters, maximumCharacters));
  } else if (request.capability_id === "vscode.diagnostics.active") {
    requireParameterFields(request.parameters, []);
    payload = diagnosticsPayload(document.uri);
  } else {
    return unavailable(request.request_id);
  }
  return {
    request_id: request.request_id,
    status: "observed",
    observed_at: new Date().toISOString(),
    payload,
    resource_uri: document.uri.toString(),
    revision,
    error: null,
  };
}

function requireParameterFields(parameters: JsonObject, allowed: string[]): void {
  const fields = Object.keys(parameters);
  if (fields.some((field) => !allowed.includes(field)) || fields.length > allowed.length) {
    throw new Error("observation parameters are invalid");
  }
}

function activePayload(editor: vscode.TextEditor): JsonObject {
  const document = editor.document;
  return {
    document_uri: document.uri.toString(),
    language_id: document.languageId,
    document_version: document.version,
    dirty: document.isDirty,
    line_count: document.lineCount,
    selection: rangePayload(editor.selection),
    visible_ranges: editor.visibleRanges.slice(0, 16).map(rangePayload),
  };
}

function selectionPayload(editor: vscode.TextEditor, maximum: number): JsonObject {
  const document = editor.document;
  const start = document.offsetAt(editor.selection.start);
  const end = document.offsetAt(editor.selection.end);
  const selectedLength = end - start;
  const boundedEnd = document.positionAt(Math.min(end, start + maximum));
  const selected = document.getText(new vscode.Range(editor.selection.start, boundedEnd));
  return {
    document_uri: editor.document.uri.toString(),
    language_id: editor.document.languageId,
    document_version: editor.document.version,
    selection: rangePayload(editor.selection),
    text: selected,
    text_truncated: selectedLength > maximum,
  };
}

function boundedRevision(document: vscode.TextDocument): string {
  const lastLine = document.lineAt(document.lineCount - 1);
  const characters = document.offsetAt(lastLine.range.end);
  if (characters > 1_048_576) return `vscode-document-version:${document.version}`;
  return documentRevision(document.version, document.getText());
}

function diagnosticsPayload(uri: vscode.Uri): JsonObject {
  const allDiagnostics = vscode.languages.getDiagnostics(uri);
  const diagnostics = allDiagnostics.slice(0, 200);
  return {
    document_uri: uri.toString(),
    diagnostics: diagnostics.map((item) => ({
      range: rangePayload(item.range),
      severity: item.severity,
      message: item.message.slice(0, 2048),
      source: item.source?.slice(0, 128) ?? null,
      code: typeof item.code === "object" ? String(item.code.value).slice(0, 128)
        : item.code === undefined ? null : String(item.code).slice(0, 128),
    })),
    truncated: allDiagnostics.length > diagnostics.length,
  };
}

function rangePayload(range: vscode.Range): JsonObject {
  return {
    start: { line: range.start.line, character: range.start.character },
    end: { line: range.end.line, character: range.end.character },
  };
}

function observationLimit(parameters: JsonObject, configured: number): number {
  const requested = parameters.maximum_characters;
  if (requested === undefined) return configured;
  if (!Number.isSafeInteger(requested) || Number(requested) <= 0) {
    throw new Error("maximum_characters is invalid");
  }
  return Math.min(configured, Number(requested));
}

function unavailable(requestId: string): JsonObject {
  return failed(requestId, "unavailable", "application.unavailable", "No matching active editor.", "after_state_change");
}

function cancelled(requestId: string): JsonObject {
  return failed(requestId, "cancelled", "application.cancelled", "The observation was cancelled.", "never");
}

function failed(
  requestId: string, category: string, code: string, safeMessage: string, retry: string,
): JsonObject {
  return {
    request_id: requestId,
    status: category === "unavailable" ? "unavailable" : "failed",
    observed_at: new Date().toISOString(),
    payload: {},
    resource_uri: null,
    revision: null,
    error: {
      category, code, safe_message: safeMessage, retry, evidence_ids: [],
      contract_version: "fam.application.failure/v1alpha1",
    },
  };
}
