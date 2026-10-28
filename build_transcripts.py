"""Assemble transcripts at each depth from filler episodes + fact exchanges.

Filler episodes are flattened into exchanges (a user turn and the assistant reply). Exchanges
are added in order until the next one would exceed the depth budget; each fact exchange is
inserted at the exchange boundary nearest its target position. Depth and positions
are measured in tokens of the prompt as the model sees it: chat template + system card +
transcript, excluding the probe.

Output per (character, depth):
  transcripts/<name>_<depth>.json          {"messages": [...]} (no system message)
  transcripts/<name>_<depth>.manifest.json total tokens + each fact's actual offset
  transcripts/<name>_<depth>_control.json  filler only, no facts (when control.enabled)

Starts llama-server with the first quant in the config to use the model's own tokenizer.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from common import ROOT, LlamaServer, load_config, load_yaml, render_card, start_server, stop_server

# Template tokens around one message in the Llama 3 chat format (header + role + eot)
MESSAGE_OVERHEAD = 5
MIN_FILL = 0.90


def load_episodes(cfg, name):
    """Load episodes/<name>/*.json in filename order; a file holds one episode or a list."""
    episodes = []
    for path in sorted((ROOT / cfg["paths"]["episodes"] / name).glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        episodes += data if isinstance(data, list) else [data]
    return episodes


def to_exchanges(episodes):
    """Split episodes into exchanges: a user turn plus the assistant turns that follow it."""
    exchanges = []
    for episode in episodes:
        for turn in episode["turns"]:
            if turn["role"] == "user" or not exchanges:
                exchanges.append([])
            exchanges[-1].append({"role": turn["role"], "content": turn["content"]})
    return exchanges


def estimate_tokens(server, exchange):
    return sum(len(server.tokenize(m["content"])) + MESSAGE_OVERHEAD for m in exchange)


def assemble(server, system, exchanges, facts, depth):
    """Fill exchanges up to `depth` tokens, inserting facts at their targets. Returns (messages, inserted fact ids)."""
    pending = sorted(facts, key=lambda f: f["target_relative_position"])
    current = server.count_chat_tokens(system)
    messages, placed = [], []
    for exchange in exchanges:
        cost = estimate_tokens(server, exchange)
        # Insert at whichever boundary (before or after this exchange) is nearer the target
        while pending and pending[0]["target_relative_position"] * depth < current + cost / 2:
            fact = pending.pop(0)
            placed.append((fact["id"], len(messages)))
            messages += fact["introducing_exchange"]
            current += estimate_tokens(server, fact["introducing_exchange"])
        if current + cost > depth:
            break
        messages += exchange
        current += cost
    else:
        raise ValueError(f"ran out of filler at ~{current} of {depth} tokens; add more episodes")
    if pending:
        raise ValueError(f"facts {[f['id'] for f in pending]} did not fit before the depth budget")
    return messages, placed


def measure(server, system, messages, placed):
    """Exact token offsets: template the prefix before each fact's first turn and count it."""
    total = server.count_chat_tokens(system + messages)
    facts = {}
    for fact_id, index in placed:
        offset = server.count_chat_tokens(system + messages[:index])
        facts[fact_id] = {"message_index": index, "token_offset": offset,
                          "relative_position": round(offset / total, 4)}
    return {"total_tokens": total, "facts": facts}


def count_term(messages, term):
    text = " ".join(m["content"] for m in messages).lower()
    return len(re.findall(rf"\b{re.escape(term.lower())}\b", text))


def validate(messages, manifest, facts, depth, tolerance, control=False):
    """Answers appear once (zero in the control); positions within tolerance; length within budget."""
    errors = []
    for fact in facts:
        expected = 0 if control else 1
        if (n := count_term(messages, fact["canonical_answer"])) != expected:
            errors.append(f"{fact['id']}: '{fact['canonical_answer']}' appears {n} times, expected {expected}")
        for alias in fact["accepted_aliases"]:
            if (n := count_term(messages, alias)) > expected:
                errors.append(f"{fact['id']}: alias '{alias}' appears {n} times, at most {expected} allowed")
        if not control:
            actual = manifest["facts"][fact["id"]]["relative_position"]
            if abs(actual - fact["target_relative_position"]) > tolerance:
                errors.append(f"{fact['id']}: at {actual:.3f}, target {fact['target_relative_position']} "
                              f"(tolerance {tolerance})")
    total = manifest["total_tokens"]
    if not MIN_FILL * depth <= total <= depth:
        errors.append(f"total {total} tokens outside [{int(MIN_FILL * depth)}, {depth}]")
    return errors


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/experiment.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)

    s = cfg["server"]
    server = LlamaServer(s["host"], s["port"])
    first_quant = next(iter(cfg["model"]["quants"].values()))
    model_path = Path(cfg["model"]["dir"]) / first_quant["file"]
    log_path = ROOT / "logs" / f"build_transcripts_{datetime.now():%Y%m%d-%H%M%S}.log"
    print(f"starting llama-server for tokenization ({model_path.name})")
    proc = start_server(cfg, model_path, log_path)

    out_dir = ROOT / cfg["paths"]["transcripts"]
    out_dir.mkdir(parents=True, exist_ok=True)
    failed = False
    try:
        for name in cfg["characters"]:
            card = load_yaml(f"{cfg['paths']['characters']}/{name}.yaml")
            facts = load_yaml(f"{cfg['paths']['facts']}/{name}.yaml")["facts"]
            exchanges = to_exchanges(load_episodes(cfg, name))
            system = [{"role": "system", "content": render_card(card)}]

            for depth in cfg["depths"]:
                variants = [("main", system, facts)]
                if cfg["control"]["enabled"]:
                    variants.append(("control", [], []))
                for condition, sys_msgs, used_facts in variants:
                    messages, placed = assemble(server, sys_msgs, exchanges, used_facts, depth)
                    manifest = measure(server, sys_msgs, messages, placed)
                    errors = validate(messages, manifest, facts, depth, cfg["position_tolerance"],
                                      control=condition == "control")

                    stem = f"{name}_{depth}" + ("_control" if condition == "control" else "")
                    write_json(out_dir / f"{stem}.json",
                               {"character": name, "depth": depth, "condition": condition, "messages": messages})
                    write_json(out_dir / f"{stem}.manifest.json",
                               {**manifest, "validation_errors": errors})

                    positions = ", ".join(f"{k}@{v['relative_position']:.3f}" for k, v in manifest["facts"].items())
                    status = "OK" if not errors else "FAILED"
                    print(f"{stem}: {manifest['total_tokens']} tokens, {len(messages)} messages "
                          f"[{positions or 'no facts'}] {status}")
                    for e in errors:
                        print(f"  - {e}")
                    failed |= bool(errors)
    finally:
        stop_server(proc)
    if failed:
        raise SystemExit("validation failed; see errors above (also saved in the manifests)")


if __name__ == "__main__":
    main()
