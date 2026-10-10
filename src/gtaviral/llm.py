from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from typing import IO, Protocol

from gtaviral.config import Config, resolve_tool


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def chat_json(self, system: str, user: str, schema: dict) -> dict: ...


class LlamaClient:
    def __init__(self, base_url: str, timeout: float = 600.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=2) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def chat_json(self, system: str, user: str, schema: dict, temperature: float = 0.3) -> dict:
        body = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "response_format": {"type": "json_schema", "json_schema": {"name": "saida", "schema": schema}},
        }
        last_error = ""
        for _ in range(2):
            req = urllib.request.Request(
                f"{self.base_url}/v1/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    payload = json.loads(r.read().decode("utf-8"))
                result = json.loads(payload["choices"][0]["message"]["content"])
                if isinstance(result, dict):
                    return result
                last_error = "resposta fora do formato: não é um objeto JSON"
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
                last_error = f"resposta fora do formato: {e}"
            except (urllib.error.URLError, OSError) as e:
                last_error = f"falha de conexão com o LLM: {e}"
        raise LLMError(last_error)


class LlamaServer:
    """Sobe o llama-server se ele não estiver no ar e o encerra na saída (só se foi ele que subiu)."""

    def __init__(self, cfg: Config, startup_timeout: float = 240.0) -> None:
        self.cfg = cfg
        self.client = LlamaClient(f"http://127.0.0.1:{cfg.llm_port}")
        self.startup_timeout = startup_timeout
        self.log_path = cfg.work_dir / "llama-server.log"
        self.proc: subprocess.Popen | None = None
        self._log: IO[str] | None = None

    def __enter__(self) -> LlamaClient:
        if self.client.health():
            return self.client
        exe = resolve_tool(self.cfg.llama_server)
        if exe is None:
            raise LLMError("llama-server não encontrado — rode: gtaviral verificar")
        if not self.cfg.llm_model.is_file():
            raise LLMError(f"modelo do LLM não encontrado: {self.cfg.llm_model} — rode: gtaviral verificar")
        self.cfg.work_dir.mkdir(parents=True, exist_ok=True)
        self._log = self.log_path.open("w", encoding="utf-8", errors="replace")
        self.proc = subprocess.Popen(
            [str(exe), "-m", str(self.cfg.llm_model), "--host", "127.0.0.1", "--port", str(self.cfg.llm_port),
             "-ngl", "99", "-c", "16384"],
            stdout=self._log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                code = self.proc.returncode
                self._stop()
                raise LLMError(f"llama-server fechou ao iniciar (código {code}):\n{self._tail()}")
            if self.client.health():
                return self.client
            time.sleep(1)
        self._stop()
        raise LLMError(f"llama-server não respondeu em {self.startup_timeout:.0f}s (log: {self.log_path})")

    def __exit__(self, *exc) -> bool:
        self._stop()
        return False

    def _stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.proc = None
        if self._log is not None:
            self._log.close()
            self._log = None

    def _tail(self) -> str:
        try:
            return "\n".join(self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-15:])
        except OSError:
            return "(sem log)"
