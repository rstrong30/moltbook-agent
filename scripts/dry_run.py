#!/usr/bin/env python3
"""Question picker for Moltbook (read-only by default)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request


MAX_QUESTION_LENGTH = 300


def load_questions() -> list[str]:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    questions_path = os.path.join(repo_root, "questions.txt")
    with open(questions_path, "r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle.readlines()]
    return [line for line in lines if line and not line.startswith("#")]


def validate_questions(questions: list[str]) -> list[str]:
    errors: list[str] = []
    for i, question in enumerate(questions, start=1):
        if not question:
            errors.append(f"Question {i} is empty.")
            continue
        if len(question) > MAX_QUESTION_LENGTH:
            errors.append(
                f"Question {i} exceeds {MAX_QUESTION_LENGTH} characters ({len(question)})."
            )
    return errors


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def pick_question(questions: list[str], index: int) -> str:
    if index < 1:
        raise ValueError("index must be >= 1")
    return questions[(index - 1) % len(questions)]


def post_question(api_key: str, submolt: str, question: str) -> None:
    payload = {
        "submolt": submolt,
        "title": question,
        "content": question,
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "https://www.moltbook.com/api/v1/posts",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    print("Posted successfully:")
    print(body)

def preview_payload(submolt: str, question: str) -> None:
    payload = {
        "submolt": submolt,
        "title": question,
        "content": question,
    }
    print("Preview payload (no API call):")
    print(json.dumps(payload, indent=2))
    print("Target URL: https://www.moltbook.com/api/v1/posts")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Moltbook question picker (read-only by default).",
    )
    parser.add_argument(
        "--index",
        type=int,
        help="1-based question index to use (overrides date-based selection)",
    )
    parser.add_argument(
        "--date",
        type=parse_date,
        help="Date to select for (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--start-date",
        type=parse_date,
        help="Queue start date (YYYY-MM-DD). Defaults to env MOLTBOOK_START_DATE or today.",
    )
    parser.add_argument(
        "--submolt",
        default="general",
        help="Target submolt (default: general).",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Post the selected question to Moltbook (opt-in).",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required with --post to confirm you want to publish.",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Print the JSON payload and exit (no API call).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print all questions and exit.",
    )
    args = parser.parse_args()

    questions = load_questions()
    if not questions:
        print("No questions found in questions.txt.")
        return 1
    errors = validate_questions(questions)
    if errors:
        print("Question validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.list:
        for i, question in enumerate(questions, start=1):
            print(f"{i:02d}. {question}")
        return 0

    if args.index is not None:
        index = args.index
        selected = pick_question(questions, index)
    else:
        today = args.date or dt.date.today()
        start_env = os.environ.get("MOLTBOOK_START_DATE")
        start_date = args.start_date or (parse_date(start_env) if start_env else today)
        delta_days = (today - start_date).days
        index = delta_days + 1
        selected = pick_question(questions, index)

    print(f"Selected question #{index} of {len(questions)}:")
    print(selected)

    if args.preview:
        preview_payload(submolt=args.submolt, question=selected)
        return 0

    if not args.post:
        print("Dry run only. No API calls were made.")
        return 0

    if not args.confirm:
        print("Refusing to post without --confirm.")
        return 2

    api_key = os.environ.get("MOLTBOOK_API_KEY")
    if not api_key:
        print("Missing MOLTBOOK_API_KEY in environment.")
        return 3

    post_question(api_key=api_key, submolt=args.submolt, question=selected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
