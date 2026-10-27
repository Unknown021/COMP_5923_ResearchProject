"""Run every trial in the config grid against llama-server; one JSONL line per trial.

Loop: quant -> (start server) -> character x depth -> seed -> probe.
Each probe is a fresh conversation: system card + transcript + one probe.

Output: results/raw/<run_name>.jsonl
"""

import argparse

from common import LlamaServer, load_config


def start_server(cfg, model_path):
    """Launch llama-server for one quant and block until /health is ready. Returns the process."""
    # TODO
    raise NotImplementedError


def stop_server(proc):
    # TODO
    raise NotImplementedError


def build_trials(cfg):
    """Expand the config grid into trial dicts (character, depth, seed, probe_type, fact_id, ...)."""
    # TODO
    raise NotImplementedError


def run_trial(server, cfg, trial):
    """Send one trial; return a record with the response, token counts and timings."""
    # TODO
    raise NotImplementedError


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config/experiment.yaml")
    ap.add_argument("--resume", action="store_true", help="skip trials already in the output file")
    args = ap.parse_args()
    cfg = load_config(args.config)
    # TODO: for each quant: hash model file, start server, run trials, stop server
    raise NotImplementedError


if __name__ == "__main__":
    main()
