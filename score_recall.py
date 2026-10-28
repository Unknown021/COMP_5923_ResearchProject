"""Score recall trials by normalized string match against the answer and aliases.

A trial is flagged for manual review when nothing matches (the model may have paraphrased),
when the answer follows a negation ("Clover. Not Thistlewick."), or when the response also
names another fact's answer (confusion). Control trials are flagged only if they match.
Manual decisions go in
results/scored/<run_name>.overrides.yaml and are applied on every run, so the scored file
can always be regenerated:

    "Q4_K_M|example|1536|main|1|f02": {correct: true, note: "said 'fourteenth day of Harrowmoot'"}

Input:  results/raw/<run_name>.jsonl
Output: results/scored/<run_name>.jsonl (recall trials only)
"""

import argparse
import json
import re

import yaml

from common import ROOT, load_config, load_yaml, read_jsonl


def normalize(text):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


NEGATION = r"\b(?:not|no|never|isn t|wasn t|ain t)\b(?:\s+\w+){0,2}\s+"


def mentions(response, term):
    return re.search(rf"\b{re.escape(normalize(term))}\b", normalize(response)) is not None


def negated(response, term):
    """The answer appears within a few words after a negation ("Clover. Not Thistlewick.")."""
    return re.search(rf"{NEGATION}{re.escape(normalize(term))}\b", normalize(response)) is not None


def score(response, fact, other_facts, control=False):
    """Return (correct, needs_review, reason).

    In the control condition the transcript holds no facts, so a miss is expected and only
    a match (a lucky guess or leakage) is flagged.
    """
    terms = [fact["canonical_answer"], *fact["accepted_aliases"]]
    correct = any(mentions(response, t) for t in terms)
    if control:
        return correct, correct, "control matched" if correct else None
    if not correct:
        return False, True, "no match"
    if any(negated(response, t) for t in terms):
        return True, True, "answer appears after a negation"
    confused = [f["id"] for f in other_facts if mentions(response, f["canonical_answer"])]
    if confused:
        return True, True, f"also names answer of {', '.join(confused)}"
    return True, False, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/experiment.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    run = cfg["run_name"]

    overrides_path = ROOT / cfg["paths"]["scored"] / f"{run}.overrides.yaml"
    overrides = {}
    if overrides_path.exists():
        with open(overrides_path, encoding="utf-8") as f:
            overrides = yaml.safe_load(f) or {}

    facts_by_char = {}
    out = ROOT / cfg["paths"]["scored"] / f"{run}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    n = n_correct = n_review = n_override = 0
    with open(out, "w", encoding="utf-8") as f:
        for trial in read_jsonl(f"{cfg['paths']['raw']}/{run}.jsonl"):
            if trial["probe_type"] != "recall":
                continue
            name = trial["character"]
            if name not in facts_by_char:
                facts_by_char[name] = {x["id"]: x for x in load_yaml(f"{cfg['paths']['facts']}/{name}.yaml")["facts"]}
            facts = facts_by_char[name]
            fact = facts[trial["probe_id"]]
            others = [x for x in facts.values() if x["id"] != fact["id"]]

            auto_correct, needs_review, reason = score(trial["response"], fact, others,
                                                       control=trial["condition"] == "control")
            record = {**trial, "auto_correct": auto_correct, "needs_review": needs_review,
                      "review_reason": reason, "correct": auto_correct, "override_note": None}
            if trial["trial_id"] in overrides:
                o = overrides[trial["trial_id"]]
                record.update(correct=o["correct"], needs_review=False, override_note=o.get("note"))
                n_override += 1
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

            n += 1
            n_correct += record["correct"]
            n_review += record["needs_review"]

    print(f"{run}: scored {n} recall trials, {n_correct} correct, {n_override} overridden, "
          f"{n_review} awaiting review -> {out.relative_to(ROOT)}")
    if n_review:
        print(f"review flagged trials and record decisions in {overrides_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
