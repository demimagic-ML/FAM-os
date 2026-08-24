import * as path from "node:path";
import * as vscode from "vscode";
import { NativeConnector } from "./sdk/connector";
import { VsCodeSemanticProvider } from "./editor/provider";

let activeConnector: NativeConnector | undefined;
let connecting = false;
let retryTimer: NodeJS.Timeout | undefined;
let automatic = false;

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("famOS.connect", () => {
      automatic = true;
      return connect(true);
    }),
    vscode.commands.registerCommand("famOS.disconnect", () => {
      automatic = false;
      clearRetry();
      disconnect();
    }),
    vscode.workspace.onDidChangeWorkspaceFolders(() => reconnectForWorkspaceChange()),
  );
  const configuration = vscode.workspace.getConfiguration("famOS.connector");
  automatic = configuration.get<boolean>("autoConnect", false);
  if (automatic) void connect(false);
}

export function deactivate(): void {
  automatic = false;
  clearRetry();
  disconnect(false);
}

async function connect(notify = true): Promise<void> {
  if (activeConnector !== undefined || connecting) return;
  clearRetry();
  connecting = true;
  const configuration = vscode.workspace.getConfiguration("famOS.connector");
  const maximum = configuration.get<number>("maximumObservationCharacters", 16_384);
  if (!Number.isSafeInteger(maximum) || maximum < 256 || maximum > 131_072) {
    void vscode.window.showErrorMessage("FAM_OS connector observation limit is invalid.");
    connecting = false;
    return;
  }
  const instanceId = `vscode-instance-${process.pid}`;
  const connectorId = `fam-vscode-${process.pid}`;
  let connector: NativeConnector | undefined;
  try {
    const provider = new VsCodeSemanticProvider(instanceId, maximum, connectorId);
    connector = new NativeConnector(socketPath(configuration), provider, (status) => {
      if (status === "disconnected" && activeConnector === connector) {
        activeConnector = undefined;
        scheduleRetry();
      }
    });
    await connector.connect();
    activeConnector = connector;
    if (notify) void vscode.window.showInformationMessage("FAM_OS semantic connector is connected.");
  } catch {
    connector?.disconnect();
    if (notify) {
      void vscode.window.showErrorMessage("FAM_OS semantic connector could not connect safely.");
    }
    scheduleRetry();
  } finally {
    connecting = false;
  }
}

function disconnect(notify = true): void {
  if (activeConnector === undefined) return;
  activeConnector.disconnect();
  activeConnector = undefined;
  if (notify) void vscode.window.showInformationMessage("FAM_OS semantic connector disconnected.");
}

function reconnectForWorkspaceChange(): void {
  if (activeConnector === undefined) return;
  disconnect(false);
  void connect(false);
}

function scheduleRetry(): void {
  if (!automatic || retryTimer !== undefined) return;
  retryTimer = setTimeout(() => {
    retryTimer = undefined;
    void connect(false);
  }, 5_000);
}

function clearRetry(): void {
  if (retryTimer !== undefined) clearTimeout(retryTimer);
  retryTimer = undefined;
}

function socketPath(configuration: vscode.WorkspaceConfiguration): string {
  const configured = configuration.get<string>("socketPath", "").trim();
  if (configured.length > 0) {
    if (!path.isAbsolute(configured)) throw new Error("connector socket path must be absolute");
    return configured;
  }
  const runtime = process.env.XDG_RUNTIME_DIR
    ?? `/run/user/${typeof process.getuid === "function" ? process.getuid() : "unknown"}`;
  return path.join(runtime, "fam-os", "applications.sock");
}
