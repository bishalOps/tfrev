# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- AWS Bedrock provider support — set `provider: aws-bedrock` in `.tfrev.yaml` or pass `--provider aws-bedrock` on the CLI to route reviews through AWS Bedrock instead of the Anthropic API directly; region and credentials come from the standard AWS credential chain
- `tfrev[aws]` optional install extra that pulls in `boto3` (required for Bedrock)
- Provider-aware error messages for authentication and permission failures on both providers
- `botocore` exception handling for AWS credential errors that escape the SDK wrapper

### Changed
- CLI progress messages now show the active provider (e.g. "Sending to Claude via AWS Bedrock for review...")
- Summary line now shows `Provider:` alongside `Model:`
- `table` and `markdown` output formats now include a footer line showing token usage (in/out), wall-clock review duration, model, and provider (e.g. `1,847 tokens in / 412 out · 3.2s · claude-sonnet-4-6 · anthropic`)

## [2.0.0] - 2026-04-17

### Migration from 1.0.x

- `--plan-text` has been removed. Use `--plan <file>` with JSON output from `terraform show -json <tfplan>` instead.
- If you invoke `tfrev review` from CI/CD, add `--quiet` to the command. Without `--quiet`, tfrev now prompts for interactive confirmation before sending plan + diff to Claude and will hang on a non-interactive stdin. The `--base-ref` confirmation and the context-overflow prompt are suppressed the same way.
- Exit code on unparseable Claude responses changed from 0 to 2. CI scripts that treated any non-zero exit as a failure will continue to work; scripts that explicitly checked `== 0` to mean "review ran" need updating.

### Added
- Non-git directory support — `tfrev review` now scans local `.tf`/`.tfvars` files when not in a git repository
- Default branch auto-detection — detects `main` vs `master` instead of hardcoding `main`
- Resource-aware context discovery — uses plan resource addresses and module references to find relevant `.tf` files, not just root-level globs
- Local module source resolution — follows relative `source` paths in module blocks to include module source files as context
- `PermissionDeniedError` handling with actionable error message for insufficient API key permissions

### Changed
- Skip the Claude API call and exit 0 when the plan shows no infrastructure changes (0 create / 0 update / 0 delete / 0 replace)
- Prompt for confirmation before sending plan + diff to Claude (default: yes). Suppressed by `--quiet` for CI/automation use.
- README "Any CI/CD" snippet updated to include `--quiet` with a note explaining why it is required in non-interactive environments
- Removed per-model context limit mapping — uses a single default context limit (200k tokens) that works with any model
- Context window overflow now prompts the user to continue instead of hard-failing (default: abort)
- Missing `--base-ref` now warns the user with an explanation of what it is and the fallback behavior, then asks to confirm before proceeding
- Both-refs-fail scenario now falls back to empty-tree diff instead of exiting with an error
- Development status classifier changed from `Production/Stable` to `Beta`
- README sample output updated to use real AWS resource types instead of `null_resource`
- README cost section clarified with typical cost range and single-call model
- ARCHITECTURE.md corrected to accurately describe single-call model (no chunking)

### Removed
- `--plan-text` option — use `--plan` with JSON output from `terraform show -json` instead
- `httpx` direct dependency — now uses `anthropic.Timeout` from the Anthropic SDK

### Fixed
- Exit code 2 (not 0) when Claude's response can't be parsed as structured JSON, so CI no longer silently passes on a broken review
- `subprocess.TimeoutExpired` from `git diff` is caught on both the primary diff path and the empty-tree fallback, producing a clear error and exit 2 instead of a traceback
- Context-file dedup now resolves diff paths against the git toplevel instead of `Path.cwd()`, preventing duplicate files when tfrev is run from a subdirectory of the repo
- `--base-ref` confirmation prompt no longer fires in non-git directories (it was asking the user to confirm diffing against `main` with no git present)
- Invalid severity values in `.tfrev.yaml` `policies[*].severity` are now rejected at load time instead of silently being treated as `info`
- File reads in config/plan loaders now pin `encoding="utf-8"` for cross-platform safety
- `_extract_json` prefers a ```` ```json ```` fenced block over any earlier fence, so a preceding `hcl` example in Claude's reply doesn't get parsed as JSON

## [1.0.1] - 2026-04-04

### Changed
- Made documentation and examples cloud-agnostic (AWS, GCP, Azure, Kubernetes)
- Updated system prompt security analysis to cover multi-cloud providers
- Expanded `.tfrev.yaml.example` with GCP, Azure, and Kubernetes sensitive resources

### Removed
- Unused `changes.diff` example file

## [1.0.0] - 2026-04-03

### Added
- CLI with `review` command (`--plan`, `--plan-text`, `--auto`, `--base-ref`)
- Auto-generated git diff — tfrev runs `git diff` internally, no manual diff file needed
- `--base-ref` flag to control what git ref the diff is generated against
- Empty-tree fallback — when no changes exist vs base ref (e.g. first commit), reviews all current `.tf` files
- Base ref auto-detection from CI env vars (`GITHUB_BASE_REF`, `CI_MERGE_REQUEST_TARGET_BRANCH_NAME`, `CHANGE_TARGET`)
- JSON, Markdown, and Table output formats
- `.tfrev.yaml` configuration with custom policies and sensitive resource lists
- `config.ignore` filtering — diff files matching ignore patterns are excluded
- Terraform source file context discovery for surrounding `.tf` files
- GitHub Action, GitLab CI template, Jenkins pipeline integrations
- Claude API client with exponential backoff retries on rate limit and server errors
- API timeout (120s request, 10s connect)
- Context window overflow detection with automatic context file trimming
- Progress spinner during API calls
- Token estimation accuracy logging
- Test suite with pytest (168 tests, 92% coverage)
- GitHub Actions CI pipeline (pytest, ruff, mypy across Python 3.9-3.13)
- PyPI publish workflow via trusted publishing (triggered on `v*` tags)
- `py.typed` marker for PEP 561 type checking support
- Docker support
