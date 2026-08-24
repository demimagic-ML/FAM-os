"""Threaded lifecycle for deterministic per-enforcement CONNECT proxies."""

from datetime import datetime, timezone
import socket
from threading import Event, Lock, Thread, current_thread

from fam_os.supervisor.network_proxy import (
    BoundedConnectProxySession, NetworkByteQuota,
)


class ThreadedConnectProxyRuntime:
    def __init__(self, *, clock=None, resolver=None, dialer=None):
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._resolver, self._dialer = resolver, dialer
        self._running, self._lock = {}, Lock()

    def start(
        self, identity, bind_host, destinations, maximum_bytes, expires_at,
        observer,
    ):
        return self.start_many(
            identity, (bind_host,), destinations, maximum_bytes, expires_at,
            observer,
        )[0][1]

    def start_many(
        self, identity, bind_hosts, destinations, maximum_bytes, expires_at,
        observer,
    ):
        if not bind_hosts or len(set(bind_hosts)) != len(bind_hosts):
            raise ValueError("network proxy bind hosts must be nonempty and unique")
        with self._lock:
            if identity in self._running:
                raise FileExistsError("network proxy identity is already active")
            running = _RunningProxy(
                identity, tuple(bind_hosts), destinations, maximum_bytes, expires_at,
                observer, self._clock, self._resolver, self._dialer,
            )
            self._running[identity] = running
        try:
            running.start()
        except BaseException:
            with self._lock: self._running.pop(identity, None)
            raise
        return running.addresses

    def snapshot(self, identity):
        running = self._require(identity)
        return running.quota.snapshot()

    def active(self, identity):
        return self._require(identity).active()

    def stop(self, identity):
        with self._lock:
            running = self._running.pop(identity, None)
        if running is None:
            raise FileNotFoundError("network proxy identity is not active")
        running.stop()
        return running.quota.snapshot()

    def recover(self, identity, fallback):
        with self._lock:
            present = identity in self._running
        return self.stop(identity) if present else fallback

    def _require(self, identity):
        with self._lock:
            value = self._running.get(identity)
        if value is None:
            raise FileNotFoundError("network proxy identity is not active")
        return value


class _RunningProxy:
    def __init__(
        self, identity, host, destinations, maximum, expires_at, observer,
        clock, resolver, dialer,
    ):
        if expires_at.tzinfo is None or expires_at <= clock():
            raise PermissionError("network proxy expiry is inactive")
        self.identity, self.expires_at = identity, expires_at
        self._clock, self._stop = clock, Event()
        self.quota = NetworkByteQuota(maximum, observer)
        self._session = lambda: BoundedConnectProxySession(
            destinations, self.quota, resolver=resolver, dialer=dialer,
            active=self.active,
        )
        self._listeners = self._open_listeners(host)
        self.addresses = tuple(
            (listener.getsockname()[0], listener.getsockname()[1])
            for listener in self._listeners
        )
        self.port = self.addresses[0][1]
        self._clients, self._threads, self._lock = set(), set(), Lock()
        self._thread = Thread(target=self._serve, name=identity, daemon=True)

    @staticmethod
    def _listener(host):
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        listener = socket.socket(family, socket.SOCK_STREAM)
        if family == socket.AF_INET6:
            listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        listener.bind((host, 0)); listener.listen(16); listener.settimeout(0.2)
        return listener

    @classmethod
    def _open_listeners(cls, hosts):
        listeners = []
        try:
            for host in hosts: listeners.append(cls._listener(host))
        except BaseException:
            for listener in listeners: listener.close()
            raise
        return tuple(listeners)

    def active(self):
        return not self._stop.is_set() and self._clock() < self.expires_at

    def start(self): self._thread.start()

    def stop(self):
        self._stop.set()
        for listener in self._listeners: listener.close()
        with self._lock: clients, threads = tuple(self._clients), tuple(self._threads)
        for client in clients:
            try: client.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            client.close()
        self._thread.join(timeout=2)
        for thread in threads: thread.join(timeout=2)
        if self._thread.is_alive() or any(thread.is_alive() for thread in threads):
            raise RuntimeError("network proxy did not stop within bound")

    def _serve(self):
        try:
            while self.active():
                accepted = False
                for listener in self._listeners:
                    try: client, _address = listener.accept()
                    except socket.timeout: continue
                    except OSError: continue
                    accepted = True
                    thread = Thread(target=self._client, args=(client,), daemon=True)
                    with self._lock: self._clients.add(client); self._threads.add(thread)
                    thread.start()
                if not accepted: continue
        finally:
            for listener in self._listeners: listener.close()
            with self._lock: clients = tuple(self._clients)
            for client in clients:
                try: client.shutdown(socket.SHUT_RDWR)
                except OSError: pass

    def _client(self, client):
        try: self._session().serve(client)
        except (ConnectionError, OSError, PermissionError, ValueError): pass
        finally:
            client.close()
            with self._lock:
                self._clients.discard(client); self._threads.discard(current_thread())
