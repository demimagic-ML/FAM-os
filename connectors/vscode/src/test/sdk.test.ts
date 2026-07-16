import assert from "node:assert/strict";
import test from "node:test";
import { FrameDecoder, canonicalJson, encodeFrame } from "../sdk/framing";
import {
  parseMessage,
  requestMessage,
  schemaDocument,
  typedPayload,
} from "../sdk/protocol";

test("canonical framing sorts keys and decodes fragmented multiple frames", () => {
  assert.equal(canonicalJson({ z: 1, a: { d: 2, b: 3 } }), '{"a":{"b":3,"d":2},"z":1}');
  const first = encodeFrame({ value: 1 });
  const second = encodeFrame({ value: 2 });
  const decoder = new FrameDecoder();
  assert.deepEqual(decoder.push(first.subarray(0, 3)), []);
  assert.deepEqual(decoder.push(Buffer.concat([first.subarray(3), second])), [
    { value: 1 }, { value: 2 },
  ]);
  decoder.finish();
  assert.throws(() => canonicalJson(Number.NaN), /non-finite/);
});

test("local messages and typed documents reject unknown fields and schemas", () => {
  const message = requestMessage(
    "message-1", "register",
    schemaDocument("fam.application.connector-registration/v1alpha1", { connector_id: "c" }),
  );
  assert.deepEqual(parseMessage(message), message);
  assert.equal(typedPayload(message, "fam.application.connector-registration/v1alpha1").connector_id, "c");
  assert.throws(() => typedPayload(message, "fam.application.observation-request/v1alpha1"), /unexpected/);
  assert.throws(() => parseMessage({ ...message, extra: true }), /fields/);
});
