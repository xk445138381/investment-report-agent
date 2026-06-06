"""LLM subprocess helper — calls DeepSeek API in a completely isolated subprocess.

This bypasses all uvicorn/asyncio/httpx issues. The subprocess has its own
Python interpreter, its own event loop, and its own HTTP client.
"""

import subprocess, sys, os, json, logging

logger = logging.getLogger(__name__)

def call_llm(api_key: str, base_url: str, model: str, prompt: str, timeout: int = 120) -> str | None:
    """Call DeepSeek API in a subprocess. Returns response text or None on failure."""
    try:
        payload = json.dumps({
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "prompt": prompt,
        })
        script = r'''
import sys, json
import urllib.request
payload = json.loads(sys.stdin.read())
api_key = payload["api_key"]
base_url = payload["base_url"].rstrip("/")
model = payload["model"]
prompt = payload["prompt"]
body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.4, "max_tokens": 4000}).encode()
req = urllib.request.Request(f"{base_url}/chat/completions", data=body, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
    print(resp["choices"][0]["message"]["content"])
except Exception as e:
    print("ERROR", file=sys.stderr)
    sys.exit(1)
'''
        result = subprocess.run(
            [sys.executable, "-c", script],
            input=payload, capture_output=True, text=True, encoding="utf-8", timeout=timeout,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        )
        stdout = (result.stdout or "").strip()
        if result.returncode == 0 and stdout:
            return stdout
        if result.stderr:
            logger.warning(f"LLM subprocess stderr: {result.stderr[:200]}")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("LLM subprocess timed out")
        return None
    except Exception as e:
        logger.warning(f"LLM subprocess error: {e}")
        return None
