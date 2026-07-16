import {
  ActionConfirmation,
  ActionPreparationRequest,
  JsonObject,
  ObservationRequest,
} from "./types";
import { isObject } from "./protocol";

export function observationRequest(value: JsonObject): ObservationRequest {
  exact(value, [
    "request_id", "instance_id", "capability_id", "permission_grant_id",
    "parameters", "resource_uri",
  ]);
  return {
    request_id: text(value.request_id, "request_id"),
    instance_id: text(value.instance_id, "instance_id"),
    capability_id: text(value.capability_id, "capability_id"),
    permission_grant_id: text(value.permission_grant_id, "permission_grant_id"),
    parameters: object(value.parameters, "parameters"),
    resource_uri: optionalText(value.resource_uri, "resource_uri"),
  };
}

export function preparationRequest(value: JsonObject): ActionPreparationRequest {
  exact(value, [
    "request_id", "instance_id", "capability_id", "permission_grant_id", "summary",
    "parameters", "resource_uri", "expected_revision",
  ]);
  return {
    request_id: text(value.request_id, "request_id"),
    instance_id: text(value.instance_id, "instance_id"),
    capability_id: text(value.capability_id, "capability_id"),
    permission_grant_id: text(value.permission_grant_id, "permission_grant_id"),
    summary: text(value.summary, "summary"),
    parameters: object(value.parameters, "parameters"),
    resource_uri: optionalText(value.resource_uri, "resource_uri"),
    expected_revision: optionalText(value.expected_revision, "expected_revision"),
  };
}

export function actionConfirmation(value: JsonObject): ActionConfirmation {
  exact(value, [
    "confirmation_id", "proposal_id", "permission_grant_id", "decision",
    "decided_by", "decided_at", "reason",
  ]);
  const decision = value.decision;
  if (decision !== "approved" && decision !== "denied") throw new Error("invalid decision");
  return {
    confirmation_id: text(value.confirmation_id, "confirmation_id"),
    proposal_id: text(value.proposal_id, "proposal_id"),
    permission_grant_id: text(value.permission_grant_id, "permission_grant_id"),
    decision,
    decided_by: text(value.decided_by, "decided_by"),
    decided_at: text(value.decided_at, "decided_at"),
    reason: optionalText(value.reason, "reason"),
  };
}

export function exact(value: JsonObject, fields: string[]): void {
  const actual = Object.keys(value).sort();
  const expected = [...fields].sort();
  if (actual.length !== expected.length || actual.some((item, index) => item !== expected[index])) {
    throw new Error("object fields are invalid");
  }
}

export function text(value: unknown, name: string): string {
  if (typeof value !== "string" || value.trim().length === 0 || value.includes("\0")) {
    throw new Error(`${name} is invalid`);
  }
  return value;
}

function optionalText(value: unknown, name: string): string | null {
  return value === null ? null : text(value, name);
}

function object(value: unknown, name: string): JsonObject {
  if (!isObject(value)) throw new Error(`${name} must be an object`);
  return value;
}
