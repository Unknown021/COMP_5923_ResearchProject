"""Shared helpers: config loading, file I/O, and the llama-server client."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent


def load_config(path="config/experiment.yaml"):
    with open(ROOT / path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml(path):
    with open(ROOT / path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_jsonl(path):
    with open(ROOT / path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path, record):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def render_card(card):
    """Render a character card dict into the system prompt text.

    Only the in-world fields are rendered; `markers` and `persona_probe` are for scoring.
    """
    def bullets(items):
        return "\n".join(f"- {item}" for item in items)

    return (
        f"You are {card['name']}, a character in an ongoing roleplay. Stay in character at all "
        f"times and reply only as {card['name']}, in their voice.\n\n"
        f"Summary: {card['summary']}\n\n"
        f"Appearance:\n{bullets(card['physical'])}\n\n"
        f"Speech:\n{bullets(card['speech'])}\n\n"
        f"Personality:\n{bullets(card['personality'])}\n\n"
        f"Backstory: {card['backstory'].strip()}"
    )


class LlamaServer:
    """Thin client for a running llama-server instance."""

    def __init__(self, host, port):
        self.base = f"http://{host}:{port}"

    def health(self):
        try:
            return requests.get(f"{self.base}/health", timeout=5).status_code == 200
        except requests.ConnectionError:
            return False

    def tokenize(self, text):
        r = requests.post(f"{self.base}/tokenize", json={"content": text, "parse_special": True}, timeout=60)
        r.raise_for_status()
        return r.json()["tokens"]

    def apply_template(self, messages):
        r = requests.post(f"{self.base}/apply-template", json={"messages": messages}, timeout=60)
        r.raise_for_status()
        return r.json()["prompt"]

    def count_chat_tokens(self, messages):
        """Token count of a message list after the model's chat template is applied."""
        return len(self.tokenize(self.apply_template(messages)))

    def chat(self, messages, seed, max_tokens, sampling):
        r = requests.post(
            f"{self.base}/v1/chat/completions",
            json={
                "messages": messages,
                "seed": seed,
                "max_tokens": max_tokens,
                "temperature": sampling["temperature"],
                "top_p": sampling["top_p"],
                "cache_prompt": sampling["cache_prompt"],
            },
            timeout=600,
        )
        r.raise_for_status()
        return r.json()


HEALTH_TIMEOUT_S = 600


def start_server(cfg, model_path, log_path):
    """Launch llama-server for one model file and block until /health is ready. Returns the process."""
    s = cfg["server"]
    client = LlamaServer(s["host"], s["port"])
    if client.health():
        raise RuntimeError(f"a server is already listening on {s['host']}:{s['port']}; stop it first")

    cmd = [
        s["binary"], "-m", str(model_path),
        "--host", s["host"], "--port", str(s["port"]),
        "-c", str(s["ctx_size"]),
        "-np", str(s["n_parallel"]),
        "-fa", s["flash_attn"],
        "--log-file", str(log_path),
    ]
    if s["n_gpu_layers"] is not None:
        cmd += ["-ngl", str(s["n_gpu_layers"])]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + HEALTH_TIMEOUT_S
    while not client.health():
        if proc.poll() is not None:
            raise RuntimeError(f"llama-server exited with code {proc.returncode}; see {log_path}")
        if time.monotonic() > deadline:
            stop_server(proc)
            raise TimeoutError(f"llama-server not ready after {HEALTH_TIMEOUT_S}s; see {log_path}")
        time.sleep(2)
    return proc


def stop_server(proc):
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
