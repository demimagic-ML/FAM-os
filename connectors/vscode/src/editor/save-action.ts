import { createHash, randomUUID } from "node:crypto";
import * as vscode from "vscode";
import {
  ActionConfirmation,
  ActionPreparationRequest,
  JsonObject,
  PreparedAction,
} from "../sdk/types";
import { documentRevision } from "./revision";

export async function prepareSave(
  request: ActionPreparationRequest, signal: AbortSignal,
): Promise<PreparedAction> {
  if (signal.aborted) throw new Error("save preparation cancelled");
  const uri = saveUri(request);
  const document = await vscode.workspace.openTextDocument(uri);
  const before = documentRevision(document.version, document.getText());
  if (request.expected_revision !== before) throw new Error("document revision changed");
  const proposalId = randomUUID();
  return {
    proposal: proposal(request, proposalId, before),
    execute: (confirmation, executionSignal) => executeSave(
      document, request, proposalId, confirmation, executionSignal,
    ),
  };
}

async function executeSave(
  document: vscode.TextDocument, request: ActionPreparationRequest,
  proposalId: string, confirmation: ActionConfirmation, signal: AbortSignal,
): Promise<JsonObject> {
  if (confirmation.proposal_id !== proposalId
    || confirmation.permission_grant_id !== request.permission_grant_id
    || confirmation.decision !== "approved") {
    throw new Error("save confirmation is invalid");
  }
  if (signal.aborted) throw new Error("save execution cancelled");
  const before = documentRevision(document.version, document.getText());
  if (before !== request.expected_revision) throw new Error("document changed before save");
  if (!await document.save()) throw new Error("VS Code did not save the document");
  const bytes = await vscode.workspace.fs.readFile(document.uri);
  const diskText = Buffer.from(bytes).toString("utf8");
  const matches = diskText === document.getText() && !document.isDirty;
  const hash = createHash("sha256").update(bytes).digest("hex");
  const evidence = [
    condition("file.sha256", "file.sha256", matches, `sha256:${hash}`),
    condition("document.saved", "vscode.document-saved", matches, `dirty:${document.isDirty}`),
  ];
  const after = documentRevision(document.version, document.getText());
  return {
    proposal_id: proposalId,
    status: matches ? "verified" : "postcondition_failed",
    completed_at: new Date().toISOString(),
    postcondition_evidence: evidence,
    output: { document_uri: document.uri.toString(), disk_sha256: hash },
    before_revision: before,
    after_revision: after,
    reversal_token: null,
    error: matches ? null : failure(),
  };
}

function proposal(request: ActionPreparationRequest, proposalId: string, before: string): JsonObject {
  return {
    proposal_id: proposalId,
    request: { ...request } as unknown as JsonObject,
    preview: { document_uri: request.resource_uri, revision: before, operation: "save" },
    reversibility: "irreversible",
    confirmation: "always",
    postconditions: [
      requirement("file.sha256", "file.sha256"),
      requirement("document.saved", "vscode.document-saved"),
    ],
    preconditions: [
      requirement("document.hash", "sha256"),
      requirement("document.version", "vscode.document-version"),
    ],
    reversal_capability_id: null,
  };
}

function saveUri(request: ActionPreparationRequest): vscode.Uri {
  const fields = Object.keys(request.parameters);
  if (fields.length !== 1 || fields[0] !== "document_uri"
    || request.parameters.document_uri !== request.resource_uri
    || typeof request.resource_uri !== "string") {
    throw new Error("save scope is invalid");
  }
  const uri = vscode.Uri.parse(request.resource_uri, true);
  if (uri.scheme !== "file" || vscode.workspace.getWorkspaceFolder(uri) === undefined) {
    throw new Error("save target is outside the workspace");
  }
  return uri;
}

function requirement(condition_id: string, verifier_id: string): JsonObject {
  return { condition_id, verifier_id, description: `${condition_id} must be verified.` };
}

function condition(
  condition_id: string, verifier_id: string, passed: boolean, details: string,
): JsonObject {
  return { condition_id, verifier_id, passed, details };
}

function failure(): JsonObject {
  return {
    category: "postcondition_failed",
    code: "application.save.postcondition_failed",
    safe_message: "The saved file did not match the editor document.",
    retry: "after_state_change",
    evidence_ids: [],
    contract_version: "fam.application.failure/v1alpha1",
  };
}
