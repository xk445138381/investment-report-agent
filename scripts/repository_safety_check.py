"""Check repository state for files that should not ship."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SENSITIVE_PATH_PATTERNS = [
    re.compile(r"(^|[\\/])\.env($|[\\/])"),
    re.compile(r"(^|[\\/])\.env\.(?!example$)[^\\/]+$"),
    re.compile(r"(^|[\\/]).*\.pem$"),
    re.compile(r"(^|[\\/]).*\.key$"),
]

SECRET_VALUE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\b"),
]

TEXT_EXTENSIONS = {
    ".env",
    ".example",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yml",
    ".yaml",
}


def _git_candidates() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_sensitive_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.endswith(".env.example"):
        return False
    return any(pattern.search(normalized) for pattern in SENSITIVE_PATH_PATTERNS)


def _is_text_candidate(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    return path.name in {".gitignore", ".dockerignore"}


def _scan_secret_values(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(content):
            findings.append(pattern.pattern)
    return findings


def main() -> int:
    errors: list[str] = []
    for relative in _git_candidates():
        if _is_sensitive_path(relative):
            errors.append(f"sensitive file is not ignored: {relative}")
            continue
        path = ROOT / relative
        if _is_text_candidate(path):
            for pattern in _scan_secret_values(path):
                errors.append(f"possible secret value in {relative}: {pattern}")

    if errors:
        print("repository_safety_check: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("repository_safety_check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
