"""Run every trial in the config grid against llama-server; one JSONL line per trial.

Loop: quant -> (start server) -> character x depth -> seed -> probe.
Each probe is a fresh conversation: system card + transcript + one probe. Probes for
the same transcript and seed run back to back so llama-server reuses the cached prefix.

Input:  transcripts/<name>_<depth>.json          {"messages": [...]}
        transcripts/<name>_<depth>.manifest.json {"facts": {id: {"token_offset", "relative_position"}}}
        transcripts/<name>_<depth>_control.json  (only when control.enabled)
Output: results/raw/<run_name>.jsonl, server logs in logs/
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from common import (ROOT, LlamaServer, append_jsonl, load_config, load_yaml, read_jsonl, render_card,
                    sha256_file, start_server, stop_server)


def transcript_path(cfg, name, depth, control=False):
    suffix = "_control" if control else ""
    return ROOT / cfg["paths"]["transcripts"] / f"{name}_{depth}{suffix}.json"


def build_trials(cfg, quant):
    """Expand the config grid into trial dicts for one quant, grouped by transcript then seed."""
    trials = []
    for name in cfg["characters"]:
        card = load_yaml(f"{cfg['paths']['characters']}/{name}.yaml")
        facts = load_yaml(f"{cfg['paths']['facts']}/{name}.yaml")["facts"]
        conditions = ["main"]
        if cfg["control"]["enabled"] and quant == cfg["control"]["quant"]:
            conditions.append("control")

        for depth in cfg["depths"]:
            for condition in conditions:
                path = transcript_path(cfg, name, depth, control=condition == "control")
                manifest = {}
                if condition == "main":
                    with open(path.with_suffix(".manifest.json"), encoding="utf-8") as f:
                        manifest = json.load(f)["facts"]

                for seed in cfg["seeds"]:
                    base = {"character": name, "depth": depth, "condition": condition,
                            "seed": seed, "transcript": path.name}
                    for fact in facts:
                        placed = manifest.get(fact["id"], {})
                        trials.append({
                            **base,
                            "probe_type": "recall",
                            "probe_id": fact["id"],
                            "probe": fact["probe_question"],
                            "position_band": fact["position_band"],
                            "target_position": fact["target_relative_position"],
                            "actual_position": placed.get("relative_position"),
                            "token_offset": placed.get("token_offset"),
                        })
                    # Persona is meaningless without a card, so the control runs recall only
                    if condition == "main":
                        trials.append({**base, "probe_type": "persona", "probe_id": "persona",
                                       "probe": card["persona_probe"].strip()})
    for t in trials:
        t["quant"] = quant
        t["trial_id"] = f"{quant}|{t['character']}|{t['depth']}|{t['condition']}|{t['seed']}|{t['probe_id']}"
    return trials


def build_messages(cfg, trial, transcript_cache):
    """System card (main condition only) + transcript turns + the probe as the final user turn."""
    key = trial["transcript"]
    if key not in transcript_cache:
        path = ROOT / cfg["paths"]["transcripts"] / key
        with open(path, encoding="utf-8") as f:
            transcript_cache[key] = json.load(f)["messages"]
    messages = []
    if trial["condition"] == "main":
        card = load_yaml(f"{cfg['paths']['characters']}/{trial['character']}.yaml")
        messages.append({"role": "system", "content": render_card(card)})
    messages += transcript_cache[key]
    messages.append({"role": "user", "content": trial["probe"]})
    return messages


def run_trial(server, cfg, trial, messages):
    """Send one trial; return a record with the response, token counts and timings."""
    sampling = cfg["sampling"]
    max_tokens = sampling["max_tokens_recall" if trial["probe_type"] == "recall" else "max_tokens_persona"]
    started = datetime.now(timezone.utc).isoformat()
    body = server.chat(messages, seed=trial["seed"], max_tokens=max_tokens, sampling=sampling)
    choice = body["choices"][0]
    return {
        **trial,
        "started_at": started,
        "response": choice["message"]["content"],
        "finish_reason": choice["finish_reason"],
        "prompt_tokens": body["usage"]["prompt_tokens"],
        "completion_tokens": body["usage"]["completion_tokens"],
        "timings": body.get("timings"),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config/experiment.yaml")
    ap.add_argument("--resume", action="store_true", help="skip trials already in the output file")
    ap.add_argument("--quants", nargs="*", help="run only these quants (default: all in config)")
    args = ap.parse_args()
    cfg = load_config(args.config)

    out = Path(cfg["paths"]["raw"]) / f"{cfg['run_name']}.jsonl"
    done = set()
    if (ROOT / out).exists():
        if not args.resume:
            raise SystemExit(f"{out} exists; pass --resume to continue it or change run_name")
        done = {r["trial_id"] for r in read_jsonl(out)}

    s = cfg["server"]
    server = LlamaServer(s["host"], s["port"])
    for quant, qcfg in cfg["model"]["quants"].items():
        if args.quants and quant not in args.quants:
            continue
        trials = [t for t in build_trials(cfg, quant) if t["trial_id"] not in done]
        if not trials:
            print(f"{quant}: nothing to run")
            continue

        model_path = Path(cfg["model"]["dir"]) / qcfg["file"]
        print(f"{quant}: hashing {model_path.name}")
        model_meta = {"model_file": qcfg["file"], "model_sha256": sha256_file(model_path),
                      "server_build": s["build"], "run_name": cfg["run_name"]}

        log_path = ROOT / "logs" / f"{cfg['run_name']}_{quant}_{datetime.now():%Y%m%d-%H%M%S}.log"
        print(f"{quant}: starting llama-server (log: {log_path.name})")
        proc = start_server(cfg, model_path, log_path)
        try:
            transcript_cache = {}
            for i, trial in enumerate(trials, 1):
                messages = build_messages(cfg, trial, transcript_cache)
                record = run_trial(server, cfg, trial, messages)
                append_jsonl(out, {**model_meta, **record, "server_log": log_path.name})
                print(f"{quant}: {i}/{len(trials)} {trial['trial_id']} "
                      f"({record['prompt_tokens']} + {record['completion_tokens']} tok)")
        finally:
            stop_server(proc)


if __name__ == "__main__":
    main()
