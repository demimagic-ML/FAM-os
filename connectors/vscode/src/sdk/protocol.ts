import {
  APPLICATION_CONTRACT_VERSION,
  JsonObject,
  LOCAL_TRANSPORT_VERSION,
  LocalMessage,
  MessageKind,
  SchemaDocument,
} from "./types";

const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const RESPONSE_KINDS = new Set<MessageKind>([
  "observation", "action_proposal", "action_result", "ack", "error",
]);

export function schemaDocument(schemaId: string, payload: JsonObject): SchemaDocument {
  if (!schemaId.endsWith("/v1alpha1")) {
    throw new Error("schema id must be versioned");
  }
  return { schema_id: schemaId, contract_version: APPLICATION_CONTRACT_VERSION, payload };
}

export function requestMessage(
  messageId: string,
  kind: Exclude<MessageKind, "observation" | "action_proposal" | "action_result" | "ack" | "error">,
  document: SchemaDocument,
): LocalMessage {
  return localMessage(messageId, kind, document as unknown as JsonObject, null);
}

export function responseMessage(
  messageId: string,
  correlationId: string,
  kind: "observation" | "action_proposal" | "action_result" | "ack" | "error",
  payload: JsonObject,
): LocalMessage {
  return localMessage(messageId, kind, payload, correlationId);
}

export function parseMessage(value: unknown): LocalMessage {
  if (!isObject(value)) throw new Error("message must be an object");
  const fields = ["contract_version", "message_id", "kind", "correlation_id", "payload"];
  if (!exactFields(value, fields)) throw new Error("message fields are invalid");
  const message = value as unknown as LocalMessage;
  if (message.contract_version !== LOCAL_TRANSPORT_VERSION) throw new Error("unsupported transport");
  if (!IDENTIFIER.test(message.message_id)) throw new Error("invalid message id");
  if (!isMessageKind(message.kind) || !isObject(message.payload)) throw new Error("invalid message");
  const response = RESPONSE_KINDS.has(message.kind);
  if (response !== (typeof message.correlation_id === "string")) {
    throw new Error("invalid correlation");
  }
  if (typeof message.correlation_id === "string" && !IDENTIFIER.test(message.correlation_id)) {
    throw new Error("invalid correlation id");
  }
  return message;
}

export function typedPayload(message: LocalMessage, schemaId: string): JsonObject {
  const document = message.payload as unknown as SchemaDocument;
  if (!isObject(document) || !exactFields(document as unknown as JsonObject, [
    "schema_id", "contract_version", "payload",
  ])) throw new Error("invalid schema document");
  if (document.schema_id !== schemaId || document.contract_version !== APPLICATION_CONTRACT_VERSION) {
    throw new Error("unexpected schema document");
  }
  if (!isObject(document.payload)) throw new Error("schema payload must be an object");
  return document.payload;
}

function localMessage(
  messageId: string, kind: MessageKind, payload: JsonObject, correlationId: string | null,
): LocalMessage {
  if (!IDENTIFIER.test(messageId)) throw new Error("invalid message id");
  return {
    contract_version: LOCAL_TRANSPORT_VERSION,
    message_id: messageId,
    kind,
    correlation_id: correlationId,
    payload,
  };
}

function exactFields(value: JsonObject, fields: string[]): boolean {
  const keys = Object.keys(value).sort();
  return keys.length === fields.length && fields.sort().every((field, index) => keys[index] === field);
}

export function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isMessageKind(value: unknown): value is MessageKind {
  return typeof value === "string" && [
    "register", "observe", "observation", "prepare_action", "action_proposal",
    "confirm_action", "action_result", "connector_event", "cancel", "ack", "error",
  ].includes(value);
}
