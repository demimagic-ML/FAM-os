import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Panel {
  id: root

  moduleName: "fam.os"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root
  readonly property var goal: fam.activeGoal
  readonly property string status: goal ? String(goal.status || "idle") : "idle"
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  function refresh() { fam.refresh() }

  function openFromHotkey() {
    root.controller.show()
    fam.refresh()
  }

  function toggle() {
    if (root.opened) root.close()
    else root.openFromHotkey()
  }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.barIdentity, direction)
    return false
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

  onOpenedChanged: if (opened) {
    fam.refresh()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  FamService { id: fam; settings: root.settings }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(420))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(590))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: guidance.activeFocus
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(text) {
        if (text === "r" || text === "R") fam.refresh()
      }

      Flickable {
        anchors.fill: parent
        contentWidth: width
        contentHeight: content.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ColumnLayout {
          id: content
          width: parent.width
          spacing: Style.space(14)

          PanelHero {
            Layout.fillWidth: true
            title: "FAM"
            meta: root.status.toUpperCase().replace(/_/g, " ")
            detail: root.goal ? String(root.goal.phase || "") : "READY"
            foreground: root.foreground
            fontFamily: root.fontFamily
            iconComponent: Component {
              Text {
                text: "F"
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.display
                font.bold: true
              }
            }
          }

          Text {
            Layout.fillWidth: true
            text: root.goal
              ? String(root.goal.title || "Active goal")
              : (fam.available ? "Ready for a goal" : "FAM service unavailable")
            color: root.foreground
            wrapMode: Text.WordWrap
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
          }

          PanelSeparator { Layout.fillWidth: true; foreground: root.foreground }

          PanelSectionHeader {
            Layout.fillWidth: true
            text: "LIVE GOAL"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          GridLayout {
            visible: root.goal !== null
            Layout.fillWidth: true
            columns: 4
            columnSpacing: Style.space(12)
            rowSpacing: Style.space(10)

            Repeater {
              model: root.goal ? [
                ["ELAPSED", root.duration(root.goal.elapsedSeconds)],
                ["MODEL", String(root.goal.model || "—")],
                ["ACTIVITY", root.activity(root.goal.lastActivityAt)],
                ["CHANGES", String(root.goal.candidateChanges || 0)],
                ["PLAN", String(root.goal.plan.current) + " / " + String(root.goal.plan.total)],
                ["CHECKS", String(root.goal.checks.passed) + " / " + String(root.goal.checks.total)],
                ["RECOVERY", root.status === "retry_wait"
                  ? root.retryTime(root.goal.nextRetryAt)
                  : String(root.goal.recoveryAttempt || 0)],
                ["RAM", root.memory(fam.document.resources.ramBytesUsed)]
              ] : []
              delegate: ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                spacing: Style.space(2)
                Text {
                  text: modelData[0]
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                  font.letterSpacing: 1
                }
                Text {
                  Layout.maximumWidth: Style.space(92)
                  text: modelData[1]
                  color: root.foreground
                  elide: Text.ElideRight
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                }
              }
            }
          }

          Text {
            visible: fam.error !== ""
            Layout.fillWidth: true
            text: fam.error
            color: root.urgent
            wrapMode: Text.WordWrap
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
          }

          RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(8)
            Button {
              text: "Console"; iconText: "󰆍"; bordered: true
              foreground: root.foreground; onClicked: fam.openConsole()
            }
            Button {
              text: "Candidate"; iconText: "󰉋"; bordered: true
              foreground: root.foreground; enabled: root.goal !== null
              onClicked: fam.openCandidate()
            }
            Item { Layout.fillWidth: true }
            PanelActionButton {
              iconText: "󰏤"; tooltipText: "Pause goal"
              foreground: root.foreground
              enabled: root.goal && ["queued", "running", "retry_wait"].indexOf(root.status) >= 0
              onClicked: fam.action("pause", "")
            }
            PanelActionButton {
              iconText: "󰐊"; tooltipText: "Resume goal"
              foreground: root.foreground; enabled: root.status === "paused"
              onClicked: fam.action("resume", "")
            }
            PanelActionButton {
              iconText: "󰅖"; tooltipText: "Cancel goal"
              foreground: root.urgent
              enabled: root.goal && ["completed", "failed", "cancelled"].indexOf(root.status) < 0
              onClicked: fam.action("cancel", "")
            }
          }

          RowLayout {
            visible: root.goal !== null
              && ["completed", "failed", "cancelled"].indexOf(root.status) < 0
            Layout.fillWidth: true
            spacing: Style.space(8)
            TextField {
              id: guidance
              Layout.fillWidth: true
              placeholderText: "Guide the active goal"
              foreground: root.foreground
              onAccepted: {
                if (text.trim() !== "") {
                  fam.action("guidance", text.trim())
                  text = ""
                }
              }
            }
            Button {
              text: "Send"
              foreground: root.foreground
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
