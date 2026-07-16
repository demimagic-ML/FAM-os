import { randomUUID } from "node:crypto";
import * as vscode from "vscode";
import {
  ActionConfirmation,
  ActionPreparationRequest,
  JsonObject,
  PreparedAction,
} from "../sdk/types";
import { buildEditPlan } from "./edit-plan";
import { reversalToken, workspaceEdits } from "./input";
import { documentRevision, sha256 } from "./revision";
import { ReversalRecord, ReversalStore } from "./reversal-store";

export class WorkspaceActionProvider {
  constructor(private readonly reversals = new ReversalStore()) {}

  async prepare(request: ActionPreparationRequest, signal: AbortSignal): Promise<PreparedAction> {
    if (signal.aborted) throw new Error("action preparation cancelled");
    if (request.capability_id === "vscode.workspace_edit.apply") {
      return this.prepareApply(request);
    }
    if (request.capability_id === "vscode.workspace_edit.undo") {
      return this.prepareUndo(request);
    }
    throw new Error("unsupported editor action");
  }

  clear(): void {
    this.reversals.clear();
  }

  private async prepareApply(request: ActionPreparationRequest): Promise<PreparedAction> {
    const uri = actionUri(request);
    const document = await workspaceDocument(uri);
    if (request.expected_revision === null) throw new Error("document revision is required");
    const plan = buildEditPlan(
      uri.toString(), document.version, document.getText(), request.expected_revision,
      workspaceEdits(request.parameters),
    );
    const proposalId = randomUUID();
    const proposal = proposalPayload(request, proposalId, {
      document_uri: plan.document_uri,
      before_hash: plan.before_hash,
      after_hash: plan.after_hash,
      edits: plan.edits.map((edit) => ({
        range: {
          start: { line: edit.range.start.line, character: edit.range.start.character },
          end: { line: edit.range.end.line, character: edit.range.end.character },
        },
        new_text: edit.new_text,
      })),
    });
    return {
      proposal,
      execute: (confirmation, signal) => this.executeApply(
        request, proposalId, plan, document.getText(), confirmation, signal,
      ),
    };
  }

  private async executeApply(
    request: ActionPreparationRequest,
    proposalId: string,
    plan: ReturnType<typeof buildEditPlan>,
    beforeText: string,
    confirmation: ActionConfirmation,
    signal: AbortSignal,
  ): Promise<JsonObject> {
    const rejected = confirmationFailure(request, proposalId, confirmation);
    if (rejected !== null) return rejected;
    if (signal.aborted) return cancelledResult(proposalId);
    const document = await workspaceDocument(vscode.Uri.parse(plan.document_uri, true));
    if (documentRevision(document.version, document.getText()) !== plan.before_revision) {
      return preconditionResult(proposalId, plan.before_revision);
    }
    const edit = new vscode.WorkspaceEdit();
    for (const item of plan.edits) {
      edit.replace(document.uri, vscodeRange(item.range), item.new_text);
    }
    if (!await vscode.workspace.applyEdit(edit)) return executionResult(proposalId);
    const afterText = document.getText();
    const afterRevision = documentRevision(document.version, afterText);
    const reversal = this.reversals.create({
      documentUri: document.uri.toString(), expectedRevision: afterRevision,
      restoreText: beforeText, restoreHash: plan.before_hash,
    });
    return verifiedOrPostcondition(
      proposalId, plan.before_revision, afterRevision, sha256(afterText),
      plan.after_hash, document.version > plan.before_version, reversal.token,
      plan.edits.length,
    );
  }

  private async prepareUndo(request: ActionPreparationRequest): Promise<PreparedAction> {
    const token = reversalToken(request.parameters);
    const record = this.reversals.get(token);
    if (request.resource_uri !== record.documentUri
      || request.expected_revision !== record.expectedRevision) {
      throw new Error("reversal request scope or revision changed");
    }
    const document = await workspaceDocument(vscode.Uri.parse(record.documentUri, true));
    if (documentRevision(document.version, document.getText()) !== record.expectedRevision) {
      throw new Error("document changed after reversible action");
    }
    const proposalId = randomUUID();
    const proposal = proposalPayload(request, proposalId, {
      document_uri: record.documentUri,
      reversal_token: token,
      restore_hash: record.restoreHash,
    });
    return {
      proposal,
      execute: (confirmation, signal) => this.executeUndo(
        request, proposalId, record, confirmation, signal,
      ),
    };
  }

  private async executeUndo(
    request: ActionPreparationRequest,
    proposalId: string,
    record: ReversalRecord,
    confirmation: ActionConfirmation,
    signal: AbortSignal,
  ): Promise<JsonObject> {
    const rejected = confirmationFailure(request, proposalId, confirmation);
    if (rejected !== null) return rejected;
    if (signal.aborted) return cancelledResult(proposalId);
    const document = await workspaceDocument(vscode.Uri.parse(record.documentUri, true));
    const currentText = document.getText();
    if (documentRevision(document.version, currentText) !== record.expectedRevision) {
      return preconditionResult(proposalId, record.expectedRevision);
    }
    const beforeRevision = record.expectedRevision;
    const edit = new vscode.WorkspaceEdit();
    edit.replace(document.uri, fullRange(document, currentText), record.restoreText);
    if (!await vscode.workspace.applyEdit(edit)) return executionResult(proposalId);
    const afterText = document.getText();
    const afterRevision = documentRevision(document.version, afterText);
    this.reversals.consume(record.token);
    const inverse = this.reversals.create({
      documentUri: record.documentUri, expectedRevision: afterRevision,
      restoreText: currentText, restoreHash: sha256(currentText),
    });
    return verifiedOrPostcondition(
      proposalId, beforeRevision, afterRevision, sha256(afterText),
      record.restoreHash, true, inverse.token, 1,
    );
  }
}

async function workspaceDocument(uri: vscode.Uri): Promise<vscode.TextDocument> {
  if (uri.scheme !== "file" || vscode.workspace.getWorkspaceFolder(uri) === undefined) {
    throw new Error("document is outside the workspace");
  }
  const document = await vscode.workspace.openTextDocument(uri);
  const lastLine = document.lineAt(document.lineCount - 1);
  if (document.offsetAt(lastLine.range.end) > 1_048_576) {
    throw new Error("document exceeds action limit");
  }
  return document;
}

function actionUri(request: ActionPreparationRequest): vscode.Uri {
  const parameterUri = request.parameters.document_uri;
  if (typeof parameterUri !== "string" || request.resource_uri !== parameterUri) {
    throw new Error("workspace edit document URI is invalid");
  }
  return vscode.Uri.parse(parameterUri, true);
}

function vscodeRange(range: { start: { line: number; character: number }; end: { line: number; character: number } }): vscode.Range {
  return new vscode.Range(range.start.line, range.start.character, range.end.line, range.end.character);
}

function fullRange(document: vscode.TextDocument, content: string): vscode.Range {
  return new vscode.Range(new vscode.Position(0, 0), document.positionAt(content.length));
}

function proposalPayload(request: ActionPreparationRequest, proposalId: string, preview: JsonObject): JsonObject {
  return {
    proposal_id: proposalId,
    request: requestPayload(request),
    preview,
    reversibility: "reversible",
    confirmation: "always",
    postconditions: conditions("post"),
    preconditions: conditions("pre"),
    reversal_capability_id: "vscode.workspace_edit.undo",
  };
}

function requestPayload(request: ActionPreparationRequest): JsonObject {
  return { ...request } as unknown as JsonObject;
}

function conditions(kind: "pre" | "post"): JsonObject[] {
  const values = kind === "pre"
    ? [["document.version", "vscode.document-version"], ["document.hash", "sha256"]]
    : [["document.hash", "sha256"], ["document.version", "vscode.document-version"]];
  return values.map(([condition_id, verifier_id]) => ({
    condition_id, verifier_id,
    description: `${condition_id} must match the approved workspace edit.`,
  }));
}

function confirmationFailure(request: ActionPreparationRequest, proposalId: string, value: ActionConfirmation): JsonObject | null {
  if (value.proposal_id !== proposalId || value.permission_grant_id !== request.permission_grant_id) {
    return deniedResult(proposalId, "The confirmation did not match the prepared action.");
  }
  return value.decision === "denied"
    ? deniedResult(proposalId, value.reason ?? "The action was denied.") : null;
}

function verifiedOrPostcondition(
  proposalId: string, beforeRevision: string, afterRevision: string,
  actualHash: string, expectedHash: string, versionAdvanced: boolean,
  reversalToken: string, editCount: number,
): JsonObject {
  const evidenceItems = [
    conditionEvidence("document.hash", "sha256", actualHash === expectedHash, `sha256:${actualHash}`),
    conditionEvidence("document.version", "vscode.document-version", versionAdvanced, afterRevision),
  ];
  const passed = actualHash === expectedHash && versionAdvanced;
  return actionResult(
    proposalId, passed ? "verified" : "postcondition_failed", evidenceItems,
    { applied_edits: editCount }, beforeRevision, afterRevision, reversalToken,
    passed ? null : failure("postcondition_failed", "application.postcondition_failed", "The editor postcondition failed.", "after_state_change"),
  );
}

function conditionEvidence(condition_id: string, verifier_id: string, passed: boolean, details: string): JsonObject {
  return { condition_id, verifier_id, passed, details };
}

function preconditionResult(proposalId: string, before: string): JsonObject {
  return actionResult(proposalId, "precondition_failed", [], {}, before, null, null,
    failure("precondition_failed", "application.precondition_failed", "The document changed before the action.", "after_state_change"));
}

function executionResult(proposalId: string): JsonObject {
  return actionResult(proposalId, "execution_failed", [], {}, null, null, null,
    failure("execution_failed", "application.execution_failed", "VS Code did not apply the workspace edit.", "after_state_change"));
}

function deniedResult(proposalId: string, message: string): JsonObject {
  return actionResult(proposalId, "denied", [], {}, null, null, null,
    failure("permission_denied", "application.confirmation.denied", safeLine(message), "after_user_action"));
}

function cancelledResult(proposalId: string): JsonObject {
  return actionResult(proposalId, "cancelled", [], {}, null, null, null,
    failure("cancelled", "application.cancelled", "The editor action was cancelled.", "never"));
}

function actionResult(
  proposal_id: string, status: string, postcondition_evidence: JsonObject[], output: JsonObject,
  before_revision: string | null, after_revision: string | null,
  reversal_token: string | null, error: JsonObject | null,
): JsonObject {
  return { proposal_id, status, completed_at: new Date().toISOString(), postcondition_evidence,
    output, before_revision, after_revision, reversal_token, error };
}

function failure(category: string, code: string, safe_message: string, retry: string): JsonObject {
  return { category, code, safe_message, retry, evidence_ids: [],
    contract_version: "fam.application.failure/v1alpha1" };
}

function safeLine(value: string): string {
  const normalized = value.replace(/[\r\n\t\0-\x1f\x7f]/g, " ").trim();
  return (normalized || "The action was denied.").slice(0, 500);
}
