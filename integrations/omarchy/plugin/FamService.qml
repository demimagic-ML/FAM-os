import QtQuick
import QtWebSockets
import Quickshell
import Quickshell.Io

Item {
  id: root

  property var settings: ({})
  property bool available: false
  property bool refreshing: false
  property string error: ""
  property var document: ({ service: "unavailable", goal: null, resources: {} })
  property string pendingAction: ""
  property int reconnectDelayMs: 1000
  property int commandSequence: 0
  readonly property string pluginVersion: "0.1.0"

  readonly property string runtimeRoot: Quickshell.env("XDG_RUNTIME_DIR") + "/fam-os"
  readonly property string tokenPath: runtimeRoot + "/widget.token"
  readonly property string descriptorPath: runtimeRoot + "/widget.json"
  readonly property string endpoint: {
    try {
      var descriptor = JSON.parse(String(descriptorFile.text() || "{}"))
      return String(descriptor.endpoint || "http://127.0.0.1:8765")
    } catch (failure) {
      return "http://127.0.0.1:8765"
    }
  }
  readonly property string token: String(tokenFile.text() || "").trim()
  readonly property string socketUrl: endpoint.replace(/^http/, "ws")
    + "/api/v1/events?token=" + encodeURIComponent(token)
  readonly property int refreshInterval: activeGoal
    ? intSetting("activeRefreshMs", 30000)
    : intSetting("idleRefreshMs", 30000)
  readonly property var activeGoal: document && document.goal ? document.goal : null

  function intSetting(name, fallback) {
    var value = parseInt(String(
      settings && settings[name] !== undefined ? settings[name] : fallback
    ), 10)
    return isFinite(value) ? value : fallback
  }

  function commandId() {
    commandSequence += 1
    return "qml-" + String(Date.now()) + "-" + String(commandSequence)
  }

  function validStatus(value) {
    return value && typeof value === "object"
      && value.apiVersion === 1
      && typeof value.serviceVersion === "string"
      && compatibleVersion(String(value.pluginMinVersion || ""), pluginVersion)
      && value.service === "healthy"
  }

  function compatibleVersion(minimum, current) {
    var expected = String(minimum).match(/^(\d+)\.(\d+)\.(\d+)$/)
    var installed = String(current).match(/^(\d+)\.(\d+)\.(\d+)$/)
    if (!expected || !installed) return false
    for (var index = 1; index <= 3; index += 1) {
      var requiredPart = parseInt(expected[index], 10)
      var currentPart = parseInt(installed[index], 10)
      if (currentPart > requiredPart) return true
      if (currentPart < requiredPart) return false
    }
    return true
  }

  function acceptStatus(value) {
    if (!validStatus(value)) return false
    document = value
    available = true
    error = ""
    return true
  }

  function refresh() {
    if (refreshing || statusProcess.running || token === "") return
    refreshing = true
    statusProcess.command = [
      "curl", "-fsS", "--max-time", "3",
      "-H", "X-FAM-Widget-Token: " + token,
      endpoint + "/api/v1/status"
    ]
    statusProcess.running = true
  }

  function connectEvents() {
    if (token === "" || eventSocket.status === WebSocket.Open
        || eventSocket.status === WebSocket.Connecting) return
    eventSocket.url = socketUrl
    eventSocket.active = true
  }

  function scheduleReconnect() {
    eventSocket.active = false
    reconnectTimer.interval = reconnectDelayMs
    reconnectTimer.restart()
    reconnectDelayMs = Math.min(30000, reconnectDelayMs * 2)
  }

  function action(operation, content) {
    if (!activeGoal || actionProcess.running || token === "") return
    pendingAction = operation
    var payload = {commandId: commandId()}
    if (operation === "guidance") payload.content = String(content || "")
    runAction(
      endpoint + "/api/v1/goals/" + encodeURIComponent(activeGoal.goalId)
        + "/" + operation,
      payload
    )
  }

  function runAction(url, payload) {
    actionProcess.command = [
      "curl", "-fsS", "--max-time", "4", "-X", "POST",
      "-H", "Content-Type: application/json",
      "-H", "X-FAM-Widget-Token: " + token,
      "--data", JSON.stringify(payload), url
    ]
    actionProcess.running = true
  }

  function openConsole() {
    if (token === "" || actionProcess.running) return
    pendingAction = "console-open"
    runAction(endpoint + "/api/v1/console/open", {commandId: commandId()})
  }

  function openCandidate() {
    if (!activeGoal || token === "" || actionProcess.running) return
    pendingAction = "candidate-open"
    runAction(endpoint + "/api/v1/candidate/open", {
      commandId: commandId(), goalId: activeGoal.goalId
    })
  }

  FileView {
    id: tokenFile
    path: root.tokenPath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: { root.refresh(); root.connectEvents() }
  }

  FileView {
    id: descriptorFile
    path: root.descriptorPath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: { root.refresh(); root.connectEvents() }
  }

  Timer {
    interval: root.refreshInterval
    repeat: true
    running: true
    triggeredOnStart: true
    onTriggered: {
      tokenFile.reload()
      descriptorFile.reload()
      root.refresh()
      root.connectEvents()
    }
  }

  Timer {
    id: reconnectTimer
    repeat: false
    onTriggered: root.connectEvents()
  }

  WebSocket {
    id: eventSocket
    active: false
    onStatusChanged: {
      if (status === WebSocket.Open) {
        root.reconnectDelayMs = 1000
        root.refresh()
      } else if (status === WebSocket.Closed || status === WebSocket.Error) {
        root.scheduleReconnect()
      }
    }
    onTextMessageReceived: function(message) {
      if (String(message).length > 65536) {
        root.scheduleReconnect()
        return
      }
      try {
        if (!root.acceptStatus(JSON.parse(String(message)))) root.error = ""
      } catch (failure) {
        // Malformed events are ignored; the conservative GET fallback repairs state.
      }
    }
  }

  Process {
    id: statusProcess
    running: false
    command: []
    stdout: StdioCollector { id: statusOutput; waitForEnd: true }
    onExited: function(code) {
      root.refreshing = false
      if (code !== 0) {
        root.available = false
        root.error = ""
        return
      }
      try {
        if (!root.acceptStatus(JSON.parse(String(statusOutput.text || "{}")))) {
          root.available = false
          root.error = ""
        }
      } catch (failure) {
        root.available = false
        root.error = ""
      }
    }
  }

  Process {
    id: actionProcess
    running: false
    command: []
    stderr: StdioCollector { id: actionError; waitForEnd: true }
    onExited: function(code) {
      root.pendingAction = ""
      root.error = code === 0
        ? ""
        : String(actionError.text || "FAM action failed").trim()
      root.refresh()
    }
  }
}
