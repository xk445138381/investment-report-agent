"""LLM subprocess helper — calls DeepSeek API in a completely isolated subprocess.

This bypasses all uvicorn/asyncio/httpx issues. The subprocess has its own
Python interpreter, its own event loop, and its own HTTP client.
"""

import subprocess, sys, os, json, logging

logger = logging.getLogger(__name__)

# Cache the script content (inject api_key at runtime)
_SCRIPT_TEMPLATE = '''
import sys, json, os
try:
    import urllib.request
    api_key = {api_key}
    model = {model}
    prompt = {prompt}
    base_url = {base_url}

    body = json.dumps({{
        "model": model,
        "messages": [{{"role": "user", "content": prompt}}],
        "temperature": 0.4,
        "max_tokens": 4000
    }}).encode()

    req = urllib.request.Request(
        f"{{base_url}}/chat/completions",
        data=body,
        headers={{
            "Authorization": f"Bearer {{api_key}}",
            "Content-Type": "application/json"
        }},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
    content = resp["choices"][0]["message"]["content"]
    print(content, flush=True)
except Exception as e:
    print(f"LLM_SUBPROCESS_ERROR: {{e}}", file=sys.stderr, flush=True)
    sys.exit(1)
'''


def call_llm(api_key: str, base_url: str, model: str, prompt: str, timeout: int = 120) -> str | None:
    """Call DeepSeek API in a subprocess. Returns response text or None on failure."""
    try:
        # Use simple replacement to avoid .format() issues with braces in prompt
        prompt_escaped = json.dumps(prompt)
        script = (_SCRIPT_TEMPLATE
                  .replace("{api_key}", json.dumps(api_key))
                  .replace("{model}", json.dumps(model))
                  .replace("{prompt}", prompt_escaped)
                  .replace("{base_url}", json.dumps(base_url)))
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        if result.returncode == 0 and result.stdout.strip():
            text = result.stdout.strip()
            if not text.startswith("LLM_SUBPROCESS_ERROR"):
                return text
        if result.stderr:
            logger.warning(f"LLM subprocess stderr: {result.stderr[:200]}")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("LLM subprocess timed out")
        return None
    except Exception as e:
        logger.warning(f"LLM subprocess error: {e}")
        return None
