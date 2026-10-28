"""Summary tables from scored recall and judged persona results.

Recall:  accuracy per (quant, depth, condition, position band) with Wilson 95% CIs.
Persona: mean score per criterion and overall per (quant, depth); repeat judgments excluded.
Judge:   self-consistency on repeated items, when there are any.

TODO (check-in #4): logistic model correct ~ quant * depth + position with character/fact
effects; ordinal persona model vs. Q8_0 with Holm correction; length covariate; plots.

Output: results/<run_name>_recall_summary.csv, results/<run_name>_persona_summary.csv
"""

import argparse

import pandas as pd
from statsmodels.stats.proportion import proportion_confint

from common import ROOT, load_config, read_jsonl

CRITERIA = ["knowledge", "speech", "traits", "hallucination"]


def recall_summary(scored):
    g = scored.groupby(["quant", "depth", "condition", "position_band"])["correct"]
    table = g.agg(n="count", correct="sum").reset_index()
    table["accuracy"] = table["correct"] / table["n"]
    lo, hi = proportion_confint(table["correct"], table["n"], method="wilson")
    table["ci_low"], table["ci_high"] = lo, hi
    return table


def persona_summary(judged):
    cols = [f"score_{c}" for c in CRITERIA] + ["score_mean", "response_tokens"]
    first = judged[~judged["repeat"]]
    table = first.groupby(["quant", "depth"])[cols].mean().round(2)
    table.insert(0, "n", first.groupby(["quant", "depth"]).size())
    return table.reset_index()


def judge_consistency(judged):
    repeats = judged[judged["repeat"]]
    if repeats.empty:
        return None
    pairs = repeats.merge(judged[~judged["repeat"]], on="trial_id", suffixes=("_2", "_1"))
    return {c: (pairs[f"score_{c}_1"] == pairs[f"score_{c}_2"]).mean() for c in CRITERIA}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/experiment.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    run = cfg["run_name"]
    pd.set_option("display.width", 200)

    scored = pd.DataFrame(read_jsonl(f"{cfg['paths']['scored']}/{run}.jsonl"))
    recall = recall_summary(scored)
    print(f"Recall accuracy ({run})\n{recall.to_string(index=False, float_format='%.2f')}\n")
    print(f"Awaiting manual review: {int(scored['needs_review'].sum())} of {len(scored)}\n")
    recall.to_csv(ROOT / "results" / f"{run}_recall_summary.csv", index=False)

    judged = pd.DataFrame(read_jsonl(f"{cfg['paths']['judged']}/{run}.jsonl"))
    persona = persona_summary(judged)
    print(f"Persona scores, 1-5 ({run})\n{persona.to_string(index=False)}\n")
    persona.to_csv(ROOT / "results" / f"{run}_persona_summary.csv", index=False)

    if (consistency := judge_consistency(judged)) is not None:
        print("Judge self-agreement on repeats: " + ", ".join(f"{c}={v:.0%}" for c, v in consistency.items()))


if __name__ == "__main__":
    main()
