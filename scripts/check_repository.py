"""Fail closed on files outside the code/docs allowlist. No content is printed."""

import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".gitignore",
    ".python-version",
    ".env.example",
    "README.md",
    "AGENTS.md",
    "pyproject.toml",
    "uv.lock",
    "Makefile",
}
CONFIGS = {
    "configs/synthetic.yaml",
    "configs/remote.example.yaml",
    "configs/feasibility.example.yaml",
    "configs/coherent_access.example.yaml",
    "configs/clinical_protocol.example.yaml",
    "configs/cohort_vocabulary.example.yaml",
    "configs/cohort_eligibility.example.yaml",
}


def allowed(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if name in ROOT_FILES | CONFIGS:
        return True
    if name in {".github/workflows/ci.yml", "results/README.md", "fixtures/README.md"}:
        return True
    directory = path.parts[0]
    return (
        (directory in {"src", "tests"} and path.suffix == ".py")
        or (directory == "scripts" and path.suffix in {".py", ".sh"})
        or (directory == "slurm" and path.suffix in {".sbatch", ".sh", ".md"})
        or (directory == "docs" and path.suffix == ".md")
    )


def violations(root: Path = ROOT) -> list[str]:
    files = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
        )
        .decode()
        .split("\0")
    )
    problems = []
    for name in sorted(set(files) - {""}):
        if not allowed(name):
            problems.append("File outside repository allowlist")
            continue
        path = root / name
        if path.is_symlink():
            problems.append("Symlink in publication set")
        elif not path.is_file():
            problems.append("Missing tracked file")
        elif path.stat().st_size > 2_000_000:
            problems.append("Oversized file in publication set")
        else:
            data = path.read_bytes()
            if b"\x00" in data or re.search(
                rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----", data
            ):
                problems.append("Binary data or private-key material in publication set")
    return problems


if __name__ == "__main__":
    issues = violations()
    if issues:
        raise SystemExit(
            f"Repository boundary check failed: {len(issues)} issue(s); inspect locally."
        )
    print("Repository file boundary check passed (not a clinical-content de-identification tool).")
