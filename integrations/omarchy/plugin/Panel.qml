import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import qs.Commons

Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool opened: false
  readonly property var goal: fam.activeGoal
  readonly property string status: goal
    ? String(goal.status || "idle") : "idle"

  function open(payloadJson) {
    try { JSON.parse(payloadJson || "{}") } catch (failure) {}
    opened = true
    fam.refresh()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  function close() { opened = false }

  function dismiss() {
    if (shell && typeof shell.hide === "function")
      shell.hide((manifest && manifest.id) || "fam.os")
    else close()
  }

  function duration(seconds) {
    var total = Math.max(0, Number(seconds || 0))
    var hours = Math.floor(total / 3600)
    var minutes = Math.floor((total % 3600) / 60)
    var secs = Math.floor(total % 60)
    return (hours > 0 ? String(hours).padStart(2, "0") + ":" : "")
      + String(minutes).padStart(2, "0") + ":"
      + String(secs).padStart(2, "0")
  }

  function memory(bytes) {
    return bytes ? (Number(bytes) / 1073741824).toFixed(1) + " GiB" : "—"
  }

  function activity(value) {
    if (!value) return "—"
    var when = new Date(String(value))
    if (isNaN(when.getTime())) return "—"
    var seconds = Math.max(0, Math.floor((Date.now() - when.getTime()) / 1000))
    if (seconds < 5) return "live"
    if (seconds < 60) return String(seconds) + "s ago"
    if (seconds < 3600) return String(Math.floor(seconds / 60)) + "m ago"
    return String(Math.floor(seconds / 3600)) + "h ago"
  }

  function retryTime(value) {
    if (!value) return "—"
    var when = new Date(String(value))
    if (isNaN(when.getTime())) return "—"
    return "in " + String(Math.max(
      0, Math.ceil((when.getTime() - Date.now()) / 1000)
    )) + "s"
  }

  FamService { id: fam }

  PanelWindow {
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "fam-os-panel"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    Rectangle {
      anchors.fill: parent
      color: Qt.rgba(0.025, 0.035, 0.045, 0.76)
      MouseArea { anchors.fill: parent; onClicked: root.dismiss() }
    }

    Item {
      id: keyCatcher
      anchors.fill: parent
      focus: true
      Keys.onEscapePressed: root.dismiss()

      Rectangle {
        id: card
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 560)
        height: Math.min(parent.height - 64, content.implicitHeight + 56)
        radius: 18
        color: "#11171d"
        border.width: 1
        border.color: "#33404a"

        MouseArea {
          anchors.fill: parent
          acceptedButtons: Qt.AllButtons
          onClicked: function(mouse) { mouse.accepted = true }
        }

        ColumnLayout {
          id: content
          anchors.fill: parent
          anchors.margins: 28
          spacing: 18

          RowLayout {
            Layout.fillWidth: true
            Text {
              text: "FAM"
              color: "#f0f4f6"
              font.family: Style.font.family
              font.pixelSize: 24
              font.weight: Font.DemiBold
              font.letterSpacing: 2
            }
            Item { Layout.fillWidth: true }
            Rectangle {
              implicitWidth: statusText.implicitWidth + 20
              implicitHeight: 28
              radius: 14
              color: root.status === "failed" ? "#3b2020"
                : root.status === "retry_wait" ? "#3d3420" : "#19352c"
              Text {
                id: statusText
                anchors.centerIn: parent
                text: root.status.toUpperCase().replace(/_/g, " ")
                color: root.status === "failed" ? "#ff8d81"
                  : root.status === "retry_wait" ? "#e8c775" : "#74d7b2"
                font.family: Style.font.family
                font.pixelSize: 11
                font.weight: Font.DemiBold
              }
            }
          }

          Text {
            Layout.fillWidth: true
            text: root.goal
              ? String(root.goal.title || "Active goal")
              : (fam.available ? "Ready for a goal" : "FAM service unavailable")
            color: "#f0f4f6"
            wrapMode: Text.WordWrap
            font.family: Style.font.family
            font.pixelSize: 19
          }

          Rectangle {
            visible: root.goal !== null
            Layout.fillWidth: true
            implicitHeight: metrics.implicitHeight + 32
            radius: 12
            color: "#172028"
            border.width: 1
            border.color: "#26333d"

            GridLayout {
              id: metrics
              anchors.fill: parent
              anchors.margins: 16
              columns: 4
              columnSpacing: 16
              rowSpacing: 12

              Repeater {
                model: root.goal ? [
                  ["PHASE", String(root.goal.phase || "—")],
                  ["ELAPSED", root.duration(root.goal.elapsedSeconds)],
                  ["MODEL", String(root.goal.model || "—")],
                  ["ACTIVITY", root.activity(root.goal.lastActivityAt)],
                  ["PLAN", String(root.goal.plan.current) + " / " + String(root.goal.plan.total)],
                  ["CHECKS", String(root.goal.checks.passed) + " / " + String(root.goal.checks.total)],
                  ["CHANGES", String(root.goal.candidateChanges || 0)],
                  ["RECOVERY", root.status === "retry_wait"
                    ? root.retryTime(root.goal.nextRetryAt)
                    : String(root.goal.recoveryAttempt || 0)],
                  ["RAM", root.memory(fam.document.resources.ramBytesUsed)],
                  ["VRAM", root.memory(fam.document.resources.vramBytesUsed)]
                ] : []
                delegate: ColumnLayout {
                  id: metric
                  required property var modelData
                  Layout.fillWidth: true
                  spacing: 3
                  Text {
                    text: metric.modelData[0]
                    color: "#73828d"
                    font.family: Style.font.family
                    font.pixelSize: 9
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1
                  }
                  Text {
                    Layout.maximumWidth: 112
                    text: metric.modelData[1]
                    color: "#d7e0e5"
                    elide: Text.ElideRight
                    font.family: Style.font.family
                    font.pixelSize: 13
                  }
                }
              }
            }
          }

          Text {
            visible: fam.error !== ""
            Layout.fillWidth: true
            text: fam.error
            color: "#ff8d81"
            wrapMode: Text.WordWrap
            font.family: Style.font.family
            font.pixelSize: 12
          }

          RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Button { text: "Console"; onClicked: fam.openConsole() }
            Button {
              text: "Candidate"
              enabled: root.goal !== null
              onClicked: fam.openCandidate()
            }
            Item { Layout.fillWidth: true }
            Button {
              text: "Pause"
              enabled: root.goal && ["queued", "running", "retry_wait"].indexOf(root.status) >= 0
              onClicked: fam.action("pause", "")
            }
            Button {
              text: "Resume"
              enabled: root.status === "paused"
              onClicked: fam.action("resume", "")
            }
            Button {
              text: "Cancel"
              enabled: root.goal && ["completed", "failed", "cancelled"].indexOf(root.status) < 0
              onClicked: fam.action("cancel", "")
            }
          }

          RowLayout {
            visible: root.goal !== null
              && ["completed", "failed", "cancelled"].indexOf(root.status) < 0
            Layout.fillWidth: true
            spacing: 10
            TextField {
              id: guidance
              Layout.fillWidth: true
              placeholderText: "Guide the active goal"
              onAccepted: {
                if (text.trim() !== "") {
                  fam.action("guidance", text.trim())
                  text = ""
                }
              }
            }
            Button {
              text: "Send"
              enabled: guidance.text.trim() !== "" && fam.pendingAction === ""
              onClicked: {
                fam.action("guidance", guidance.text.trim())
                guidance.text = ""
              }
            }
          }
        }
      }
    }
  }
}
