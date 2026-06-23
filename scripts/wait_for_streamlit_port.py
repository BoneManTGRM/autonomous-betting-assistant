from __future__ import annotations

import socket
import sys
import time


def wait_for_port(host: str = "127.0.0.1", port: int = 8501, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    last_error: OSError | None = None
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(2)
            try:
                sock.connect((host, port))
                print(f"{host}:{port} is accepting connections")
                return
            except OSError as exc:
                last_error = exc
                time.sleep(2)
    raise RuntimeError(f"Timed out waiting for {host}:{port}; last_error={last_error}")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8501
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 90
    wait_for_port(host, port, timeout)
