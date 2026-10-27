"""Tables and plots from scored recall and judged persona results.

Recall: accuracy per (quant, depth, position band) with Wilson 95% CIs;
        logistic model correct ~ quant * depth + position (+ character/fact effects).
Persona: score per (quant, depth) vs. Q8_0; length as covariate.
Judge validation: agreement with hand scores, self-consistency.
"""

import argparse

from common import load_config


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config/experiment.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    # TODO
    raise NotImplementedError


if __name__ == "__main__":
    main()
