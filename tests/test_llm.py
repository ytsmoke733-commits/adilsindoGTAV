import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from gtaviral.llm import LlamaClient, LlamaServer, LLMError
from tests.test_doctor import make_cfg


class _Handler(BaseHTTPRequestHandler):
    responses: list = []
    requests: list = []

    def do_GET(self):
        self._send(200 if self.path == "/health" else 404, {"status": "ok"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append(body)
        code, payload = type(self).responses.pop(0)
        self._send(code, payload)

    def _send(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def completion(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


@pytest.fixture
def server():
    _Handler.responses = []
    _Handler.requests = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", _Handler
    httpd.shutdown()
    httpd.server_close()


def test_health(server):
    url, _ = server
    assert LlamaClient(url).health() is True
    assert LlamaClient("http://127.0.0.1:1").health() is False


def test_chat_json_sends_schema_and_parses(server):
    url, h = server
    h.responses = [(200, completion('{"ok": true}'))]
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    assert LlamaClient(url).chat_json("sys", "user", schema) == {"ok": True}
    sent = h.requests[0]
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["response_format"]["json_schema"]["schema"] == schema
    assert [m["role"] for m in sent["messages"]] == ["system", "user"]


def test_chat_json_retries_once_on_bad_json(server):
    url, h = server
    h.responses = [(200, completion("não é json")), (200, completion('{"ok": 1}'))]
    assert LlamaClient(url).chat_json("s", "u", {}) == {"ok": 1}
    assert len(h.requests) == 2


def test_chat_json_gives_up_after_two_failures(server):
    url, h = server
    h.responses = [(200, completion("x")), (200, completion("[1, 2]"))]
    with pytest.raises(LLMError, match="formato"):
        LlamaClient(url).chat_json("s", "u", {})


def test_llama_server_without_binary_explains(tmp_path):
    cfg = make_cfg(tmp_path, llm_port=1)
    with pytest.raises(LLMError, match="gtaviral verificar"):
        with LlamaServer(cfg):
            pass


def test_llama_server_stops_process_when_enter_is_interrupted(tmp_path, monkeypatch):
    import subprocess
    import sys

    from gtaviral import llm

    model = tmp_path / "m.gguf"
    model.write_bytes(b"x")
    exe = sys.executable
    cfg = make_cfg(tmp_path, llm_port=1, llama_server=exe, llm_model=model)
    spawned: list[subprocess.Popen] = []
    real_popen = subprocess.Popen

    def fake_popen(*args, **kwargs):
        p = real_popen([exe, "-c", "import time; time.sleep(60)"], stdout=kwargs.get("stdout"),
                       stderr=kwargs.get("stderr"))
        spawned.append(p)
        return p

    calls = {"n": 0}

    def health(self):
        calls["n"] += 1
        if calls["n"] == 1:
            return False  # antes da subida
        raise KeyboardInterrupt  # interrompido durante a espera

    monkeypatch.setattr(llm.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(llm.LlamaClient, "health", health)
    with pytest.raises(KeyboardInterrupt):
        with LlamaServer(cfg):
            pass
    assert len(spawned) == 1
    assert spawned[0].poll() is not None


@pytest.mark.integration
def test_real_llama_server_returns_schema_json(real_cfg):
    schema = {"type": "object", "properties": {"traducao": {"type": "string"}}, "required": ["traducao"]}
    with LlamaServer(real_cfg) as llm:
        out = llm.chat_json("Traduza para português do Brasil.", "Bro, look at this car.", schema)
    assert isinstance(out["traducao"], str) and out["traducao"]
