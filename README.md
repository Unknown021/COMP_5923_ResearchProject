# COMP 5923 Research Project

Does the GGUF quantization level of Llama-3.1-8B-Instruct affect its ability to recall facts and
stay in character at different context depths in a roleplay setting?

## Layout

```
config/experiment.yaml   quants, depths, seeds, sampler params, server build (one file per run)
scenarios/<id>.yaml      a shared story: setting + the characters the model voices together
characters/<id>.yaml     character cards (system prompt), judge anchors, persona probe
facts/<scenario>.yaml    15 facts per scenario with probes, answers, aliases
episodes/<scenario>/     Claude-generated multi-character filler episodes + generation log
prompts/                 judge, adjudicator and episode-generation prompts (paper appendix)
transcripts/             assembled transcripts + fact-offset manifests
results/raw|scored|judged  JSONL, one line per trial
claude_judge.py          shared claude -p / API call for judging and generation
common.py                config loading, I/O, llama-server client
```

## Pipeline

```
python generate_episodes.py --scenario caravan   # drafts filler with Claude; review before use
python build_transcripts.py   # starts llama-server briefly for the model's tokenizer
python run_inference.py       # starts/stops llama-server per quant
python score_recall.py        # manual decisions: results/scored/<run>.overrides.yaml
python judge_persona.py       # judge.backend cli: claude -p (Claude Code login); api: ANTHROPIC_API_KEY
python analyze.py
```

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Requires a llama.cpp release build (`server.binary` in the config; pilot and full run both use b11936,
win-cuda-12.4-x64 locally). Download every quant from one GGUF repo into a folder outside the repo,
then set `model.source`, `model.dir` and the quant filenames in `config/experiment.yaml`.
