"""scripts/check_no_direct_calls.py must catch every way of bypassing Prune or leaking a key, and pass on this repo.

The bad examples are assembled at runtime so this file itself never contains a real-looking key or provider URL.
"""
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "check_no_direct_calls", pathlib.Path(__file__).resolve().parents[2] / "scripts" / "check_no_direct_calls.py")
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

OPENAI_URL = "https://api." + "openai.com/v1/chat/completions"
SECRET = "sk-" + "proj-" + "A1b2C3d4" * 4
GOOGLE = "AI" + "za" + "B" * 35


def test_catches_direct_calls_sdk_imports_and_frontend_llm_use():
    assert chk.scan_text("backend/app/x.py", f'URL = "{OPENAI_URL}"')
    assert chk.scan_text("backend/app/x.py", "imp" + "ort anthropic\n")
    assert chk.scan_text("scripts/tool.py", "fr" + "om openai import OpenAI\n")
    assert chk.scan_text("frontend/src/lib/ai.ts", 'fetch("https://api.' + 'withprune.com/v1/chat/completions")')


def test_allows_the_one_prune_client_and_receipt_links():
    assert chk.scan_text("backend/app/ai/prune_client.py", "imp" + "ort openai\nfr" + "om openai import OpenAI\n") == []
    assert chk.scan_text("backend/tests/test_x.py", "imp" + "ort openai\n") == []  # tests build fake errors with it
    assert chk.scan_text("frontend/src/components/ops.tsx", '<a href="https://withprune.com/verify">Verify</a>') == []


def test_catches_keys_but_not_the_empty_example():
    assert chk.scan_text("backend/app/config.py", f'KEY = "{SECRET}"')
    assert chk.scan_text("docs/notes.md", GOOGLE)
    assert chk.scan_text("backend/.env.local", "PRUNE_" + "API_KEY=pk_live_abcdef123456")
    assert chk.scan_text(".env.example", "PRUNE_" + "API_KEY=                 # ops key\nMODEL_SMALL=\n") == []


def test_forbidden_files():
    bad = [".env", "backend/.env", "backend/.env.local", "backend/keys/pass_signing.key", "backend/safetrail.db",
           "backend/benchmark.db-wal"]
    assert all(chk.FORBIDDEN_FILE.search(f) for f in bad)
    assert not chk.FORBIDDEN_FILE.search(".env.example")


def test_this_repo_is_clean():
    assert chk.main() == 0
