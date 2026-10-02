"""Start the LLMOps HTTP server locally for a client such as Archinex (governance, no demo data).

    poetry run python scripts/serve_local.py [--port 8000]

Restart = Ctrl+C, then run it again (state lives in the governance database, not in the process).

Reads ``.env`` into the real environment first (so OWNER_DISCORD_WEBHOOK, SMTP settings... in ``.env`` are seen by the
notifier), then applies local defaults for what is NOT already set:

    CANDIDATES_BACKEND=sql, GOVERNANCE_DATABASE_URL=sqlite:///data/governance.db   (survives restarts)
    SERVER_TOKEN                 a random token printed at start if unset (public demo-style, no governance scope)
    ENGAGEMENT_TOKENS            <LLMOPS_SERVICE_TOKEN>:kb:review,kb:delegate,*   (the token Archinex must use)

The service token is generated once and kept in .llmops-local-service-token (git-ignored) so a restart does not
change it; set LLMOPS_SERVICE_TOKEN (or ENGAGEMENT_TOKENS yourself) to choose it. It is never hard-coded.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


TOKEN_FILE = ROOT / ".llmops-local-service-token"


def persistent_token() -> str:
    """Service token kept between restarts (git-ignored file), so that Archinex's configuration stays valid."""
    try:
        value = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    except OSError:
        pass
    value = secrets.token_urlsafe(24)
    TOKEN_FILE.write_text(value + "\n", encoding="utf-8")
    return value


def configure(environ: dict[str, str] | None = None) -> dict[str, str]:
    """Apply the local defaults to ``environ`` (os.environ by default); return what was defaulted."""
    env = os.environ if environ is None else environ
    applied: dict[str, str] = {}

    def default(name: str, value: str) -> None:
        if not env.get(name, "").strip():
            env[name] = value
            applied[name] = value

    default("LLMOPS_TRANSPORT", "sse")
    default("CANDIDATES_BACKEND", "sql")
    default("GOVERNANCE_DATABASE_URL", f"sqlite:///{(ROOT / 'data' / 'governance.db').as_posix()}")
    default("SERVER_TOKEN", secrets.token_urlsafe(24))
    if not env.get("ENGAGEMENT_TOKENS", "").strip():
        service = env.get("LLMOPS_SERVICE_TOKEN", "").strip() or persistent_token()
        env["LLMOPS_SERVICE_TOKEN"] = service
        default("ENGAGEMENT_TOKENS", f"{service}:kb:review,kb:delegate,*")
    return applied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:  # python-dotenv is a dependency; tolerate a stripped environment
        pass
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    if args.host:
        os.environ["HOST"] = args.host
    if args.port:
        os.environ["PORT"] = str(args.port)
    applied = configure()

    port = os.environ.get("PORT", "8000")
    print(f"LLMOps server on http://{os.environ.get('HOST', '127.0.0.1')}:{port}  (Ctrl+C to stop, rerun to restart)")
    print(f"  governance database : {os.environ['GOVERNANCE_DATABASE_URL']}  (backend {os.environ['CANDIDATES_BACKEND']})")
    if "ENGAGEMENT_TOKENS" in applied:
        print(f"  service token for Archinex (LLMOPS_AUTH_TOKEN): {os.environ['LLMOPS_SERVICE_TOKEN']}")
    else:
        print("  ENGAGEMENT_TOKENS : taken from the environment")
    print(f"  Discord for owners  : {'OWNER_DISCORD_WEBHOOK set' if os.environ.get('OWNER_DISCORD_WEBHOOK') else 'OWNER_DISCORD_WEBHOOK not set'}")

    from mcp_server.main import main as serve

    serve()


if __name__ == "__main__":
    main()
