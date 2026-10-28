"""Blind persona judging with Claude.

Each persona trial targets one character of a multi-character scenario. The judge scores only
that character's lines, against their own card, on five criteria; the other characters' cards
are supplied only for the distinctness (character-bleed) criterion. The judge never sees the
transcript, depth, or quantization level. Items get a
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
from common import ROOT, append_jsonl, first_name, load_config, load_scenario, read_jsonl, render_card

CRITERIA = ["knowledge", "speech", "traits", "hallucination", "distinctness"]
ANCHORED = CRITERIA[:4]  # character-specific anchors; distinctness uses a generic rubric

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
    "properties": {**{c: _criterion for c in CRITERIA},
                   "target_absent": {"type": "boolean"}, "broke_character": {"type": "boolean"}},
    "required": [*CRITERIA, "target_absent", "broke_character"],
    "additionalProperties": False,
}


def build_prompt(template, scenario, target_id, probe, response):
    card = scenario["cards"][target_id]
    others = [c for cid, c in scenario["cards"].items() if cid != target_id]
    return template.format(
        target_name=card["name"],
        target_first_name=first_name(card),
        target_card=render_card(card),
        other_cards="\n\n".join(render_card(c) for c in others),
        scene_prompt=probe,
        response=response,
        **{f"anchors_{c}": card["judge_anchors"][c].strip() for c in ANCHORED},
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

    scenarios = {}
    for i, (trial, repeat) in enumerate(queue, 1):
        name = trial["scenario"]
        if name not in scenarios:
            scenarios[name] = load_scenario(cfg, name)
        prompt = build_prompt(template, scenarios[name], trial["character"], trial["probe"], trial["response"])
        judge_id = uuid.uuid4().hex[:12]
        judgment, model = call_claude(jcfg, JUDGE_SYSTEM, prompt, SCHEMA)

        scores = {c: judgment[c]["score"] for c in CRITERIA}
        append_jsonl(out, {
            "judge_id": judge_id,
            "trial_id": trial["trial_id"],
            "repeat": repeat,
            "quant": trial["quant"],
            "scenario": name,
            "character": trial["character"],
            "depth": trial["depth"],
            "seed": trial["seed"],
            **{f"score_{c}": s for c, s in scores.items()},
            "score_mean": sum(scores.values()) / len(scores),
            "target_absent": judgment["target_absent"],
            "broke_character": judgment["broke_character"],
            "response_chars": len(trial["response"]),
            "response_tokens": trial["completion_tokens"],
            "judgment": judgment,
            "judge_backend": jcfg["backend"],
            "judge_model": model,
            "judge_effort": jcfg["effort"],
            "judged_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"{i}/{len(queue)} judged {judge_id} [{trial['character']}]{' (repeat)' if repeat else ''}: "
              + " ".join(f"{c}={s}" for c, s in scores.items()))


if __name__ == "__main__":
    main()
