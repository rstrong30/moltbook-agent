#!/usr/bin/env python3
"""Autonomous Moltbook agent loop (manual run, opt-in posting)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://www.moltbook.com/api/v1"
MAX_QUESTION_LENGTH = 300
DEFAULT_MIN_COMMENT_LENGTH = 80
DEFAULT_MAX_REPLIES = 3
DEFAULT_SUBMOLT_ROTATION = ["general", "crypto", "todayilearned"]
DEFAULT_SCAN_SUBMOLTS = ["crypto", "todayilearned", "ponderings", "showandtell"]


def default_state_path() -> str:
    return os.path.expanduser(
        "~/Library/Application Support/moltbook-agent/agent_state.json"
    )


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_questions() -> list[str]:
    questions_path = os.path.join(repo_root(), "questions.txt")
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


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {
            "last_post_date": None,
            "last_post_id": None,
            "replied_comment_ids": [],
            "commented_post_ids": [],
            "last_run_at": None,
            "submolt_rotation_index": 0,
        }
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_state(path: str, state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
    except PermissionError:
        print(f"Warning: could not write state file at {path}.")


def request_json(url: str, api_key: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = None
    headers = {"Authorization": f"Bearer {api_key}"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def check_claimed(api_key: str) -> bool:
    data = request_json(f"{API_BASE}/agents/status", api_key)
    return data.get("status") == "claimed"


def post_question(api_key: str, submolt: str, question: str) -> dict:
    payload = {"submolt": submolt, "title": question, "content": question}
    return request_json(f"{API_BASE}/posts", api_key, method="POST", payload=payload)


def get_profile(api_key: str, name: str) -> dict:
    return request_json(f"{API_BASE}/agents/profile?name={name}", api_key)


def get_post(api_key: str, post_id: str) -> dict:
    return request_json(f"{API_BASE}/posts/{post_id}", api_key)


def get_submolt_feed(api_key: str, submolt: str, limit: int = 10) -> list[dict]:
    data = request_json(f"{API_BASE}/submolts/{submolt}/feed?sort=new&limit={limit}", api_key)
    if isinstance(data, dict) and "posts" in data:
        return data.get("posts", [])
    return data if isinstance(data, list) else []


def get_comments(api_key: str, post_id: str) -> list[dict]:
    try:
        data = request_json(f"{API_BASE}/posts/{post_id}/comments?sort=new", api_key)
        if isinstance(data, dict) and "comments" in data:
            return data.get("comments", [])
        return data if isinstance(data, list) else []
    except urllib.error.HTTPError as error:
        if error.code != 405:
            raise
    post = get_post(api_key, post_id)
    return post.get("comments", []) if isinstance(post, dict) else []


def is_high_quality(comment: dict, min_length: int) -> bool:
    content = (comment.get("content") or "").strip()
    if len(content) < min_length:
        return False
    words = [word for word in content.split() if word.isalnum()]
    if len(words) < 8:
        return False
    if content.count("http://") + content.count("https://") > 1:
        return False
    return True


def is_post_high_quality(post: dict, min_length: int) -> bool:
    title = (post.get("title") or "").strip()
    content = (post.get("content") or "").strip()
    text = f"{title} {content}".strip()
    if len(text) < min_length:
        return False
    if text.count("http://") + text.count("https://") > 1:
        return False
    return True


def is_promotional(comment: dict) -> bool:
    content = (comment.get("content") or "").lower()
    if not content:
        return False
    if "http://" in content or "https://" in content:
        return True
    promo_keywords = [
        "subscribe",
        "newsletter",
        "rss",
        "follow",
        "join",
        "invite",
        "discord",
        "telegram",
        "airdrop",
        "promo",
        "promotion",
        "sponsored",
        "api",
        "curl",
        "browse:",
        "click",
        "watch",
    ]
    return any(keyword in content for keyword in promo_keywords)


def is_promotional_post(post: dict) -> bool:
    title = (post.get("title") or "").lower()
    content = (post.get("content") or "").lower()
    text = f"{title} {content}".strip()
    if not text:
        return False
    if "http://" in text or "https://" in text:
        return True
    promo_keywords = [
        "subscribe",
        "newsletter",
        "rss",
        "follow",
        "join",
        "invite",
        "discord",
        "telegram",
        "airdrop",
        "promo",
        "promotion",
        "sponsored",
        "giveaway",
        "mint",
        "sale",
    ]
    return any(keyword in text for keyword in promo_keywords)


def parse_post_date(created_at: str | None) -> dt.date | None:
    if not created_at:
        return None
    try:
        return dt.datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def find_duplicate_post(posts: list[dict], question: str, today: dt.date) -> tuple[bool, str]:
    for post in posts:
        title = (post.get("title") or "").strip()
        content = (post.get("content") or "").strip()
        created_at = parse_post_date(post.get("created_at"))
        if title == question or content == question:
            return True, "question already posted recently"
        if created_at == today:
            return True, "already posted today"
    return False, ""


def choose_reply(comment_id: str, comment: dict) -> str:
    prompts = [
        "Thanks for the perspective. What concrete example or data point best supports it?",
        "Interesting take. What would you consider the strongest counterpoint?",
        "Appreciate the insight. How would you test or validate that claim?",
        "Curious angle. What would change your mind on this?",
    ]
    content = (comment.get("content") or "").strip()
    snippet = ""
    if content:
        snippet = content[:120].rstrip()
        if len(content) > 120:
            snippet += "..."
        snippet = f"You mentioned \"{snippet}\". "
    index = abs(hash(comment_id)) % len(prompts)
    return f"{snippet}{prompts[index]}"


def choose_post_reply(post_id: str, post: dict) -> str:
    prompts = [
        "Curious how you’d measure that in practice—what metric would you track first?",
        "What’s the strongest counterargument you’ve heard to this view?",
        "If you had to pick one concrete example, which would it be?",
        "What would change your mind on this over the next 6–12 months?",
    ]
    title = (post.get("title") or "").strip()
    snippet = ""
    if title:
        snippet = f"Re: \"{title[:120]}\" — "
    index = abs(hash(post_id)) % len(prompts)
    return f"{snippet}{prompts[index]}"


def post_reply(api_key: str, post_id: str, content: str, parent_id: str | None = None) -> dict:
    payload = {"content": content}
    if parent_id:
        payload["parent_id"] = parent_id
    return request_json(
        f"{API_BASE}/posts/{post_id}/comments",
        api_key,
        method="POST",
        payload=payload,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manual autonomous Moltbook agent (read-only by default).",
    )
    parser.add_argument("--name", default="xrp589", help="Agent name.")
    parser.add_argument(
        "--submolt",
        default="",
        help="Target submolt. If empty, uses rotation list.",
    )
    parser.add_argument(
        "--submolt-rotation",
        default=",".join(DEFAULT_SUBMOLT_ROTATION),
        help="Comma-separated submolt rotation list.",
    )
    parser.add_argument(
        "--scan-submolts",
        default=",".join(DEFAULT_SCAN_SUBMOLTS),
        help="Comma-separated submolts to scan for posts to reply to.",
    )
    parser.add_argument(
        "--scan-limit",
        type=int,
        default=8,
        help="Max posts per submolt to scan.",
    )
    parser.add_argument(
        "--state",
        default=default_state_path(),
        help="State file path.",
    )
    parser.add_argument(
        "--start-date",
        type=parse_date,
        help="Queue start date (YYYY-MM-DD). Defaults to env MOLTBOOK_START_DATE or today.",
    )
    parser.add_argument(
        "--min-comment-length",
        type=int,
        default=DEFAULT_MIN_COMMENT_LENGTH,
        help="Minimum comment length to reply to.",
    )
    parser.add_argument(
        "--max-replies",
        type=int,
        default=DEFAULT_MAX_REPLIES,
        help="Maximum replies per run.",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Enable posting and replies (opt-in).",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required with --post to confirm you want to publish.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("MOLTBOOK_API_KEY")
    if args.post and not api_key:
        print("Missing MOLTBOOK_API_KEY in environment.")
        return 2

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

    state = load_state(args.state)
    today = dt.date.today()
    start_env = os.environ.get("MOLTBOOK_START_DATE")
    start_date = args.start_date or (parse_date(start_env) if start_env else today)
    delta_days = (today - start_date).days
    index = delta_days + 1
    question = pick_question(questions, index)

    print(f"Selected question #{index} of {len(questions)}:")
    print(question)

    rotation = [s.strip() for s in args.submolt_rotation.split(",") if s.strip()]
    rotation = rotation or DEFAULT_SUBMOLT_ROTATION
    rotation_index = state.get("submolt_rotation_index", 0) % len(rotation)
    target_submolt = args.submolt or rotation[rotation_index]

    if args.post:
        if not args.confirm:
            print("Refusing to post without --confirm.")
            return 3
        if not check_claimed(api_key):
            print("Agent is not claimed. Aborting.")
            return 4

    posted_today = state.get("last_post_date") == today.isoformat()
    profile_posts: list[dict] = []
    if args.post:
        profile = get_profile(api_key, args.name)
        profile_posts = profile.get("recentPosts", []) if isinstance(profile, dict) else []
        is_dup, dup_reason = find_duplicate_post(profile_posts, question, today)
        if is_dup:
            print(f"Skipping post: {dup_reason}.")
            posted_today = True
    if posted_today:
        print("Post already sent today; skipping new post.")
    elif args.post:
        result = post_question(api_key, target_submolt, question)
        post_id = result.get("post", {}).get("id")
        print(f"Posted question to {target_submolt}. id={post_id}")
        state["last_post_date"] = today.isoformat()
        state["last_post_id"] = post_id
        if not args.submolt:
            state["submolt_rotation_index"] = (rotation_index + 1) % len(rotation)
    else:
        print("Dry run only. No API calls were made.")

    if not args.post:
        state["last_run_at"] = dt.datetime.utcnow().isoformat() + "Z"
        save_state(args.state, state)
        return 0

    posts = profile_posts
    if not posts:
        print("No recent posts to check for replies.")
        state["last_run_at"] = dt.datetime.utcnow().isoformat() + "Z"
        save_state(args.state, state)
        return 0

    replied_ids = set(state.get("replied_comment_ids", []))
    commented_post_ids = set(state.get("commented_post_ids", []))
    replies_sent = 0
    for post in posts[:5]:
        post_id = post.get("id")
        if not post_id:
            continue
        comments = get_comments(api_key, post_id)
        for comment in comments:
            comment_id = comment.get("id") or comment.get("comment_id")
            if not comment_id or comment_id in replied_ids:
                continue
            author = comment.get("author", {})
            if author.get("name") == args.name:
                continue
            if is_promotional(comment):
                continue
            if not is_high_quality(comment, args.min_comment_length):
                continue
            reply_text = choose_reply(str(comment_id), comment)
            post_reply(api_key, post_id, reply_text, parent_id=comment_id)
            print(f"Replied to comment {comment_id} on post {post_id}.")
            replied_ids.add(comment_id)
            replies_sent += 1
            if replies_sent >= args.max_replies:
                break
        if replies_sent >= args.max_replies:
            break

    if replies_sent < args.max_replies:
        scan_list = [s.strip() for s in args.scan_submolts.split(",") if s.strip()]
        for submolt in scan_list:
            feed_posts = get_submolt_feed(api_key, submolt, limit=args.scan_limit)
            for post in feed_posts:
                post_id = post.get("id")
                if not post_id or post_id in commented_post_ids:
                    continue
                author = post.get("author", {})
                if author.get("name") == args.name:
                    continue
                if is_promotional_post(post):
                    continue
                if not is_post_high_quality(post, args.min_comment_length):
                    continue
                reply_text = choose_post_reply(str(post_id), post)
                post_reply(api_key, post_id, reply_text)
                print(f"Replied to post {post_id} in {submolt}.")
                commented_post_ids.add(post_id)
                replies_sent += 1
                if replies_sent >= args.max_replies:
                    break
            if replies_sent >= args.max_replies:
                break

    state["replied_comment_ids"] = sorted(replied_ids)
    state["commented_post_ids"] = sorted(commented_post_ids)
    state["last_run_at"] = dt.datetime.utcnow().isoformat() + "Z"
    save_state(args.state, state)
    print(f"Replies sent: {replies_sent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
