import assert from "node:assert/strict";
import test from "node:test";
import { applyPlannedEdits, buildEditPlan } from "../editor/edit-plan";
import { documentRevision, sha256 } from "../editor/revision";

test("plans UTF-16 and CRLF editor ranges with deterministic hashes", () => {
  const content = "a😀b\r\nsecond\n";
  const plan = buildEditPlan(
    "file:///workspace/example.ts",
    7,
    content,
    documentRevision(7, content),
    [{
      range: { start: { line: 0, character: 1 }, end: { line: 0, character: 3 } },
      new_text: "X",
    }],
  );
  const updated = applyPlannedEdits(content, plan.edits);
  assert.equal(updated, "aXb\r\nsecond\n");
  assert.equal(plan.before_hash, sha256(content));
  assert.equal(plan.after_hash, sha256(updated));
});

test("rejects stale, overlapping, duplicate-position, and out-of-range edits", () => {
  const content = "alpha\nbeta";
  assert.throws(() => buildEditPlan(
    "file:///workspace/a", 2, content, "stale", [{
      range: { start: { line: 0, character: 0 }, end: { line: 0, character: 1 } },
      new_text: "x",
    }],
  ), /revision changed/);
  const revision = documentRevision(2, content);
  assert.throws(() => buildEditPlan("file:///workspace/a", 2, content, revision, [
    { range: { start: { line: 0, character: 0 }, end: { line: 0, character: 3 } }, new_text: "x" },
    { range: { start: { line: 0, character: 2 }, end: { line: 0, character: 4 } }, new_text: "y" },
  ]), /overlap/);
  assert.throws(() => buildEditPlan("file:///workspace/a", 2, content, revision, [
    { range: { start: { line: 0, character: 1 }, end: { line: 0, character: 1 } }, new_text: "x" },
    { range: { start: { line: 0, character: 1 }, end: { line: 0, character: 1 } }, new_text: "y" },
  ]), /overlap/);
  assert.throws(() => buildEditPlan("file:///workspace/a", 2, content, revision, [{
    range: { start: { line: 4, character: 0 }, end: { line: 4, character: 0 } }, new_text: "x",
  }]), /outside/);
});
