import QtQuick
import Quickshell.Io
import qs.Ui

BarWidget {
  id: root

  moduleName: "fam.os"
  visible: fam.available
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function open() {
    if (summonProcess.running) return
    summonProcess.command = ["omarchy-shell", "shell", "summon", "fam.os", "{}"]
    summonProcess.running = true
  }

  function close() {
    if (summonProcess.running) return
    summonProcess.command = ["omarchy-shell", "shell", "hide", "fam.os"]
    summonProcess.running = true
  }

  function refresh() { fam.refresh() }

  FamService { id: fam; settings: root.settings }

  Process { id: summonProcess; running: false; command: [] }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "F"
    tooltipText: fam.activeGoal
      ? String(fam.activeGoal.title || "FAM") + " · "
        + String(fam.activeGoal.status || "idle").replace(/_/g, " ")
      : "FAM · ready"
    opacity: fam.activeGoal ? pulseOpacity : 0.62
    property real pulseOpacity: 1.0
    readonly property bool goalActive: fam.activeGoal
      && ["running", "queued", "retry_wait"].indexOf(
        String(fam.activeGoal.status)
      ) >= 0

    SequentialAnimation {
      running: button.goalActive
      loops: Animation.Infinite
      NumberAnimation {
        target: button; property: "pulseOpacity"; to: 0.5; duration: 850
        easing.type: Easing.InOutSine
      }
      NumberAnimation {
        target: button; property: "pulseOpacity"; to: 1.0; duration: 850
        easing.type: Easing.InOutSine
      }
    }

    Canvas {
      id: progressRing
      anchors.centerIn: parent
      width: Math.min(parent.width, parent.height) - 5
      height: width
      antialiasing: true
      readonly property var goal: fam.activeGoal
      readonly property string status: goal ? String(goal.status || "idle") : "idle"
      readonly property real progress: {
        if (!goal) return 0
        if (status === "completed") return 1
        var checks = goal.checks || ({passed: 0, total: 0})
        var plan = goal.plan || ({current: 0, total: 0})
        if (Number(checks.total) > 0)
          return Math.min(1, Number(checks.passed) / Number(checks.total))
        if (Number(plan.total) > 0)
          return Math.min(1, Number(plan.current) / Number(plan.total))
        return 0.08
      }
      onProgressChanged: requestPaint()
      onStatusChanged: requestPaint()
      onPaint: {
        var context = getContext("2d")
        context.reset()
        if (!goal || status === "idle" || status === "draft") return
        var color = root.bar ? root.bar.foreground : "#d8dee9"
        if (status === "retry_wait") color = "#d6a64f"
        else if (status === "paused" || status === "pause_requested") color = "#8f88b8"
        else if (status === "failed") color = "#d35f4a"
        else if (status === "completed") color = "#4d9b75"
        context.strokeStyle = color
        context.lineWidth = 1.5
        context.lineCap = "round"
        context.beginPath()
        context.arc(
          width / 2, height / 2, width / 2 - 1.5, -Math.PI / 2,
          -Math.PI / 2 + Math.PI * 2 * progress
        )
        context.stroke()
      }
    }

    onPressed: function(code) {
      if (code === Qt.MiddleButton) root.refresh()
      else root.open()
    }
  }
}
