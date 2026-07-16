import { NativeConnector } from "../sdk/connector";
import {
  ActionConfirmation,
  ActionPreparationRequest,
  JsonObject,
  NativeCapabilityProvider,
  ObservationRequest,
  PreparedAction,
} from "../sdk/types";
import { registration } from "../editor/registration";

class FixtureProvider implements NativeCapabilityProvider {
  constructor(private readonly completed: () => void) {}

  registration(): JsonObject {
    return registration({
      connectorId: "fixture-connector",
      instanceId: "fixture-instance",
      processId: process.pid,
      vscodeVersion: "fixture",
      workspaceUris: ["file:///fixture"],
    });
  }

  async observe(request: ObservationRequest, signal: AbortSignal): Promise<JsonObject> {
    if (signal.aborted) throw new Error("cancelled");
    return {
      request_id: request.request_id,
      status: "observed",
      observed_at: new Date().toISOString(),
      payload: { language_id: "typescript", fixture: true },
      resource_uri: "file:///fixture/example.ts",
      revision: "fixture-revision-1",
      error: null,
    };
  }

  async prepare(request: ActionPreparationRequest): Promise<PreparedAction> {
    const proposalId = "fixture-proposal";
    return {
      proposal: {
        proposal_id: proposalId,
        request: { ...request } as unknown as JsonObject,
        preview: { change: "fixture" },
        reversibility: "reversible",
        confirmation: "always",
        postconditions: [{
          condition_id: "document.hash", verifier_id: "sha256",
          description: "Fixture hash passes.",
        }],
        preconditions: [],
        reversal_capability_id: "vscode.workspace_edit.undo",
      },
      execute: async (confirmation: ActionConfirmation) => {
        if (confirmation.permission_grant_id !== request.permission_grant_id) {
          throw new Error("grant mismatch");
        }
        setTimeout(this.completed, 20);
        return {
          proposal_id: proposalId,
          status: "verified",
          completed_at: new Date().toISOString(),
          postcondition_evidence: [{
            condition_id: "document.hash", verifier_id: "sha256", passed: true,
            details: "fixture-hash",
          }],
          output: { applied_edits: 1 },
          before_revision: "fixture-revision-1",
          after_revision: "fixture-revision-2",
          reversal_token: "fixture-undo",
          error: null,
        };
      },
    };
  }
}

async function main(): Promise<void> {
  const socketPath = process.argv[2];
  if (socketPath === undefined) throw new Error("socket path is required");
  let finish: () => void = () => undefined;
  const completed = new Promise<void>((resolve) => { finish = resolve; });
  const connector = new NativeConnector(socketPath, new FixtureProvider(finish));
  await connector.connect();
  await completed;
  connector.disconnect();
}

void main().catch(() => { process.exitCode = 1; });
