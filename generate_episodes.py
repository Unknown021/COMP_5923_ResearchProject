"""Draft filler episodes for a scenario with Claude (prompts/episode_generation.md).

Every fact answer and alias in facts/<scenario>.yaml is forbidden in the filler; episodes
that contain one anyway, or whose assistant turns have no name-prefixed line, are rejected
and reported rather than saved. Accepted episodes are written one per file, numbered after
any already present, and each call is recorded in generation_log.jsonl next to them.

Review the episodes before building transcripts: they are study materials.

Output: episodes/<scenario>/ep_NNN.json, episodes/<scenario>/generation_log.jsonl
"""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone

from claude_judge import call_claude
from common import ROOT, append_jsonl, first_name, load_config, load_scenario, load_yaml, render_card

SYSTEM = "You write vivid, consistent roleplay filler for a research dataset. Follow the constraints exactly."

_turn = {
    "type": "object",
    "properties": {"role": {"type": "string", "enum": ["user", "assistant"]}, "content": {"type": "string"}},
    "required": ["role", "content"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {"episodes": {"type": "array", "items": {
        "type": "object",
        "properties": {"title": {"type": "string"}, "turns": {"type": "array", "items": _turn}},
        "required": ["title", "turns"],
        "additionalProperties": False,
    }}},
    "required": ["episodes"],
    "additionalProperties": False,
}


def forbidden_terms(facts):
    return sorted({t for f in facts for t in [f["canonical_answer"], *f["accepted_aliases"]]})


def problems(episode, terms, names):
    """Reasons to reject an episode (empty list = accept)."""
    found = []
    text = " ".join(t["content"] for t in episode["turns"]).lower()
    found += [f"uses forbidden term '{t}'" for t in terms if re.search(rf"\b{re.escape(t.lower())}\b", text)]
    roles = [t["role"] for t in episode["turns"]]
    if not roles or roles[0] != "user" or any(a == b for a, b in zip(roles, roles[1:])):
        found.append("turns do not alternate user/assistant starting with user")
    prefix = re.compile(rf"^\s*(?:{'|'.join(map(re.escape, names))}):", re.MULTILINE)
    if any(t["role"] == "assistant" and not prefix.search(t["content"]) for t in episode["turns"]):
        found.append("an assistant turn has no name-prefixed line")
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/experiment.yaml")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--count", type=int, default=12, help="episodes to request in this call")
    ap.add_argument("--tokens-per-episode", type=int, default=350)
    args = ap.parse_args()
    cfg = load_config(args.config)

    scenario = load_scenario(cfg, args.scenario)
    cards = list(scenario["cards"].values())
    names = [first_name(c) for c in cards]
    facts = load_yaml(f"{cfg['paths']['facts']}/{args.scenario}.yaml")["facts"]
    terms = forbidden_terms(facts)

    with open(ROOT / "prompts" / "episode_generation.md", encoding="utf-8") as f:
        template = f.read()
    prompt = template.format(
        setting=scenario["setting"].strip(),
        character_profiles="\n\n".join(render_card(c) for c in cards),
        n_episodes=args.count,
        tokens_per_episode=args.tokens_per_episode,
        format_example=f"{names[0]}: *spits into the reeds* \"Too high. Ferry'll charge double.\"\n"
                       f"{names[1]}: \"According to the river charts, it should fall by morning.\"",
        n_characters=len(cards),
        forbidden_terms=", ".join(terms),
    )

    out_dir = ROOT / cfg["paths"]["episodes"] / args.scenario
    out_dir.mkdir(parents=True, exist_ok=True)
    next_index = len(list(out_dir.glob("ep_*.json"))) + 1

    print(f"requesting {args.count} episodes from {cfg['generator']['model']} ...")
    result, model = call_claude(cfg["generator"], SYSTEM, prompt, SCHEMA)

    accepted, rejected = [], []
    for episode in result["episodes"]:
        reasons = problems(episode, terms, names)
        if reasons:
            rejected.append((episode["title"], reasons))
            continue
        ep_id = f"{args.scenario}_e{next_index:03d}"
        with open(out_dir / f"ep_{next_index:03d}.json", "w", encoding="utf-8") as f:
            json.dump({"id": ep_id, "title": episode["title"], "turns": episode["turns"]}, f,
                      ensure_ascii=False, indent=1)
        accepted.append(ep_id)
        next_index += 1

    append_jsonl(f"{cfg['paths']['episodes']}/{args.scenario}/generation_log.jsonl", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model, "backend": cfg["generator"]["backend"], "effort": cfg["generator"]["effort"],
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "requested": args.count, "accepted": accepted,
        "rejected": [{"title": t, "reasons": r} for t, r in rejected],
    })
    print(f"accepted {len(accepted)}, rejected {len(rejected)} -> {out_dir.relative_to(ROOT)}")
    for title, reasons in rejected:
        print(f"  rejected '{title}': {'; '.join(reasons)}")


if __name__ == "__main__":
    main()
