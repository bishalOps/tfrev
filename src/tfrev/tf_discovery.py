"""Discover Terraform source files for additional context in reviews."""

from __future__ import annotations

from pathlib import Path

from tfrev.diff_parser import DiffSummary
from tfrev.plan_parser import PlanSummary

# Max total bytes of context files to include, to avoid blowing up the prompt
_MAX_CONTEXT_BYTES = 100_000
# Max individual file size to include
_MAX_FILE_BYTES = 20_000


def infer_root_dir(diff: DiffSummary) -> Path | None:
    """Infer the Terraform project root from the diff's changed .tf files."""
    tf_paths = [
        Path(f.path) for f in diff.files if f.path.endswith(".tf") or f.path.endswith(".tfvars")
    ]
    if not tf_paths:
        return None

    # Find the common parent of all changed .tf files
    parents = [p.parent for p in tf_paths]
    common = parents[0]
    for parent in parents[1:]:
        # Walk up until we find a common ancestor
        while common != parent and common not in parent.parents:
            common = common.parent
        if common == Path("."):
            break

    root = Path.cwd() / common
    if root.exists():
        return root
    return Path.cwd()


def discover_context_files(
    diff: DiffSummary,
    plan: PlanSummary,
    root: Path,
) -> dict[str, str]:
    """Discover relevant .tf files in root that aren't already in the diff.

    Returns a mapping of relative path → file contents.
    """
    # Paths already covered by the diff — skip them
    diff_paths = {Path(f.path).resolve() for f in diff.files}

    # Collect .tf files from the root directory (non-recursive for the root,
    # then recurse into modules referenced by the plan)
    candidate_files: list[Path] = []

    # Root-level .tf files (variables, outputs, providers, versions, etc.)
    for tf_file in sorted(root.glob("*.tf")):
        candidate_files.append(tf_file)

    # Module directories referenced in the plan
    module_dirs: set[Path] = set()
    for rc in plan.resource_changes:
        if rc.module_address:
            # module.foo.bar -> modules/foo
            parts = rc.module_address.split(".")
            if len(parts) >= 2:
                module_dir = root / "modules" / parts[1]
                if module_dir.exists():
                    module_dirs.add(module_dir)

    for mod_dir in sorted(module_dirs):
        for tf_file in sorted(mod_dir.glob("*.tf")):
            candidate_files.append(tf_file)

    # Read files, skipping those already in diff or too large
    context_files: dict[str, str] = {}
    total_bytes = 0

    for tf_file in candidate_files:
        if tf_file.resolve() in diff_paths:
            continue
        if not tf_file.exists():
            continue

        file_size = tf_file.stat().st_size
        if file_size > _MAX_FILE_BYTES:
            continue
        if total_bytes + file_size > _MAX_CONTEXT_BYTES:
            break

        try:
            content = tf_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Use a path relative to CWD for display
        try:
            display_path = str(tf_file.relative_to(Path.cwd()))
        except ValueError:
            display_path = str(tf_file)

        context_files[display_path] = content
        total_bytes += file_size

    return context_files


def format_context_for_prompt(context_files: dict[str, str]) -> str:
    """Format discovered context files for inclusion in the Claude prompt."""
    if not context_files:
        return "(No additional source files discovered)"

    parts = []
    for path in sorted(context_files):
        content = context_files[path]
        parts.append(f"### {path}\n```hcl\n{content}\n```")

    return "\n\n".join(parts)
