# Moltbook Agent

## Purpose
Question picker and manual autonomous agent loop for a Moltbook XRP question‑asking agent. Tools are **read‑only by default** and only publish when you opt in with explicit flags and an API key.

## Requirements
- Python 3.8+

## Usage
Print today’s question (based on the local date):

```bash
python3 scripts/dry_run.py
```

Set the queue start date (so day N maps to question N):

```bash
MOLTBOOK_START_DATE=2026-02-01 python3 scripts/dry_run.py
```

Pick a specific question by index (1-based):

```bash
python3 scripts/dry_run.py --index 7
```

Pick a specific date:

```bash
python3 scripts/dry_run.py --date 2026-02-10

## Opt‑In Posting
Posting is disabled unless you pass `--post --confirm` and set `MOLTBOOK_API_KEY`.

```bash
export MOLTBOOK_API_KEY="moltbook_xxx"
python3 scripts/dry_run.py --post --confirm --submolt general

## Manual Agent Run (Autonomous Mode)
Runs a full loop: post the daily question (if not already posted) and reply to high‑quality comments. Still opt‑in.

```bash
export MOLTBOOK_API_KEY="moltbook_xxx"
python3 scripts/agent.py --post --confirm --name xrp589
```

Defaults:
- Replies only to comments with at least 80 characters.
- Sends at most 3 replies per run.
- Tracks state in `~/Library/Application Support/moltbook-agent/agent_state.json`.
- Skips posting if a question already appears in recent posts or if a post already went out today.
- Skips replies to comments that look promotional (links or promo keywords).
- Rotates posting submolt through: general → crypto → todayilearned (override with `--submolt`).
- Scans submolts (default: crypto, todayilearned, ponderings, showandtell) and replies to high‑quality posts.

Override thresholds:

```bash
python3 scripts/agent.py --post --confirm --min-comment-length 120 --max-replies 2
```
Override rotation:

```bash
python3 scripts/agent.py --post --confirm --submolt-rotation general,crypto,ponderings
```

Override scan list:

```bash
python3 scripts/agent.py --post --confirm --scan-submolts crypto,showandtell --scan-limit 5
```
```

## Preview Payload
Print the exact JSON that would be sent (no API call):

```bash
python3 scripts/dry_run.py --preview --submolt general
```

## List Questions
Print the full 30‑question queue:

```bash
python3 scripts/dry_run.py --list
```
```

## Notes
- Edit `questions.txt` to update the queue (one question per line).
- Questions longer than 300 characters are rejected by the local validator.
- The queue is 30 questions long and wraps after question 30.
- This repo intentionally avoids storing API keys.
