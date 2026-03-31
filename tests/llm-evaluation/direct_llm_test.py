#!/usr/bin/env python3
"""
Direct LLM Evaluation Test — Tests whether AI models can build a real estate
marketplace application when given a detailed specification.

Supports 3 model backends:
  1. DeepSeek R1 (local Ollama)
  2. Kimi2.5 (Ollama cloud API)
  3. GLM5 (Ollama cloud API)

Usage:
  # Test all models (requires OLLAMA_API_KEY env var for cloud models)
  python direct_llm_test.py --all

  # Test a single model
  python direct_llm_test.py --model kimi-k2.5

  # Test local DeepSeek R1 only (no API key needed)
  python direct_llm_test.py --model deepseek-r1

Environment variables:
  OLLAMA_API_KEY       — Required for cloud models (kimi-k2.5, glm-5)
  OLLAMA_CLOUD_URL     — Cloud API base URL (default: https://ollama.com/v1)
  OLLAMA_LOCAL_URL     — Local Ollama URL (default: http://localhost:11434/v1)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: openai package not installed. Run: pip install openai")
    sys.exit(1)

# ── Configuration ──────────────────────────────────────────────────────────

OLLAMA_CLOUD_URL = os.environ.get("OLLAMA_CLOUD_URL", "https://ollama.com/v1")
OLLAMA_LOCAL_URL = os.environ.get("OLLAMA_LOCAL_URL", "http://localhost:11434/v1")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")

MODELS = {
    "deepseek-r1": {
        "model": "deepseek-r1:8b",
        "base_url": OLLAMA_LOCAL_URL,
        "api_key": "ollama",  # local Ollama doesn't need a real key
        "is_cloud": False,
    },
    "kimi-k2.5": {
        "model": "kimi-k2.5",
        "base_url": OLLAMA_CLOUD_URL,
        "api_key": OLLAMA_API_KEY,
        "is_cloud": True,
    },
    "glm-5": {
        "model": "glm-5",
        "base_url": OLLAMA_CLOUD_URL,
        "api_key": OLLAMA_API_KEY,
        "is_cloud": True,
    },
}

# Required database models that should appear in the response
REQUIRED_MODELS = [
    "User", "Property", "Address", "PropertyImage",
    "PropertyFeature", "Favorite", "Inquiry", "Review",
    "Agency", "AgentProfile",
]

# ── Task Specification ─────────────────────────────────────────────────────

TASK_SPEC = """You are a senior backend engineer. Build a complete real estate marketplace backend.

Create these files with COMPLETE, RUNNABLE code (use str_replace_editor tool with create command):

1. backend/models.py — SQLAlchemy models with these 10 tables:
   - User (email, hashed_password, first_name, last_name, phone, role, is_active)
   - Property (title, description, type, status, price, bedrooms, bathrooms, sqft, year_built)
   - Address (street, city, state, zip_code, country, latitude, longitude)
   - PropertyImage (property_id, image_url, caption, is_primary, display_order)
   - PropertyFeature (property_id, feature_name, feature_value)
   - Favorite (user_id, property_id)
   - Inquiry (buyer_id, property_id, message, status, response)
   - Review (property_id, reviewer_id, rating, comment)
   - Agency (name, description, logo_url, website, phone, email, is_verified)
   - AgentProfile (user_id, agency_id, license_number, bio, years_experience, rating_average)

2. backend/main.py — FastAPI app with CRUD routes for all models
3. backend/auth.py — JWT auth with role-based access (buyer, seller, agent, admin)
4. backend/schemas.py — Pydantic schemas for all models
5. requirements.txt — All dependencies

Requirements:
- All relationships and foreign keys must be defined
- Use proper SQLAlchemy ORM patterns
- Include created_at/updated_at timestamps
- Use Pydantic v2 with ConfigDict
"""

SYSTEM_PROMPT = """You are an expert software engineer using the str_replace_editor tool.
When creating files, use this exact format:

<str_replace_editor>
<command>create</command>
<path>/workspace/path/to/file.py</path>
<file_text>
... complete file contents ...
</file_text>
</str_replace_editor>

Write COMPLETE, production-ready code. No placeholders, no TODOs, no truncation."""


# ── Test Runner ────────────────────────────────────────────────────────────

def test_model(model_name: str, output_dir: Path) -> dict:
    """Test a single model and return metrics."""
    config = MODELS[model_name]

    if config["is_cloud"] and not config["api_key"]:
        print(f"  SKIP {model_name}: OLLAMA_API_KEY not set (required for cloud models)")
        return {"model": model_name, "status": "skipped", "reason": "no_api_key"}

    print(f"  Testing {model_name} via {config['base_url']}...")

    client = OpenAI(base_url=config["base_url"], api_key=config["api_key"])

    start = time.time()
    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": TASK_SPEC},
            ],
            temperature=0.7,
            max_tokens=16384,
        )
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ERROR {model_name}: {e}")
        return {
            "model": model_name,
            "status": "error",
            "error": str(e),
            "time": round(elapsed, 2),
        }

    elapsed = time.time() - start
    msg = response.choices[0].message

    # Extract content
    content = msg.content or ""
    reasoning = getattr(msg, "reasoning_content", "") or ""

    # Save full response
    resp_file = output_dir / f"{model_name}_response.txt"
    with open(resp_file, "w") as f:
        if reasoning:
            f.write(f"=== REASONING ({len(reasoning)} chars) ===\n{reasoning}\n\n")
        f.write(f"=== RESPONSE ({len(content)} chars) ===\n{content}\n")

    # Analyze response quality
    tool_calls = content.count("<str_replace_editor>")
    has_python = "import " in content or "from " in content
    model_count = sum(1 for m in REQUIRED_MODELS if m in content)
    has_all_models = model_count == len(REQUIRED_MODELS)

    # Token usage
    usage = response.usage
    tokens_in = usage.prompt_tokens if usage else 0
    tokens_out = usage.completion_tokens if usage else 0

    result = {
        "model": model_name,
        "status": "success",
        "time_seconds": round(elapsed, 2),
        "response_length": len(content),
        "reasoning_length": len(reasoning),
        "tool_call_count": tool_calls,
        "has_code": has_python,
        "models_found": model_count,
        "has_all_10_models": has_all_models,
        "missing_models": [m for m in REQUIRED_MODELS if m not in content],
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "response_file": str(resp_file),
    }

    print(f"  OK {model_name}: {len(content)} chars, {tool_calls} tool calls, "
          f"{model_count}/10 models, {elapsed:.1f}s")
    return result


def main():
    parser = argparse.ArgumentParser(description="Direct LLM Evaluation Test")
    parser.add_argument("--model", choices=list(MODELS.keys()),
                        help="Test a single model")
    parser.add_argument("--all", action="store_true",
                        help="Test all 3 models")
    parser.add_argument("--output-dir", default="tests/llm-evaluation/responses",
                        help="Directory to save responses")
    args = parser.parse_args()

    if not args.model and not args.all:
        parser.print_help()
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    models_to_test = list(MODELS.keys()) if args.all else [args.model]
    results = []

    print(f"\n{'='*60}")
    print(f"  Direct LLM Evaluation — Real Estate Marketplace Spec")
    print(f"{'='*60}\n")

    for model_name in models_to_test:
        result = test_model(model_name, output_dir)
        results.append(result)
        print()

    # Save summary
    summary_file = output_dir / "test_results.json"
    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2)

    # Print comparison table
    print(f"\n{'='*60}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*60}\n")
    print(f"{'Model':<15} {'Status':<10} {'Time':>8} {'Chars':>8} {'Tools':>6} {'Models':>8}")
    print(f"{'-'*15} {'-'*10} {'-'*8} {'-'*8} {'-'*6} {'-'*8}")
    for r in results:
        status = r.get("status", "?")
        time_s = f"{r.get('time_seconds', r.get('time', 0)):.1f}s"
        chars = str(r.get("response_length", r.get("length", 0)))
        tools = str(r.get("tool_call_count", 0))
        models = f"{r.get('models_found', r.get('model_count', 0))}/10"
        print(f"{r['model']:<15} {status:<10} {time_s:>8} {chars:>8} {tools:>6} {models:>8}")

    print(f"\nResults saved to: {summary_file}")
    return 0 if all(r.get("status") == "success" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
