"""One-shot, schema-constrained Claude calls shared by the persona and recall judges.

Backends (config judge.backend):
  cli  `claude -p` with the Claude Code login: no tools, replaced system prompt, no saved
       session, run from an empty temp directory so no project files or memory load.
  api  Anthropic Python SDK with ANTHROPIC_API_KEY.
Both pin the model ID and effort and enforce a JSON schema. Current Claude models accept no
temperature setting, so repeated calls can differ.
"""

import json
import subprocess
import tempfile


def call_claude(jcfg, system, prompt, schema):
    """Send one prompt in a fresh session. Returns (parsed JSON, model that answered)."""
    if jcfg["backend"] == "cli":
        return _call_cli(jcfg, system, prompt, schema)
    if jcfg["backend"] == "api":
        return _call_api(jcfg, system, prompt, schema)
    raise ValueError(f"unknown judge.backend: {jcfg['backend']}")


def _call_cli(jcfg, system, prompt, schema):
    cmd = ["claude", "-p", "--output-format", "json", "--json-schema", json.dumps(schema),
           "--tools", "", "--no-session-persistence", "--system-prompt", system,
           "--model", jcfg["model"], "--effort", jcfg["effort"]]
    with tempfile.TemporaryDirectory() as cwd:
        result = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                                cwd=cwd, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed ({result.returncode}): {result.stderr.strip()[:500]}")
    body = json.loads(result.stdout)
    if body.get("is_error") or body.get("structured_output") is None:
        raise RuntimeError(f"claude -p returned no structured output: {body.get('result', '')[:500]}")
    models = list(body.get("modelUsage", {}))
    return body["structured_output"], models[0] if len(models) == 1 else models


def _call_api(jcfg, system, prompt, schema):
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=jcfg["model"],
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": jcfg["effort"], "format": {"type": "json_schema", "schema": schema}},
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"judge refused: {response.stop_details}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text), response.model
