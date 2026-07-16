export const APPLICATION_CONTRACT_VERSION = "fam.applications/v1alpha1";
export const LOCAL_TRANSPORT_VERSION = "fam.applications.local/v1alpha1";
export const MAX_FRAME_BYTES = 1_048_576;

export type JsonScalar = string | number | boolean | null;
export type JsonValue = JsonScalar | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export type MessageKind =
  | "register" | "observe" | "observation" | "prepare_action"
  | "action_proposal" | "confirm_action" | "action_result"
  | "connector_event" | "cancel" | "ack" | "error";

export interface SchemaDocument {
  schema_id: string;
  contract_version: string;
  payload: JsonObject;
}

export interface LocalMessage {
  contract_version: string;
  message_id: string;
  kind: MessageKind;
  correlation_id: string | null;
  payload: JsonObject;
}

export interface ObservationRequest {
  request_id: string;
  instance_id: string;
  capability_id: string;
  permission_grant_id: string;
  parameters: JsonObject;
  resource_uri: string | null;
}

export interface ActionPreparationRequest {
  request_id: string;
  instance_id: string;
  capability_id: string;
  permission_grant_id: string;
  summary: string;
  parameters: JsonObject;
  resource_uri: string | null;
  expected_revision: string | null;
}

export interface ActionConfirmation {
  confirmation_id: string;
  proposal_id: string;
  permission_grant_id: string;
  decision: "approved" | "denied";
  decided_by: string;
  decided_at: string;
  reason: string | null;
}

export interface ConditionRequirement {
  condition_id: string;
  verifier_id: string;
  description: string;
}

export interface PreparedAction {
  proposal: JsonObject;
  execute(confirmation: ActionConfirmation, signal: AbortSignal): Promise<JsonObject>;
}

export interface NativeCapabilityProvider {
  registration(): JsonObject;
  observe(request: ObservationRequest, signal: AbortSignal): Promise<JsonObject>;
  prepare(request: ActionPreparationRequest, signal: AbortSignal): Promise<PreparedAction>;
  close?(): void;
}
