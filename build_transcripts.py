"""Assemble transcripts at each depth from filler episodes + fact exchanges.

Output per (character, depth):
  transcripts/<name>_<depth>.json          message list (user/assistant turns)
  transcripts/<name>_<depth>.manifest.json actual token offset of each fact, total tokens

Requires a running llama-server for token counting (the model's own tokenizer).
"""

import argparse

from common import LlamaServer, load_config


def load_episodes(cfg, name):
    """Load episodes/<name>/*.json in filename order."""
    # TODO
    raise NotImplementedError


def assemble(episodes, facts, depth, positions, server):
    """Fill episodes up to `depth` tokens, inserting each fact exchange at its target position.

    Returns (messages, manifest).
    """
    # TODO
    raise NotImplementedError


def validate(messages, manifest, facts, depth, tolerance):
    """Each answer string appears exactly once; positions within tolerance; length within budget."""
    # TODO
    raise NotImplementedError


def build_control(episodes, depth, server):
    """Filler-only transcript: no facts (card is omitted at inference time)."""
    # TODO
    raise NotImplementedError


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config/experiment.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    server = LlamaServer(cfg["server"]["host"], cfg["server"]["port"])
    # TODO: loop characters x depths -> assemble -> validate -> write files
    raise NotImplementedError


if __name__ == "__main__":
    main()
