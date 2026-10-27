"""Blind persona judging with Claude.

The judge sees only: character card, persona probe, response. Items carry a
random ID and are judged in shuffled order, each in a fresh context. The
mapping from judge ID back to trial metadata stays local.

Input:  results/raw/<run_name>.jsonl (persona trials only)
Output: results/judged/<run_name>.jsonl
"""

import argparse

from common import load_config


def build_prompt(template, card, probe, response):
    # TODO: fill prompts/judge_persona.md, including per-character anchors
    raise NotImplementedError


def judge_api(cfg, prompt):
    """Call the Anthropic API (key from ANTHROPIC_API_KEY); return parsed JSON."""
    # TODO
    raise NotImplementedError


def judge_cli(cfg, prompt):
    """Fallback: `claude -p` on the subscription; return parsed JSON."""
    # TODO
    raise NotImplementedError


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config/experiment.yaml")
    ap.add_argument("--repeat-fraction", type=float, default=0.0,
                    help="fraction of items to re-judge for self-consistency")
    args = ap.parse_args()
    cfg = load_config(args.config)
    # TODO: select persona trials, assign random IDs, shuffle, judge, write
    raise NotImplementedError


if __name__ == "__main__":
    main()
