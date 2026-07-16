import * as vscode from "vscode";
import {
  ActionPreparationRequest,
  JsonObject,
  NativeCapabilityProvider,
  ObservationRequest,
  PreparedAction,
} from "../sdk/types";
import { observeEditor } from "./observations";
import { registration } from "./registration";
import { WorkspaceActionProvider } from "./workspace-actions";

export class VsCodeSemanticProvider implements NativeCapabilityProvider {
  private readonly actions = new WorkspaceActionProvider();
  private readonly registrationValue: JsonObject;

  constructor(
    private readonly instanceId: string,
    private readonly maximumObservationCharacters: number,
    connectorId: string,
  ) {
    const workspaceUris = (vscode.workspace.workspaceFolders ?? [])
      .map((item) => directoryScope(item.uri.toString())).sort();
    this.registrationValue = registration({
      connectorId,
      instanceId,
      processId: process.pid,
      vscodeVersion: vscode.version,
      workspaceUris,
    });
  }

  registration(): JsonObject {
    return this.registrationValue;
  }

  async observe(request: ObservationRequest, signal: AbortSignal): Promise<JsonObject> {
    this.requireInstance(request.instance_id);
    return observeEditor(request, this.maximumObservationCharacters, signal);
  }

  async prepare(
    request: ActionPreparationRequest, signal: AbortSignal,
  ): Promise<PreparedAction> {
    this.requireInstance(request.instance_id);
    return this.actions.prepare(request, signal);
  }

  close(): void {
    this.actions.clear();
  }

  private requireInstance(instanceId: string): void {
    if (instanceId !== this.instanceId) throw new Error("connector instance mismatch");
  }
}

function directoryScope(uri: string): string {
  return uri.endsWith("/") ? uri : `${uri}/`;
}
