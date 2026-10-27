"""Shared helpers: config loading, file I/O, and the llama-server client."""

import hashlib
import json
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
    """Render a character card dict into the system prompt text."""
    # TODO: finalize the system prompt format (roleplay instructions + card)
    raise NotImplementedError


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
        r = requests.post(f"{self.base}/tokenize", json={"content": text}, timeout=60)
        r.raise_for_status()
        return r.json()["tokens"]

    def count_chat_tokens(self, messages):
        """Token count of a message list after the model's chat template is applied."""
        # TODO: use /apply-template then /tokenize so counts include template tokens
        raise NotImplementedError

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
