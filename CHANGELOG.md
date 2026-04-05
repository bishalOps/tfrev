# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
