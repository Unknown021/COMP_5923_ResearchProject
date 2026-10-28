"""Score recall trials: string match first, Claude for the ambiguous ones, human overrides last.

1. Automatic match: normalized response contains the answer or an accepted alias.
2. A trial is flagged when nothing matches (the model may have paraphrased), when the answer
   follows a negation ("Clover. Not Thistlewick."), or when the response also names another
   fact's answer. Control trials are flagged only if they match.
3. Flagged trials go to a blind Claude adjudicator (prompts/judge_recall.md) that sees only
   the question, the answer, and the reply. Verdicts are cached in
   results/scored/<run_name>.adjudications.jsonl, so re-running costs nothing.
4. Human decisions in results/scored/<run_name>.overrides.yaml take precedence. Entries for
   adjudicated trials double as the validation sample for the adjudicator:

       "Q3_K_M|caravan|4096|main|1|f11": {correct: false, note: "asserted Clover"}

A flagged trial with no adjudication and no override has correct = null and is excluded
from analysis.

Input:  results/raw/<run_name>.jsonl
Output: results/scored/<run_name>.jsonl (recall trials only)
"""

import argparse
import json
import re
from datetime import datetime, timezone

import yaml

from claude_judge import call_claude
from common import ROOT, append_jsonl, load_config, load_yaml, read_jsonl

NEGATION = r"\b(?:not|no|never|isn t|wasn t|ain t)\b(?:\s+\w+){0,2}\s+"

ADJUDICATOR_SYSTEM = "You are a careful, impartial grader of factual recall. Follow the instructions exactly."
ADJUDICATOR_SCHEMA = {
    "type": "object",
    "properties": {"reason": {"type": "string"}, "correct": {"type": "boolean"}},
    "required": ["reason", "correct"],
    "additionalProperties": False,
}


def normalize(text):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def mentions(response, term):
    return re.search(rf"\b{re.escape(normalize(term))}\b", normalize(response)) is not None


def negated(response, term):
    """The answer appears within a few words after a negation."""
    return re.search(rf"{NEGATION}{re.escape(normalize(term))}\b", normalize(response)) is not None


def auto_score(response, fact, other_facts, control=False):
    """Return (match, flag_reason). flag_reason is None when the match can be trusted."""
    terms = [fact["canonical_answer"], *fact["accepted_aliases"]]
    match = any(mentions(response, t) for t in terms)
    if control:
        return match, "control matched" if match else None
    if not match:
        return False, "no match"
    if any(negated(response, t) for t in terms):
        return True, "answer appears after a negation"
    confused = [f["id"] for f in other_facts if mentions(response, f["canonical_answer"])]
    if confused:
        return True, f"also names answer of {', '.join(confused)}"
    return True, None


def adjudicate(jcfg, template, trial, fact):
    prompt = template.format(
        question=trial["probe"],
        canonical_answer=fact["canonical_answer"],
        aliases="\n".join(fact["accepted_aliases"]) or "(none)",
        response=trial["response"],
    )
    verdict, model = call_claude(jcfg, ADJUDICATOR_SYSTEM, prompt, ADJUDICATOR_SCHEMA)
    return {"trial_id": trial["trial_id"], "correct": verdict["correct"], "reason": verdict["reason"],
            "judge_model": model, "judge_backend": jcfg["backend"], "judge_effort": jcfg["effort"],
            "judged_at": datetime.now(timezone.utc).isoformat()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/experiment.yaml")
    ap.add_argument("--no-adjudicate", action="store_true", help="skip Claude; flagged trials stay unresolved")
    args = ap.parse_args()
    cfg = load_config(args.config)
    run = cfg["run_name"]
    scored_dir = cfg["paths"]["scored"]

    overrides_path = ROOT / scored_dir / f"{run}.overrides.yaml"
    overrides = {}
    if overrides_path.exists():
        with open(overrides_path, encoding="utf-8") as f:
            overrides = yaml.safe_load(f) or {}

    adjudications_path = f"{scored_dir}/{run}.adjudications.jsonl"
    adjudications = {}
    if (ROOT / adjudications_path).exists():
        adjudications = {a["trial_id"]: a for a in read_jsonl(adjudications_path)}
    with open(ROOT / "prompts" / "judge_recall.md", encoding="utf-8") as f:
        template = f.read()

    facts_by_scenario = {}
    records = []
    for trial in read_jsonl(f"{cfg['paths']['raw']}/{run}.jsonl"):
        if trial["probe_type"] != "recall":
            continue
        name = trial["scenario"]
        if name not in facts_by_scenario:
            facts_by_scenario[name] = {x["id"]: x for x in load_yaml(f"{cfg['paths']['facts']}/{name}.yaml")["facts"]}
        facts = facts_by_scenario[name]
        fact = facts[trial["probe_id"]]
        others = [x for x in facts.values() if x["id"] != fact["id"]]

        match, flag = auto_score(trial["response"], fact, others, control=trial["condition"] == "control")
        tid = trial["trial_id"]
        if flag and tid not in adjudications and tid not in overrides and not args.no_adjudicate:
            print(f"adjudicating {tid} ({flag})")
            adjudications[tid] = adjudicate(cfg["judge"], template, trial, fact)
            append_jsonl(adjudications_path, adjudications[tid])

        adj = adjudications.get(tid) if flag else None
        override = overrides.get(tid)
        if override is not None:
            correct, source = override["correct"], "override"
        elif not flag:
            correct, source = match, "auto"
        elif adj is not None:
            correct, source = adj["correct"], "adjudicator"
        else:
            correct, source = None, "unresolved"

        records.append({**trial, "auto_match": match, "flag_reason": flag,
                        "adjudicator_correct": adj["correct"] if adj else None,
                        "adjudicator_reason": adj["reason"] if adj else None,
                        "override_correct": override["correct"] if override else None,
                        "override_note": override.get("note") if override else None,
                        "correct": correct, "score_source": source})

    out = ROOT / scored_dir / f"{run}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    counts = {s: sum(r["score_source"] == s for r in records) for s in ("auto", "adjudicator", "override", "unresolved")}
    print(f"{run}: scored {len(records)} recall trials -> {out.relative_to(ROOT)}")
    print("  by source: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"  correct: {sum(r['correct'] is True for r in records)}")
    if counts["unresolved"]:
        print(f"  {counts['unresolved']} unresolved trials will be excluded from analysis")


if __name__ == "__main__":
    main()
