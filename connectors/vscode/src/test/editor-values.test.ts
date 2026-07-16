import assert from "node:assert/strict";
import test from "node:test";
import { workspaceEdits } from "../editor/input";
import { registration } from "../editor/registration";
import { ReversalStore } from "../editor/reversal-store";

test("registration exposes only bounded semantic editor capabilities", () => {
  const value = registration({
    connectorId: "connector-1",
    instanceId: "instance-1",
    processId: 42,
    vscodeVersion: "1.114.0",
    workspaceUris: ["file:///workspace"],
  });
  const capabilities = value.capabilities;
  assert.ok(Array.isArray(capabilities));
  assert.equal(capabilities.length, 5);
  assert.deepEqual(capabilities.map((item) => (item as { capability: { capability_id: string } }).capability.capability_id), [
    "vscode.editor.active",
    "vscode.editor.selection",
    "vscode.diagnostics.active",
    "vscode.workspace_edit.apply",
    "vscode.workspace_edit.undo",
  ]);
});

test("workspace edit input is exact and typed", () => {
  const edits = workspaceEdits({ document_uri: "file:///workspace/a", edits: [{
    range: { start: { line: 1, character: 2 }, end: { line: 1, character: 3 } },
    new_text: "replacement",
  }] });
  assert.equal(edits[0].range.start.line, 1);
  assert.throws(() => workspaceEdits({ document_uri: "file:///workspace/a", edits: [{
    range: { start: { line: 1, character: 2 }, end: { line: 1, character: 3 } },
    new_text: "x", extra: true,
  }] }), /fields/);
});

test("reversal store is bounded and tokens are single-consumption", () => {
  const store = new ReversalStore(1);
  const first = store.create({
    documentUri: "file:///a", expectedRevision: "r1", restoreText: "a", restoreHash: "h1",
  });
  const second = store.create({
    documentUri: "file:///b", expectedRevision: "r2", restoreText: "b", restoreHash: "h2",
  });
  assert.throws(() => store.get(first.token), /unavailable/);
  assert.equal(store.get(second.token), second);
  store.consume(second.token);
  assert.throws(() => store.get(second.token), /unavailable/);
});
