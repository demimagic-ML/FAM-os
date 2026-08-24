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
import { prepareSave } from "./save-action";

export class VsCodeSemanticProvider implements NativeCapabilityProvider {
  private readonly actions = new WorkspaceActionProvider();
  private readonly registrationValue: JsonObject;
  private readonly workspaceUris: string[];

  constructor(
    private readonly instanceId: string,
    private readonly maximumObservationCharacters: number,
    connectorId: string,
  ) {
    this.workspaceUris = (vscode.workspace.workspaceFolders ?? [])
      .map((item) => directoryScope(item.uri.toString())).sort();
    this.registrationValue = registration({
      connectorId,
      instanceId,
      processId: process.pid,
      vscodeVersion: vscode.version,
      workspaceUris: this.workspaceUris,
    });
  }

  registration(): JsonObject {
    return this.registrationValue;
  }

  async observe(request: ObservationRequest, signal: AbortSignal): Promise<JsonObject> {
    this.requireInstance(request.instance_id);
    return observeEditor(
      request, this.maximumObservationCharacters, this.workspaceUris, signal,
    );
  }

  async prepare(
    request: ActionPreparationRequest, signal: AbortSignal,
  ): Promise<PreparedAction> {
    this.requireInstance(request.instance_id);
    if (request.capability_id === "vscode.document.save") {
      return prepareSave(request, signal);
    }
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
