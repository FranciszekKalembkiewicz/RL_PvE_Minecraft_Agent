"""TCP JSON client for WaveArena plugin."""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        root = Path(__file__).resolve().parent.parent
        path = root / "configs" / "waves.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class BridgeClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5555,
        timeout: float = 10.0,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None

    def connect(self) -> None:
        self.close()
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        self._sock = sock

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def send_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(2):
            try:
                if self._sock is None:
                    self.connect()
                assert self._sock is not None
                line = json.dumps(payload, separators=(",", ":")) + "\n"
                self._sock.sendall(line.encode("utf-8"))
                buf = b""
                while b"\n" not in buf:
                    chunk = self._sock.recv(4096)
                    if not chunk:
                        raise ConnectionError("Bridge connection closed")
                    buf += chunk
                response_line = buf.split(b"\n", 1)[0]
                return json.loads(response_line.decode("utf-8"))
            except (TimeoutError, ConnectionError, OSError):
                self.close()
                if attempt == 0:
                    continue
                raise
        raise ConnectionError("Bridge send failed")

    def reset(self) -> dict[str, Any]:
        return self.send_command({"cmd": "reset"})

    def step(self, action: int) -> dict[str, Any]:
        return self.send_command({"cmd": "step", "action": int(action)})

    def status(self) -> dict[str, Any]:
        return self.send_command({"cmd": "status"})

    def reload_config(self) -> dict[str, Any]:
        return self.send_command({"cmd": "reload"})

    @classmethod
    def from_config(cls, cfg: dict[str, Any] | None = None) -> "BridgeClient":
        if cfg is None:
            cfg = load_config()
        bridge = cfg.get("bridge", {})
        return cls(
            host=bridge.get("host", "127.0.0.1"),
            port=int(bridge.get("port", 5555)),
            timeout=float(bridge.get("connect_timeout_sec", 10.0)),
        )
