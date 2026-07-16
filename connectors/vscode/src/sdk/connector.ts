import { promises as fs } from "node:fs";
import net from "node:net";
import { randomUUID } from "node:crypto";
import { FrameDecoder, encodeFrame } from "./framing";
import {
  parseMessage,
  requestMessage,
  responseMessage,
  schemaDocument,
  typedPayload,
} from "./protocol";
import {
  ActionConfirmation,
  LocalMessage,
  NativeCapabilityProvider,
  PreparedAction,
} from "./types";
import {
  actionConfirmation,
  observationRequest,
  preparationRequest,
} from "./validation";

export class NativeConnector {
  private socket: net.Socket | undefined;
  private decoder = new FrameDecoder();
  private readonly operations = new Map<string, AbortController>();
  private readonly proposals = new Map<string, PreparedAction>();
  private registrationWait: RegistrationWait | undefined;

  constructor(
    private readonly socketPath: string,
    private readonly provider: NativeCapabilityProvider,
    private readonly onStatus: (status: string) => void = () => undefined,
  ) {}

  async connect(): Promise<void> {
    if (this.socket !== undefined) return;
    await requirePrivateSocket(this.socketPath);
    const socket = net.createConnection({ path: this.socketPath });
    await new Promise<void>((resolve, reject) => {
      socket.once("connect", resolve);
      socket.once("error", reject);
    });
    this.socket = socket;
    socket.on("data", (chunk) => this.receive(chunk));
    socket.on("error", () => this.disconnect());
    socket.on("close", () => this.disconnect());
    const registrationId = randomUUID();
    const registered = this.waitForRegistration(registrationId);
    this.send(requestMessage(
      registrationId, "register",
      schemaDocument("fam.application.connector-registration/v1alpha1", this.provider.registration()),
    ));
    try {
      await registered;
    } catch (error) {
      this.disconnect();
      throw error;
    }
    this.onStatus("connected");
  }

  disconnect(): void {
    if (this.socket === undefined && this.registrationWait === undefined) return;
    const socket = this.socket;
    this.socket = undefined;
    for (const operation of this.operations.values()) operation.abort();
    this.operations.clear();
    this.proposals.clear();
    if (this.registrationWait !== undefined) {
      clearTimeout(this.registrationWait.timer);
      this.registrationWait.reject(new Error("connector registration ended"));
      this.registrationWait = undefined;
    }
    this.decoder = new FrameDecoder();
    this.provider.close?.();
    if (socket !== undefined && !socket.destroyed) socket.destroy();
    this.onStatus("disconnected");
  }

  private receive(chunk: Buffer): void {
    try {
      for (const value of this.decoder.push(chunk)) void this.handle(parseMessage(value));
    } catch {
      this.disconnect();
    }
  }

  private async handle(message: LocalMessage): Promise<void> {
    if (this.registrationWait !== undefined
      && message.correlation_id === this.registrationWait.messageId) {
      const wait = this.registrationWait;
      this.registrationWait = undefined;
      clearTimeout(wait.timer);
      if (message.kind === "ack") wait.resolve();
      else wait.reject(new Error("connector registration was rejected"));
      return;
    }
    if (message.kind === "cancel") {
      const requestId = message.payload.request_id;
      if (typeof requestId === "string") this.operations.get(requestId)?.abort();
      return;
    }
    if (message.kind === "ack" || message.kind === "error") return;
    const controller = new AbortController();
    this.operations.set(message.message_id, controller);
    try {
      await this.dispatch(message, controller.signal);
    } catch (error) {
      const code = error instanceof ConnectorError ? error.code : "connector.request_failed";
      this.send(responseMessage(randomUUID(), message.message_id, "error", { code }));
    } finally {
      this.operations.delete(message.message_id);
    }
  }

  private async dispatch(message: LocalMessage, signal: AbortSignal): Promise<void> {
    if (message.kind === "observe") return this.observe(message, signal);
    if (message.kind === "prepare_action") return this.prepare(message, signal);
    if (message.kind === "confirm_action") return this.execute(message, signal);
    throw new ConnectorError("connector.message_unsupported");
  }

  private async observe(message: LocalMessage, signal: AbortSignal): Promise<void> {
    const request = observationRequest(typedPayload(
      message, "fam.application.observation-request/v1alpha1",
    ));
    const result = await this.provider.observe(request, signal);
    this.send(responseMessage(
      randomUUID(), message.message_id, "observation",
      schemaDocument("fam.application.observation-result/v1alpha1", result) as unknown as objectPayload,
    ));
  }

  private async prepare(message: LocalMessage, signal: AbortSignal): Promise<void> {
    const request = preparationRequest(typedPayload(
      message, "fam.application.action-preparation/v1alpha1",
    ));
    const prepared = await this.provider.prepare(request, signal);
    const proposalId = prepared.proposal.proposal_id;
    if (typeof proposalId !== "string") throw new ConnectorError("connector.proposal_invalid");
    this.proposals.set(proposalId, prepared);
    this.send(responseMessage(
      randomUUID(), message.message_id, "action_proposal",
      schemaDocument("fam.application.action-proposal/v1alpha1", prepared.proposal) as unknown as objectPayload,
    ));
  }

  private async execute(message: LocalMessage, signal: AbortSignal): Promise<void> {
    const confirmation = actionConfirmation(typedPayload(
      message, "fam.application.action-confirmation/v1alpha1",
    ));
    const prepared = this.proposals.get(confirmation.proposal_id);
    if (prepared === undefined) throw new ConnectorError("connector.proposal_unknown");
    this.proposals.delete(confirmation.proposal_id);
    const result = await prepared.execute(confirmation, signal);
    this.send(responseMessage(
      randomUUID(), message.message_id, "action_result",
      schemaDocument("fam.application.action-result/v1alpha1", result) as unknown as objectPayload,
    ));
  }

  private send(message: LocalMessage): void {
    if (this.socket === undefined) throw new ConnectorError("connector.disconnected");
    this.socket.write(encodeFrame(message));
  }

  private waitForRegistration(messageId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        if (this.registrationWait?.messageId !== messageId) return;
        this.registrationWait = undefined;
        reject(new Error("connector registration timed out"));
      }, 5_000);
      this.registrationWait = { messageId, resolve, reject, timer };
    });
  }
}

type objectPayload = { [key: string]: import("./types").JsonValue };

interface RegistrationWait {
  messageId: string;
  resolve: () => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
}

export class ConnectorError extends Error {
  constructor(readonly code: string) {
    super(code);
  }
}

async function requirePrivateSocket(path: string): Promise<void> {
  const details = await fs.lstat(path);
  if (!details.isSocket() || (details.mode & 0o777) !== 0o600) {
    throw new Error("connector endpoint is not a private socket");
  }
  if (typeof process.getuid === "function" && details.uid !== process.getuid()) {
    throw new Error("connector endpoint owner is invalid");
  }
}
