#!/usr/bin/env python3
"""
Generate questions with the Groq LLM and insert them into the Questions Master service.

Requirements:
  pip install requests

Env vars (loaded from .env if present):
  GROQ_API_KEY       -> API key for Groq chat/completions endpoint
  MQDB_API_KEY       -> API key for your Questions Master service (falls back to DEMO_API_KEY/MQDB_DEMO_API_KEY)
  MQDB_BASE_URL      -> Base URL for your service (e.g., http://localhost:8000/api/v1)
  GROQ_API_URL       -> Optional, default https://api.groq.com/openai/v1/chat/completions

Usage:
  python scripts/groq_question_ingest.py --subject Physics --count 5 --difficulty 2
"""

import argparse
import os
import sys
from typing import Any, Dict, List

import requests


GROQ_API_URL_DEFAULT = "https://api.groq.com/openai/v1/chat/completions"
# Prefer latest Groq models; override via GROQ_MODEL env or --model flag
GROQ_MODEL_DEFAULT = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_MODEL_FALLBACKS = ["llama-3.3-70b-versatile"]


def build_prompt(subject: str, count: int, difficulty: int) -> str:
    return f"""
Generate {count} multiple-choice questions for subject "{subject}".
Constraints:
- Difficulty (1-5): target around {difficulty}.
- Output JSON only, array of objects with fields:
  text (string), type ("single_choice"), options (array of {{id,text}} with 4 items, ids A-D),
  answer_key {{type:"single", option_id:"A"|"B"|"C"|"D"}},
  tags (array of strings)
Do not include explanations or additional text outside JSON.
"""


def call_groq(prompt: str, groq_api_key: str, groq_api_url: str, model: str) -> List[Dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a question generator. Return JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 1500,
    }
    resp = requests.post(groq_api_url, json=payload, headers=headers, timeout=60)
    if not resp.ok:
        # Surface useful info; caller can retry with a fallback model
        raise RuntimeError(
            f"Groq API error {resp.status_code}: {resp.text}\n"
            f"(model used: {model}, url: {groq_api_url})"
        )
    content = resp.json()
    # Expect Groq to return choices[0].message.content as JSON string
    msg = content["choices"][0]["message"]["content"]
    data = _parse_json_array(msg)
    return data


def _parse_json_array(raw: str) -> List[Dict[str, Any]]:
    """Parse a JSON array string, with a best-effort trim to the last closing bracket."""

    import json

    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("not a list")
        return data
    except Exception:
        # Try to salvage if trailing text/truncation occurred
        if "[" in raw and "]" in raw:
            start = raw.find("[")
            end = raw.rfind("]")
            snippet = raw[start : end + 1]
            try:
                data = json.loads(snippet)
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        raise RuntimeError(f"Failed to parse Groq response as JSON array. Raw content starts with:\n{raw[:500]}")


def sanitize_question(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Groq-generated question into a safe payload for the Questions Master."""

    text = raw.get("text", "").strip()
    qtype = raw.get("type", "single_choice") or "single_choice"
    options_raw = raw.get("options") or []

    # Ensure we have 4 options with ids A-D
    letters = ["A", "B", "C", "D"]
    options: List[Dict[str, str]] = []
    for idx, opt in enumerate(options_raw[:4]):
        oid = opt.get("id") or (letters[idx] if idx < len(letters) else str(idx + 1))
        options.append({"id": oid, "text": opt.get("text", "").strip()})
    # Pad missing options if fewer than 4
    for idx in range(len(options), 4):
        options.append({"id": letters[idx], "text": f"Option {letters[idx]}"})

    # Ensure answer_key points to a valid option
    answer_key = raw.get("answer_key") or {}
    option_id = answer_key.get("option_id")
    option_ids = {opt["id"] for opt in options}
    if option_id not in option_ids:
        option_id = options[0]["id"]

    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = []

    return {
        "text": text,
        "type": qtype,
        "options": options,
        "answer_key": {"type": answer_key.get("type", "single"), "option_id": option_id},
        "tags": tags,
    }


def post_question(q: Dict[str, Any], subject: str, difficulty: int, mqdb_base: str, mqdb_api_key: str) -> str:
    url = f"{mqdb_base}/questions"
    # Default to single_choice; prompt enforces MCQ
    qtype = q.get("type", "single_choice")
    payload = {
        "text": q["text"],
        "type": qtype,
        "options": [{"id": opt["id"], "text": opt["text"]} for opt in q["options"]],
        "answer_key": {"type": q.get("answer_key", {}).get("type", "single"), "option_id": q["answer_key"]["option_id"]},
        "solution": None,
        "taxonomy": {
            "subject_id": subject,  # map subject name/slug to your subject_id
            "topic_ids": [],
            "target_exam_ids": [],
        },
        "difficulty": difficulty,
        "tags": q.get("tags", []),
        "language": "en",
        "usage": {"status": "published", "is_active": True, "visibility": "public"},
        "meta": {"source": "groq"},
    }
    headers = {"X-API-Key": mqdb_api_key, "Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if not resp.ok:
        raise RuntimeError(
            f"Question insert failed {resp.status_code}: {resp.text}\nPayload: {payload}"
        )
    return resp.json()["question_id"]


def load_env_from_file(path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file if present and not already set."""

    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate questions with Groq and insert into Questions Master.")
    parser.add_argument("--subject", required=True, help="Subject id/slug to tag questions with")
    parser.add_argument("--count", type=int, default=5, help="Total number of questions to generate")
    parser.add_argument("--batch-size", type=int, default=10, help="Max questions to request per Groq call")
    parser.add_argument("--difficulty", type=int, default=2, help="Difficulty 1-5 to stamp on created questions")
    parser.add_argument("--api-key", dest="api_key", help="Override MQDB API key (otherwise use env)")
    parser.add_argument(
        "--model",
        default=GROQ_MODEL_DEFAULT,
        help=f"Groq model name (default from GROQ_MODEL or {GROQ_MODEL_DEFAULT}); fallbacks: {', '.join(GROQ_MODEL_FALLBACKS)}",
    )
    args = parser.parse_args()

    load_env_from_file()

    groq_api_key = os.getenv("GROQ_API_KEY")
    mqdb_api_key = args.api_key or os.getenv("MQDB_API_KEY") or os.getenv("DEMO_API_KEY") or os.getenv("MQDB_DEMO_API_KEY")
    mqdb_base = os.getenv("MQDB_BASE_URL", "http://localhost:8000/api/v1")
    groq_api_url = os.getenv("GROQ_API_URL", GROQ_API_URL_DEFAULT)
    groq_model = args.model

    if not groq_api_key:
        sys.stderr.write("GROQ_API_KEY is required\n")
        sys.exit(1)
    if not mqdb_api_key:
        sys.stderr.write("MQDB_API_KEY (or DEMO_API_KEY/MQDB_DEMO_API_KEY or --api-key) is required\n")
        sys.exit(1)

    models_to_try = [groq_model] if groq_model else []
    for m in GROQ_MODEL_FALLBACKS:
        if m not in models_to_try:
            models_to_try.append(m)

    remaining = args.count
    batch_size = max(1, min(args.batch_size, 20))
    created_ids: List[str] = []
    failed: List[str] = []

    while remaining > 0:
        current = min(batch_size, remaining)
        prompt = build_prompt(args.subject, current, args.difficulty)

        questions: List[Dict[str, Any]] = []
        last_err: Exception | None = None
        for model_name in models_to_try:
            try:
                questions = call_groq(prompt, groq_api_key, groq_api_url, model_name)
                break
            except Exception as exc:  # pragma: no cover
                last_err = exc
                continue
        else:
            raise last_err or RuntimeError("Failed to generate questions with Groq")

        # Trim to requested batch size if Groq returned extra
        questions = questions[:current]

        for q in questions:
            try:
                normalized = sanitize_question(q)
                qid = post_question(normalized, args.subject, args.difficulty, mqdb_base, mqdb_api_key)
                created_ids.append(qid)
                print(f"Created question: {qid}")
            except Exception as exc:  # pragma: no cover
                failed.append(str(exc))
                print(f"Failed to create question: {exc}", file=sys.stderr)

        remaining -= len(questions)

    print(f"Done. Created {len(created_ids)} questions. Failed: {len(failed)}")
    if failed:
        print("Failures:", *failed, sep="\n- ")


if __name__ == "__main__":
    main()
