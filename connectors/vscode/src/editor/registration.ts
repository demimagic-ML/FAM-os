import { JsonObject } from "../sdk/types";

interface RegistrationSettings {
  connectorId: string;
  instanceId: string;
  processId: number;
  vscodeVersion: string;
  workspaceUris: string[];
}

export function registration(settings: RegistrationSettings): JsonObject {
  const application = {
    application_id: "com.microsoft.vscode",
    display_name: "Visual Studio Code",
    vendor: "Microsoft",
    version: settings.vscodeVersion,
  };
  const instance = {
    instance_id: settings.instanceId,
    application,
    connector_id: settings.connectorId,
    process_id: settings.processId,
    workspace_uris: settings.workspaceUris,
  };
  const capabilities = declarations().map((capability) => ({
    entry_id: `${settings.instanceId}:${capability.capability_id}`,
    connector_id: settings.connectorId,
    instance_id: settings.instanceId,
    application_id: application.application_id,
    capability,
    resource_scopes: settings.workspaceUris,
    available: true,
  }));
  return {
    connector_id: settings.connectorId,
    transport_kind: "native_local",
    protocol_id: "fam.native-connector",
    protocol_version: "1",
    instance,
    capabilities,
    connected_at: new Date().toISOString(),
    contract_version: "fam.applications/v1alpha1",
  };
}

function declarations(): JsonObject[] {
  return [
    observation("vscode.editor.active", "Observe active editor", "active"),
    observation("vscode.editor.selection", "Observe selected editor text", "selection"),
    observation("vscode.diagnostics.active", "Observe active editor diagnostics", "diagnostics"),
    action("vscode.workspace_edit.apply", "Apply reversible workspace edit"),
    action("vscode.workspace_edit.undo", "Reverse an applied workspace edit"),
  ];
}

function observation(capabilityId: string, name: string, schema: string): JsonObject {
  return {
    capability_id: capabilityId,
    display_name: name,
    description: `${name} through the native semantic editor API.`,
    kind: "observation",
    required_authority: "observe",
    input_schema_id: `vscode.editor.${schema}.input.v1`,
    output_schema_id: `vscode.editor.${schema}.output.v1`,
    reversibility: "not_applicable",
    confirmation: "not_required",
    postcondition_ids: [],
  };
}

function action(capabilityId: string, name: string): JsonObject {
  return {
    capability_id: capabilityId,
    display_name: name,
    description: `${name} after exact document revision validation.`,
    kind: "action",
    required_authority: "modify",
    input_schema_id: "vscode.workspace_edit.input.v1",
    output_schema_id: "vscode.workspace_edit.output.v1",
    reversibility: "reversible",
    confirmation: "always",
    postcondition_ids: ["document.hash", "document.version"],
  };
}
