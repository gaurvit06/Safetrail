"""SPEC rule 1 and the definition of done: fail if anything could bypass Prune or leak a key.

    bash scripts/check_no_direct_calls.sh        (or: python scripts/check_no_direct_calls.py)

Checks every file git knows about (tracked, plus new files that aren't ignored):
  1. no direct AI-provider URL anywhere (every LLM call goes through Prune's one base URL)
  2. no AI SDK import outside backend/app/ai/prune_client.py (tests may import it to build fake errors)
  3. the frontend never talks to an LLM: no Prune API URL or chat/completions in frontend/src
  4. no keys: OpenAI/Anthropic/Google/AWS-style keys, private key blocks, or a filled-in PRUNE_API_KEY=...
  5. no .env, backend/keys/ or database files committed
and then scans the added lines of the whole git history (rule 4) and the built frontend bundle (rules 1, 3, 4).
Exit code 0 = clean, 1 = something found. Stdlib only.
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SELF = {"scripts/check_no_direct_calls.py", "scripts/check_no_direct_calls.sh"}
SDK_ALLOWED = ("backend/app/ai/prune_client.py", "backend/tests/")

PROVIDER = re.compile(
    r"api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis\.com|aiplatform\.googleapis\.com"
    r"|bedrock-runtime\.|\.openai\.azure\.com|inference\.ai\.azure\.com|api\.mistral\.ai|api\.cohere\.(?:com|ai)"
    r"|api\.groq\.com|api\.together\.(?:xyz|ai)|openrouter\.ai/api|api\.deepseek\.com|api\.x\.ai|api\.perplexity\.ai"
    r"|api\.fireworks\.ai")
SDK_IMPORT = re.compile(r"^\s*(?:import|from)\s+(?:openai|anthropic|google\.generativeai|google\.genai|mistralai|cohere"
                        r"|groq|together|litellm|langchain\w*)\b", re.M)
FRONTEND_LLM = re.compile(r"api\.withprune\.com|chat/completions|PRUNE_API_KEY|PRUNE_PUBLIC_API_KEY")
KEYS = [
    ("an OpenAI/Anthropic-style secret key", re.compile(r"\bsk-(?:proj-|ant-[a-z0-9]+-)?[A-Za-z0-9_\-]{24,}")),
    ("a Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("an AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("a private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----")),
    ("a filled-in API key setting", re.compile(
        r"(?m)^\s*(?:PRUNE_API_KEY|PRUNE_PUBLIC_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|GOOGLE_API_KEY)\s*=\s*[\"']?[A-Za-z0-9_\-]{12,}")),
]
FORBIDDEN_FILE = re.compile(r"(?:^|/)\.env(?:\.(?!example$)[^/]+)?$|^backend/keys/|\.db(?:-wal|-shm)?$")


def scan_text(path: str, text: str) -> list[str]:
    """All problems in one file's text. Pure function (unit-tested)."""
    out = []
    lines = text.splitlines()

    def where(m) -> str:
        return f"{path}:{text.count(chr(10), 0, m.start()) + 1}"

    for m in PROVIDER.finditer(text):
        out.append(f"{where(m)}: direct AI-provider URL '{m.group(0)}' (route every LLM call through Prune)")
    if not path.startswith(SDK_ALLOWED):
        for m in SDK_IMPORT.finditer(text):
            out.append(f"{where(m)}: AI SDK import outside prune_client.py: '{m.group(0).strip()}'")
    if path.startswith("frontend/src/"):
        for m in FRONTEND_LLM.finditer(text):
            out.append(f"{where(m)}: the app must never call an LLM or hold a Prune key ('{m.group(0)}')")
    for label, rx in KEYS:
        for m in rx.finditer(text):
            line = lines[text.count("\n", 0, m.start())] if lines else ""
            if path.endswith(".env.example") and re.match(r"^\s*\w+\s*=\s*(#|$)", line):
                continue
            out.append(f"{where(m)}: looks like {label}")
    return out


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=True).stdout


def files() -> list[str]:
    return sorted(set(git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()))


def scan_history() -> tuple[list[str], int]:
    """Keys in any line ever added to the history (a deleted key is still a leaked key)."""
    out, commit = [], "?"
    log = git("log", "--all", "-p", "--no-color", "--format=commit %h")
    n = 0
    for line in log.splitlines():
        if line.startswith("commit "):
            commit, n = line.split()[1], n + 1
        elif line.startswith("+") and not line.startswith("+++"):
            for label, rx in KEYS[:4]:  # the "filled-in setting" rule needs the file context, checked on files instead
                if rx.search(line):
                    out.append(f"history {commit}: an added line looks like {label}")
    return out, n


def main() -> int:
    problems = []
    tracked = files()
    for f in tracked:
        if FORBIDDEN_FILE.search(f):
            problems.append(f"{f}: must never be committed (secrets or personal data)")
        p = REPO / f
        if f in SELF or not p.is_file():
            continue
        data = p.read_bytes()
        if b"\0" in data[:4096]:  # binary
            continue
        problems += scan_text(f, data.decode("utf-8", errors="replace"))
    try:
        hist, commits = scan_history()
        problems += hist
        shallow = git("rev-parse", "--is-shallow-repository").strip() == "true"
    except (subprocess.CalledProcessError, FileNotFoundError):
        commits, shallow = 0, False
        problems.append("git history could not be read (is git installed and is this a git checkout?)")
    dist = REPO / "frontend" / "dist"
    bundle_files = [p for p in dist.rglob("*") if p.is_file() and p.suffix in (".js", ".html", ".json", ".webmanifest")] if dist.exists() else []
    for p in bundle_files:
        rel = p.relative_to(REPO).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        problems += [x for x in scan_text("frontend/src/" + rel, text)]  # bundle gets the frontend rules too
    if problems:
        print(f"FAILED: {len(problems)} problem(s)")
        for x in problems:
            print("  - " + x)
        return 1
    print(f"OK: {len(tracked)} files, {commits} commits{' (shallow clone: older history not checked)' if shallow else ''}, "
          f"{len(bundle_files)} built frontend files: no direct AI calls, no SDK outside prune_client.py, no keys.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
