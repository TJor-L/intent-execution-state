"""Generate a local, ignored handoff prompt pinned to a clean source commit."""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def create_handoff(root: Path, output: Path) -> str:
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)
    if dirty.strip():
        raise ValueError("Commit verified source changes before generating a handoff")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    template = (root / "docs/server_codex_prompt.md").read_text()
    prompt = template.replace("{{COMMIT_SHA}}", revision)
    if "{{COMMIT_SHA}}" in prompt:
        raise ValueError("Unresolved handoff revision")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(prompt)
    return revision


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "handoff/UCSF_CODEX_PROMPT.md")
    args = parser.parse_args()
    try:
        commit = create_handoff(ROOT, args.output)
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"Handoff unavailable: {error}\n")
    print(f"Handoff generated for commit {commit}: {args.output}")
