import QtQuick
import qs.Commons
import qs.Ui

BarWidget {
  id: root

  moduleName: "fam.os"

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }

  function refresh() {
    if (panelLoader.item && panelLoader.item.refresh)
      panelLoader.item.refresh()
  }

  function togglePanel() {
    if (panelLoader.item && panelLoader.item.toggle)
      panelLoader.item.toggle()
  }

  readonly property bool opened: panelLoader.item
    ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item
    ? panelLoader.item.popoutSwitchClosing === true : false

  function open() {
    if (panelLoader.item && panelLoader.item.openFromHotkey)
      panelLoader.item.openFromHotkey()
  }

  function close() {
    if (panelLoader.item && panelLoader.item.close)
      panelLoader.item.close()
  }

  function closeForPopoutSwitch() {
    if (panelLoader.item && panelLoader.item.closeForPopoutSwitch)
      panelLoader.item.closeForPopoutSwitch()
  }

  visible: panelLoader.item !== null
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "F"
    tooltipText: panelLoader.item && panelLoader.item.goal
      ? String(panelLoader.item.goal.title || "FAM") + " · "
        + panelLoader.item.status.replace(/_/g, " ")
      : "FAM · ready"
    opacity: panelLoader.item && panelLoader.item.goal ? pulseOpacity : 0.62
    property real pulseOpacity: 1.0
    readonly property bool goalActive: panelLoader.item
      && panelLoader.item.goal
      && ["running", "queued", "retry_wait"].indexOf(panelLoader.item.status) >= 0

    SequentialAnimation {
      running: button.goalActive
      loops: Animation.Infinite
      NumberAnimation {
        target: button
        property: "pulseOpacity"
        to: 0.5
        duration: 850
        easing.type: Easing.InOutSine
      }
      NumberAnimation {
        target: button
        property: "pulseOpacity"
        to: 1.0
        duration: 850
        easing.type: Easing.InOutSine
      }
    }

    Canvas {
      id: progressRing
      anchors.centerIn: parent
      width: Math.min(parent.width, parent.height) - 5
      height: width
      antialiasing: true
      readonly property var goal: panelLoader.item ? panelLoader.item.goal : null
      readonly property string status: panelLoader.item
        ? panelLoader.item.status : "idle"
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
      onGoalChanged: requestPaint()
      onPaint: {
        var context = getContext("2d")
        context.reset()
        if (!goal || status === "idle" || status === "draft") return
        var color = root.bar ? root.bar.barForeground : Color.foreground
        if (status === "retry_wait") color = "#d6a64f"
        else if (status === "paused") color = "#8f88b8"
        else if (status === "failed")
          color = root.bar ? root.bar.urgent : Color.urgent
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
      else root.togglePanel()
    }
  }
}
