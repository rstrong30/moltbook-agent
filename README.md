# Moltbook Agent (Dry Run)

## Purpose
Question picker for a Moltbook XRP question‑asking agent. It is **read‑only by default** and only prints the question it would post. Posting is **opt‑in** and requires explicit flags plus an API key.

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
