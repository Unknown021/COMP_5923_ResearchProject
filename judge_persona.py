"""Blind persona judging with Claude.

The judge sees only the character card, the persona probe, and the response. Items get a
random judge ID and are judged in shuffled order, each in a fresh session; the mapping from
judge ID back to quant/depth stays in the local output file.

Claude is called through claude_judge.py (judge.backend: cli or api).

Input:  results/raw/<run_name>.jsonl (persona trials)
Output: results/judged/<run_name>.jsonl (resumes: already judged trials are skipped)
"""

import argparse
import random
import uuid
from datetime import datetime, timezone

from claude_judge import call_claude
from common import ROOT, append_jsonl, load_config, load_yaml, read_jsonl, render_card

CRITERIA = ["knowledge", "speech", "traits", "hallucination"]

JUDGE_SYSTEM = "You are a careful, impartial evaluator of roleplay consistency. Follow the rubric exactly."

_criterion = {
    "type": "object",
    "properties": {
        "evidence": {"type": "string"},
        "reason": {"type": "string"},
        "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    },
    "required": ["evidence", "reason", "score"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {**{c: _criterion for c in CRITERIA}, "broke_character": {"type": "boolean"}},
    "required": [*CRITERIA, "broke_character"],
    "additionalProperties": False,
}


def build_prompt(template, card, probe, response):
    anchors = card["judge_anchors"]
    return template.format(
        character_card=render_card(card),
        scene_prompt=probe,
        response=response,
        **{f"anchors_{c}": anchors[c].strip() for c in CRITERIA},
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/experiment.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    jcfg = cfg["judge"]
    run = cfg["run_name"]

    with open(ROOT / jcfg["prompt_file"], encoding="utf-8") as f:
        template = f.read()

    out = f"{cfg['paths']['judged']}/{run}.jsonl"
    done = set()
    if (ROOT / out).exists():
        done = {(r["trial_id"], r["repeat"]) for r in read_jsonl(out)}

    trials = [t for t in read_jsonl(f"{cfg['paths']['raw']}/{run}.jsonl") if t["probe_type"] == "persona"]
    rng = random.Random(jcfg["shuffle_seed"])
    rng.shuffle(trials)
    n_repeat = round(len(trials) * jcfg["repeat_fraction"])
    queue = [(t, False) for t in trials] + [(t, True) for t in rng.sample(trials, n_repeat)]
    queue = [(t, rep) for t, rep in queue if (t["trial_id"], rep) not in done]

    cards = {}
    for i, (trial, repeat) in enumerate(queue, 1):
        name = trial["character"]
        cards.setdefault(name, load_yaml(f"{cfg['paths']['characters']}/{name}.yaml"))
        prompt = build_prompt(template, cards[name], trial["probe"], trial["response"])
        judge_id = uuid.uuid4().hex[:12]
        judgment, model = call_claude(jcfg, JUDGE_SYSTEM, prompt, SCHEMA)

        scores = {c: judgment[c]["score"] for c in CRITERIA}
        append_jsonl(out, {
            "judge_id": judge_id,
            "trial_id": trial["trial_id"],
            "repeat": repeat,
            "quant": trial["quant"],
            "character": name,
            "depth": trial["depth"],
            "seed": trial["seed"],
            **{f"score_{c}": s for c, s in scores.items()},
            "score_mean": sum(scores.values()) / len(scores),
            "broke_character": judgment["broke_character"],
            "response_chars": len(trial["response"]),
            "response_tokens": trial["completion_tokens"],
            "judgment": judgment,
            "judge_backend": jcfg["backend"],
            "judge_model": model,
            "judge_effort": jcfg["effort"],
            "judged_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"{i}/{len(queue)} judged {judge_id}{' (repeat)' if repeat else ''}: "
              + " ".join(f"{c}={s}" for c, s in scores.items()))


if __name__ == "__main__":
    main()
