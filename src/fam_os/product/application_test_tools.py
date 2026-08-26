"""Stateful Playwright-backed application testing tools for the iterative agent."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fam_os.core.agent import (
    AgentToolDescriptor,
    AgentToolEffect,
    AgentToolExecution,
    AgentToolRegistry,
    ApplicationAssertionKind,
    ApplicationTestPlan,
    ApplicationTestingObjectiveCompiler,
)


class BrowserDriver(Protocol):
    @staticmethod
    def available() -> bool: ...
    def start(self, url: str, artifact_root: Path) -> dict[str, object]: ...
    def snapshot(self) -> dict[str, object]: ...
    def click(self, ref: str) -> dict[str, object]: ...
    def fill(self, ref: str, value: str) -> dict[str, object]: ...
    def select(self, ref: str, value: str) -> dict[str, object]: ...
    def press(self, key: str, ref: str | None = None) -> dict[str, object]: ...
    def screenshot(self, path: Path) -> None: ...
    def console_errors(self) -> tuple[str, ...]: ...
    def network_failures(self) -> tuple[str, ...]: ...
    def stop(self, trace_path: Path) -> dict[str, object]: ...


@dataclass(slots=True)
class ApplicationTestSession:
    session_id: str
    application_id: str
    objective: str
    workspace: str
    url: str
    launch_command: tuple[str, ...]
    process_id: int | None
    browser_identity: dict[str, object]
    cleanup_policy: str
    plan: ApplicationTestPlan
    resumed_from: str | None = None
    status: str = "running"
    current_snapshot: dict[str, object] = field(default_factory=dict)
    console_events: list[str] = field(default_factory=list)
    network_events: list[str] = field(default_factory=list)
    action_sequence: list[str] = field(default_factory=list)
    assertions: list[dict[str, object]] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    trace: str | None = None


class ApplicationTestTools:
    """Own one launch/browser/assertion lifecycle so the model does not have to."""

    def __init__(
        self, workspace_root: Path, *, objective: str,
        driver_factory= None, process_factory=subprocess.Popen,
        compiler: ApplicationTestingObjectiveCompiler | None = None,
    ) -> None:
        root = workspace_root.resolve(strict=True)
        if not root.is_dir() or root.is_symlink():
            raise PermissionError("application test workspace must be a real directory")
        self.root = root
        self.artifact_root = root / ".fam-test-artifacts"
        self.objective = objective
        self._driver_factory = driver_factory or PlaywrightBrowserDriver
        self._process_factory = process_factory
        self._compiler = compiler or ApplicationTestingObjectiveCompiler()
        self._driver: BrowserDriver | None = None
        self._process = None
        self._process_log = None
        self.session: ApplicationTestSession | None = None
        self.successful_assertions: list[str] = []

    def register(self, registry: AgentToolRegistry) -> None:
        def register(
            tool, description, effect, properties, implementation, **options,
        ) -> None:
            registry.register(
                AgentToolDescriptor(tool, description, effect, {
                    "type": "object", "properties": properties,
                    "required": list(options.get("required", ())),
                    "additionalProperties": False,
                }), implementation,
                available=options.get("available", _available),
            )
        register(
            "app_start",
            "Launch or attach to one localhost web application and create a stateful "
            "Playwright test session. Provide model-proposed checks; the harness owns "
            "their execution state, diagnostics, artifacts, and cleanup.",
            AgentToolEffect.APPLICATION_TEST,
            {
                "application_id": {"type": "string"},
                "url": {"type": "string"},
                "launch_command": {"type": "array", "items": {"type": "string"}},
                "ready_timeout_seconds": {"type": "number"},
                "checks": {"type": "array", "items": {"type": "object"}},
                "cleanup_policy": {"type": "string", "enum": ["stop_on_completion"]},
            }, self.start, required=("application_id", "url"),
            available=self._driver_available,
        )
        register("app_snapshot", "Return the current structured accessibility-oriented "
                 "snapshot and fresh short-lived element refs.", AgentToolEffect.OBSERVE,
                 {}, self.snapshot, available=self._active)
        register("app_click", "Click one element ref and automatically return the new "
                 "snapshot.", AgentToolEffect.APPLICATION_TEST,
                 {"ref": {"type": "string"}}, self.click, required=("ref",),
                 available=self._active)
        register("app_fill", "Fill one editable element ref and automatically return "
                 "the new snapshot.", AgentToolEffect.APPLICATION_TEST,
                 {"ref": {"type": "string"}, "value": {"type": "string"}},
                 self.fill, required=("ref", "value"), available=self._active)
        register("app_select", "Select an option on one element ref and return the new "
                 "snapshot.", AgentToolEffect.APPLICATION_TEST,
                 {"ref": {"type": "string"}, "value": {"type": "string"}},
                 self.select, required=("ref", "value"), available=self._active)
        register("app_press", "Press a keyboard key globally or on one element ref, then "
                 "return the new snapshot.", AgentToolEffect.APPLICATION_TEST,
                 {"key": {"type": "string"}, "ref": {"type": "string"}},
                 self.press, required=("key",), available=self._active)
        register("app_screenshot", "Capture visual evidence for layout, canvas, chart, or "
                 "game behavior; structured snapshots remain the interaction default.",
                 AgentToolEffect.APPLICATION_TEST,
                 {"name": {"type": "string"}}, self.screenshot,
                 available=self._active)
        register("app_console_errors", "Return browser console errors and uncaught page "
                 "exceptions retained by this test session.", AgentToolEffect.OBSERVE,
                 {}, self.console_errors, available=self._active)
        register("app_network_failures", "Return failed requests and HTTP error responses "
                 "retained by this test session.", AgentToolEffect.OBSERVE,
                 {}, self.network_failures, available=self._active)
        register("app_assert", "Evaluate one explicit completion check against structured "
                 "page, URL, element, console, or network evidence and persist a receipt.",
                 AgentToolEffect.APPLICATION_TEST,
                 {
                     "check_id": {"type": "string"},
                     "kind": {"type": "string", "enum": [item.value for item in ApplicationAssertionKind]},
                     "expected": {"type": "string"},
                     "ref": {"type": "string"},
                     "description": {"type": "string"},
                 }, self.assert_outcome, required=("check_id", "kind", "expected"),
                 available=self._active)
        register("app_stop", "Capture the final screenshot and trace, persist summaries, "
                 "and stop only resources created by this application-test session.",
                 AgentToolEffect.APPLICATION_TEST, {}, self.stop,
                 available=self._active)

    def start(self, arguments: dict[str, object]) -> str:
        if self._active():
            raise RuntimeError("an application test session is already active")
        application_id = _text(arguments, "application_id")
        url = _local_url(_text(arguments, "url"))
        command = _command(arguments.get("launch_command"))
        timeout = _timeout(arguments.get("ready_timeout_seconds", 60), maximum=600)
        checks = _checks(arguments.get("checks"))
        cleanup = str(arguments.get("cleanup_policy", "stop_on_completion"))
        if cleanup != "stop_on_completion":
            raise ValueError("cleanup_policy must be stop_on_completion")
        plan = self._compiler.compile(self.objective, checks)
        resumed_from = self._latest_interrupted_session()
        session_id = f"app-test-{uuid4().hex}"
        artifacts = self.artifact_root / session_id
        artifacts.mkdir(parents=True, exist_ok=False)
        pid = None
        try:
            if command:
                self._process_log = (artifacts / "process.log").open("w", encoding="utf-8")
                process_command = _sandboxed_application_command(command, self.root)
                self._process = self._process_factory(
                    process_command, cwd=self.root, stdin=subprocess.DEVNULL,
                    stdout=self._process_log, stderr=subprocess.STDOUT,
                    text=True, start_new_session=True,
                )
                pid = self._process.pid
            _wait_ready(url, timeout, self._process, artifacts / "process.log")
            self._driver = self._driver_factory()
            identity = self._driver.start(url, artifacts)
            snapshot = self._driver.snapshot()
            self.session = ApplicationTestSession(
                session_id, application_id, self.objective, str(self.root), url,
                command, pid, identity, cleanup, plan,
                resumed_from=resumed_from, current_snapshot=snapshot,
            )
            self._persist()
            return _json(self._view())
        except Exception:
            self._cleanup_process()
            raise

    def snapshot(self, _arguments: dict[str, object]) -> str:
        session, driver = self._require_active()
        session.current_snapshot = driver.snapshot()
        self._persist()
        return _json(session.current_snapshot)

    def click(self, arguments: dict[str, object]) -> str:
        return self._action("click", _text(arguments, "ref"))

    def fill(self, arguments: dict[str, object]) -> str:
        return self._action("fill", _text(arguments, "ref"), _text(arguments, "value", empty=True))

    def select(self, arguments: dict[str, object]) -> str:
        return self._action("select", _text(arguments, "ref"), _text(arguments, "value"))

    def press(self, arguments: dict[str, object]) -> str:
        ref = arguments.get("ref")
        if ref is not None and (not isinstance(ref, str) or not ref.strip()):
            raise ValueError("ref must be non-empty text when supplied")
        return self._action("press", _text(arguments, "key"), ref)

    def screenshot(self, arguments: dict[str, object]) -> AgentToolExecution:
        session, driver = self._require_active()
        name = _safe_name(str(arguments.get("name", f"screenshot-{len(session.screenshots) + 1}")))
        path = self._session_root() / f"{name}.png"
        driver.screenshot(path)
        session.screenshots.append(str(path.relative_to(self.root)))
        self._persist()
        return AgentToolExecution(_json({"screenshot": str(path.relative_to(self.root))}), {
            "verified": path.is_file() and path.stat().st_size > 0,
            "operation": "application_screenshot", "path": str(path.relative_to(self.root)),
        })

    def console_errors(self, _arguments: dict[str, object]) -> str:
        _session, driver = self._require_active()
        values = driver.console_errors()
        return _json({"count": len(values), "errors": values})

    def network_failures(self, _arguments: dict[str, object]) -> str:
        _session, driver = self._require_active()
        values = driver.network_failures()
        return _json({"count": len(values), "failures": values})

    def assert_outcome(self, arguments: dict[str, object]) -> AgentToolExecution:
        session, driver = self._require_active()
        check_id = _text(arguments, "check_id")
        kind = ApplicationAssertionKind(_text(arguments, "kind"))
        expected = _text(arguments, "expected", empty=True)
        ref = arguments.get("ref")
        snapshot = driver.snapshot()
        session.current_snapshot = snapshot
        if kind is ApplicationAssertionKind.TEXT:
            observed = str(snapshot.get("document_text", ""))
            passed = bool(expected) and expected in observed
        elif kind is ApplicationAssertionKind.URL:
            observed = str(snapshot.get("url", ""))
            passed = observed == expected
        elif kind is ApplicationAssertionKind.ELEMENT:
            observed = "present" if any(
                item.get("ref") == ref for item in snapshot.get("elements", [])
            ) else "missing"
            passed = observed == expected
        elif kind is ApplicationAssertionKind.CONSOLE_ERRORS:
            observed = str(len(driver.console_errors()))
            passed = observed == expected
        else:
            observed = str(len(driver.network_failures()))
            passed = observed == expected
        receipt = {
            "assertion": arguments.get("description") or _plan_description(session.plan, check_id),
            "check_id": check_id, "kind": kind.value,
            "action_sequence": tuple(session.action_sequence),
            "expected": expected, "observed": observed,
            "console_errors": len(driver.console_errors()),
            "network_failures": len(driver.network_failures()),
            "passed": passed,
        }
        session.assertions.append(receipt)
        if passed:
            self.successful_assertions.append(check_id)
        self._persist()
        return AgentToolExecution(_json(receipt), {
            "verified": passed, "operation": "application_assertion",
            "path": str(self._state_path().relative_to(self.root)),
            "check_id": check_id, "kind": kind.value,
        })

    def stop(self, _arguments: dict[str, object]) -> AgentToolExecution:
        session, driver = self._require_active()
        final = self._session_root() / "final.png"
        driver.screenshot(final)
        if str(final.relative_to(self.root)) not in session.screenshots:
            session.screenshots.append(str(final.relative_to(self.root)))
        trace = self._session_root() / "trace.zip"
        session.console_events = list(driver.console_errors())
        session.network_events = list(driver.network_failures())
        browser = driver.stop(trace)
        video = browser.get("video")
        if isinstance(video, str):
            video_path = Path(video)
            try:
                session.videos.append(str(video_path.relative_to(self.root)))
            except ValueError:
                session.videos.append(video)
        session.trace = str(trace.relative_to(self.root)) if trace.is_file() else None
        session.status = "completed"
        self._driver = None
        self._cleanup_process()
        self._persist()
        passed = len(self.successful_assertions)
        summary = {
            **self._view(), "browser_stop": browser,
            "passed_assertions": passed,
            "planned_checks": len(session.plan.checks),
        }
        return AgentToolExecution(_json(summary), {
            "verified": self.all_checks_passed,
            "operation": "application_test_session",
            "path": str(self._state_path().relative_to(self.root)),
            "status": "completed", "passed_assertions": passed,
        })

    def cleanup(self, *, interrupted: bool = False) -> None:
        if self._driver is not None and self.session is not None:
            try:
                if interrupted:
                    self._interrupt()
                else:
                    self.stop({})
            except Exception:
                self._driver = None
                self._cleanup_process()
        else:
            self._cleanup_process()

    @property
    def all_checks_passed(self) -> bool:
        if self.session is None:
            return False
        latest = {
            str(item["check_id"]): bool(item["passed"])
            for item in self.session.assertions
        }
        return all(
            latest.get(item.check_id, False) for item in self.session.plan.checks
        )

    @property
    def summary(self) -> dict[str, object] | None:
        """Return the persisted owner-visible session evidence, when available."""
        return None if self.session is None else self._view()

    def _interrupt(self) -> None:
        session, driver = self._require_active()
        session.console_events = list(driver.console_errors())
        session.network_events = list(driver.network_failures())
        trace = self._session_root() / "interrupted-trace.zip"
        browser = driver.stop(trace)
        session.trace = str(trace.relative_to(self.root)) if trace.is_file() else None
        video = browser.get("video")
        if isinstance(video, str):
            video_path = Path(video)
            try:
                session.videos.append(str(video_path.relative_to(self.root)))
            except ValueError:
                session.videos.append(video)
        session.status = "interrupted"
        self._driver = None
        self._cleanup_process()
        self._persist()

    def _action(self, action: str, first: str, second=None) -> str:
        session, driver = self._require_active()
        if action == "click":
            snapshot = driver.click(first)
            label = f"click {first}"
        elif action == "fill":
            snapshot = driver.fill(first, second)
            label = f"fill {first}"
        elif action == "select":
            snapshot = driver.select(first, second)
            label = f"select {first}"
        else:
            snapshot = driver.press(first, second)
            label = f"press {first}" + (f" on {second}" if second else "")
        session.action_sequence.append(label)
        session.current_snapshot = snapshot
        self._persist()
        return _json(snapshot)

    def _driver_available(self) -> bool:
        try:
            return bool(self._driver_factory.available())
        except (AttributeError, ImportError, OSError):
            return False

    def _active(self) -> bool:
        return self.session is not None and self.session.status == "running" and self._driver is not None

    def _require_active(self) -> tuple[ApplicationTestSession, BrowserDriver]:
        if not self._active() or self.session is None or self._driver is None:
            raise RuntimeError("no active application test session")
        return self.session, self._driver

    def _session_root(self) -> Path:
        if self.session is None:
            raise RuntimeError("application test session is unavailable")
        return self.artifact_root / self.session.session_id

    def _latest_interrupted_session(self) -> str | None:
        if not self.artifact_root.is_dir():
            return None
        states = sorted(
            self.artifact_root.glob("app-test-*/session.json"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for state in states:
            try:
                document = json.loads(state.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if document.get("status") == "interrupted":
                value = document.get("session_id")
                return value if isinstance(value, str) else None
            return None
        return None

    def _state_path(self) -> Path:
        return self._session_root() / "session.json"

    def _persist(self) -> None:
        state = self._state_path()
        temporary = state.with_suffix(".tmp")
        temporary.write_text(_json(self._view()) + "\n", encoding="utf-8")
        temporary.replace(state)

    def _view(self) -> dict[str, object]:
        if self.session is None:
            return {"status": "not_started", "playwright_available": self._driver_available()}
        value = asdict(self.session)
        value["plan"] = asdict(self.session.plan)
        if self._driver:
            value["console_events"] = list(self._driver.console_errors())
            value["network_events"] = list(self._driver.network_failures())
        return value

    def _cleanup_process(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        if self._process_log is not None:
            self._process_log.close()
            self._process_log = None


class PlaywrightBrowserDriver:
    """Playwright adapter using structured DOM/accessibility refs before pixels."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._generation = 0
        self._console: list[str] = []
        self._network: list[str] = []

    @staticmethod
    def available() -> bool:
        cache = Path.home() / ".cache/ms-playwright"
        cached_browser = cache.is_dir() and any(
            path.is_dir()
            for pattern in ("chromium-*", "chromium_headless_shell-*")
            for path in cache.glob(pattern)
        )
        return (
            importlib.util.find_spec("playwright.sync_api") is not None
            and (
                any(shutil.which(item) for item in (
                    "google-chrome", "chromium", "chromium-browser",
                ))
                or cached_browser
            )
        )

    def start(self, url: str, artifact_root: Path) -> dict[str, object]:
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        executable = next((
            value for value in (
                shutil.which("google-chrome"), shutil.which("chromium"),
                shutil.which("chromium-browser"),
            ) if value
        ), None)
        options = {"headless": True}
        if executable:
            options["executable_path"] = executable
        self._browser = self._playwright.chromium.launch(**options)
        video = artifact_root / "video"
        video.mkdir(exist_ok=True)
        self._context = self._browser.new_context(record_video_dir=str(video))
        self._context.tracing.start(screenshots=True, snapshots=True, sources=True)
        self._page = self._context.new_page()
        self._page.on("console", lambda message: self._console.append(
            f"{message.type}: {message.text}"
        ) if message.type == "error" else None)
        self._page.on("pageerror", lambda error: self._console.append(str(error)))
        self._page.on("requestfailed", lambda request: self._network.append(
            f"{request.method} {request.url}: {request.failure}"
        ))
        self._page.on("response", lambda response: self._network.append(
            f"HTTP {response.status} {response.url}"
        ) if response.status >= 400 else None)
        self._page.goto(url, wait_until="domcontentloaded")
        return {
            "engine": "playwright", "browser": "chromium",
            "version": self._browser.version,
            "headless": True, "structured_snapshots": True,
        }

    def snapshot(self) -> dict[str, object]:
        page = self._require_page()
        self._generation += 1
        generation = self._generation
        return page.evaluate("""generation => {
          document.querySelectorAll('[data-fam-ref]').forEach(
            element => element.removeAttribute('data-fam-ref'));
          const selectors = 'a,button,input,select,textarea,[role],[contenteditable="true"],summary';
          const elements = Array.from(document.querySelectorAll(selectors))
            .filter(element => {
              const style = getComputedStyle(element);
              const rect = element.getBoundingClientRect();
              return style.visibility !== 'hidden' && style.display !== 'none'
                && rect.width > 0 && rect.height > 0;
            }).slice(0, 256).map((element, index) => {
              const ref = `s${generation}e${index + 1}`;
              element.setAttribute('data-fam-ref', ref);
              const role = element.getAttribute('role') || ({
                A: 'link', BUTTON: 'button', INPUT: element.type || 'textbox',
                SELECT: 'combobox', TEXTAREA: 'textbox', SUMMARY: 'button'
              }[element.tagName] || element.tagName.toLowerCase());
              const name = element.getAttribute('aria-label')
                || element.getAttribute('title') || element.placeholder
                || element.innerText || element.value || element.name || '';
              return {ref, role, name: String(name).trim().slice(0, 240),
                disabled: Boolean(element.disabled), value: String(element.value || '').slice(0, 240)};
            });
          return {generation, url: location.href, title: document.title,
            document_text: String(document.body?.innerText || '').slice(0, 16000), elements};
        }""", generation)

    def click(self, ref: str) -> dict[str, object]:
        self._locator(ref).click()
        return self._settle_snapshot()

    def fill(self, ref: str, value: str) -> dict[str, object]:
        self._locator(ref).fill(value)
        return self._settle_snapshot()

    def select(self, ref: str, value: str) -> dict[str, object]:
        self._locator(ref).select_option(value)
        return self._settle_snapshot()

    def press(self, key: str, ref: str | None = None) -> dict[str, object]:
        (self._locator(ref) if ref else self._require_page().keyboard).press(key)
        return self._settle_snapshot()

    def screenshot(self, path: Path) -> None:
        self._require_page().screenshot(path=str(path), full_page=True)

    def console_errors(self) -> tuple[str, ...]:
        return tuple(self._console[-128:])

    def network_failures(self) -> tuple[str, ...]:
        return tuple(self._network[-128:])

    def stop(self, trace_path: Path) -> dict[str, object]:
        video = None if self._page is None else self._page.video
        if self._context is not None:
            self._context.tracing.stop(path=str(trace_path))
            self._context.close()
        video_path = None
        if video is not None:
            try:
                video_path = video.path()
            except Exception:
                video_path = None
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._page = self._context = self._browser = self._playwright = None
        return {
            "stopped": True, "trace": str(trace_path), "video": video_path,
        }

    def _locator(self, ref: str):
        if not ref.startswith(f"s{self._generation}e"):
            raise ValueError("element ref is stale; call app_snapshot and use a current ref")
        locator = self._require_page().locator(f'[data-fam-ref="{ref}"]')
        if locator.count() != 1:
            raise LookupError("element ref is unavailable; capture a fresh snapshot")
        return locator

    def _settle_snapshot(self) -> dict[str, object]:
        self._require_page().wait_for_timeout(100)
        return self.snapshot()

    def _require_page(self):
        if self._page is None:
            raise RuntimeError("Playwright page is not active")
        return self._page


def _local_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "localhost", "127.0.0.1", "::1",
    }:
        raise PermissionError("application tests may attach only to localhost URLs")
    return value


def _wait_ready(url: str, timeout: float, process, log_path: Path) -> None:
    deadline = time.monotonic() + timeout
    error = "application did not become ready"
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            detail = log_path.read_text(encoding="utf-8", errors="replace")[-4_000:] if log_path.exists() else ""
            raise RuntimeError(f"application process exited before readiness\n{detail}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except (OSError, urllib.error.URLError) as exception:
            error = str(exception)
        time.sleep(.2)
    raise TimeoutError(f"application readiness timed out: {error}")


def _command(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item or "\0" in item for item in value
    ):
        raise ValueError("launch_command must be a non-empty argv array")
    return tuple(value)


def _sandboxed_application_command(
    command: tuple[str, ...], workspace: Path,
) -> tuple[str, ...]:
    bubblewrap = shutil.which("bwrap")
    if bubblewrap is None:
        raise RuntimeError(
            "application launch requires bubblewrap; attach to an existing localhost "
            "URL or install the project sandbox dependency"
        )
    root = str(workspace)
    values = [
        bubblewrap, "--unshare-user", "--unshare-ipc", "--unshare-pid",
        "--unshare-uts", "--unshare-cgroup", "--die-with-parent",
        "--new-session", "--clearenv", "--cap-drop", "ALL",
        "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
        "--ro-bind-try", "/lib64", "/lib64",
        "--ro-bind-try", "/etc/hosts", "/etc/hosts",
        "--ro-bind-try", "/etc/nsswitch.conf", "/etc/nsswitch.conf",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--bind", root, root, "--chdir", root,
        "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/tmp",
        "--", *command,
    ]
    return tuple(values)


def _checks(value: object) -> tuple[dict[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("checks must be an array of objects")
    return tuple({str(key): str(item) for key, item in entry.items()} for entry in value)


def _timeout(value: object, *, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < float(value) <= maximum:
        raise ValueError("timeout is invalid")
    return float(value)


def _text(arguments: dict[str, object], key: str, *, empty: bool = False) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f"{key} must be {'text' if empty else 'non-empty text'}")
    return value if empty else value.strip()


def _safe_name(value: str) -> str:
    name = "".join(character for character in value if character.isalnum() or character in "-_").strip("-_")
    if not name or len(name) > 80:
        raise ValueError("screenshot name is invalid")
    return name


def _plan_description(plan: ApplicationTestPlan, check_id: str) -> str:
    return next((item.description for item in plan.checks if item.check_id == check_id), check_id)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)[:262_144]


def _available() -> bool:
    return True
