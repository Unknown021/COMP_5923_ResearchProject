"""Score recall trials by normalized string match against the answer and aliases.

Trials with no match, or with a correct and an incorrect candidate (hedging),
are flagged for manual review. Manual overrides are recorded, not silently applied.

Input:  results/raw/<run_name>.jsonl
Output: results/scored/<run_name>.jsonl
"""

import argparse
import re

from common import load_config


def normalize(text):
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def score(response, fact):
    """Return (correct: bool, needs_review: bool)."""
    # TODO
    raise NotImplementedError


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config/experiment.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    # TODO
    raise NotImplementedError


if __name__ == "__main__":
    main()
