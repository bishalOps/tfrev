# tfrev — AI-Powered Terraform Plan Reviewer

**Verify your Terraform plan matches your code intent before apply.**

tfrev uses Claude AI to review your `terraform plan` output against your code changes, catching mismatches, security risks, and unexpected side effects before they hit production. Works with any Terraform provider — AWS, Azure, GCP, Kubernetes, and more.

## Quick Start

### Anthropic API (default)

```bash
# Install
pip install tfrev

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Review a plan
terraform plan -out=tfplan
terraform show -json tfplan > plan.json

tfrev review --plan plan.json
```

### AWS Bedrock

```bash
# Install with Bedrock support
pip install 'tfrev[aws]'

# Configure AWS credentials (env vars, ~/.aws/credentials, or IAM role)
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1

# Via .tfrev.yaml
cat >> .tfrev.yaml <<'EOF'
provider: aws-bedrock
model: anthropic.claude-sonnet-4-5-20250514-v1:0
EOF
tfrev review --plan plan.json

# Or entirely via CLI flags
tfrev review --plan plan.json \
  --provider aws-bedrock \
  --model anthropic.claude-sonnet-4-5-20250514-v1:0
```

Or use auto-detection:

```bash
terraform plan -out=tfplan
tfrev review --auto
```

To diff against a specific ref (e.g. last deployed SHA):

```bash
tfrev review --plan plan.json --base-ref abc1234
```

## What It Catches

- **Intent mismatches** — plan does something the code change didn't intend
- **Unexpected replacements** — a tag change triggering a full resource destroy+create
- **Security regressions** — widened security groups, broadened IAM policies
- **Blast radius** — too many resources changing at once
- **Drift** — plan changes with no corresponding code change
- **Policy violations** — custom team rules defined in `.tfrev.yaml`

## CI/CD Integration

### GitHub Actions

```yaml
# Anthropic API
- name: AI Plan Review
  uses: bishalOps/tfrev@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    post_comment: "true"
    fail_on: high
```

```yaml
# AWS Bedrock (using OIDC or IAM credentials already configured in the job)
- name: AI Plan Review (Bedrock)
  run: |
    pip install 'tfrev[aws]'
    tfrev review --auto --provider aws-bedrock \
      --model anthropic.claude-sonnet-4-5-20250514-v1:0 \
      --output markdown --fail-on high --quiet
  env:
    AWS_DEFAULT_REGION: us-east-1
```

### GitLab CI

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/bishalOps/tfrev/main/ci/gitlab/.gitlab-ci-template.yml'
```

### Jenkins

Copy `ci/jenkins/Jenkinsfile` into your repo and add `ANTHROPIC_API_KEY` as a credential.

### Any CI/CD

```bash
# Anthropic API
pip install tfrev
export ANTHROPIC_API_KEY=$YOUR_SECRET
tfrev review --auto --output markdown --fail-on high --quiet

# AWS Bedrock (credentials via env or IAM role)
pip install 'tfrev[aws]'
tfrev review --auto --provider aws-bedrock \
  --model anthropic.claude-sonnet-4-5-20250514-v1:0 \
  --output markdown --fail-on high --quiet
```

> **Note:** Always pass `--quiet` in CI/CD. Without it, tfrev prompts for
> interactive confirmation before sending the plan + diff to Claude and will
> hang waiting for input on a non-interactive stdin. `--quiet` also suppresses
> the `--base-ref` confirmation and the context-overflow prompt.

## Configuration

Create a `.tfrev.yaml` in your project root:

```yaml
# Provider: "anthropic" (default) or "aws-bedrock"
provider: anthropic

model: claude-sonnet-4-6
fail_on: high
policies:
  - name: no-public-ingress
    description: "Flag security group rules allowing 0.0.0.0/0"
    severity: critical
sensitive_resources:
  - aws_iam_*            # AWS
  - google_project_iam_* # GCP
  - azurerm_key_vault*   # Azure
```

For AWS Bedrock, set `provider: aws-bedrock`, install `tfrev[aws]`, and use a Bedrock model ID. Region and credentials are read from the standard AWS credential chain (`AWS_DEFAULT_REGION`, `~/.aws/config`, IAM role, etc.):

```yaml
provider: aws-bedrock
model: anthropic.claude-sonnet-4-5-20250514-v1:0
```

See `.tfrev.yaml.example` for all options.

## Sample Output

```
────────────────────────────────────────────────────────────────────────
  ❌  Verdict: FAIL   Confidence: 95%
────────────────────────────────────────────────────────────────────────

  This plan contains three significant security regressions introduced by the code diff:
  SSH access widened from a private CIDR to 0.0.0.0/0, an RDS database marked
  publicly_accessible=true, and an S3 bucket ACL changed from private to public-read. All
  four resource creations are explained by code changes, but the security posture of the
  planned infrastructure is critically degraded and should not be applied without
  deliberate review and approval.

  Resources: 4 reviewed  |  +4 create  |  ~0 update  |  -0 delete  |  -/+0 replace

  ID     Severity     Category             Resource                                   Title
  ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  F001   CRITICAL     security             aws_security_group.web_sg                  SSH ingress opened to the entire internet (0.0.0.0/0)
  F002   CRITICAL     security             aws_db_instance.app_db                     RDS database instance set to publicly_accessible=true
  F003   HIGH         security             aws_s3_bucket.app_assets                   S3 bucket ACL changed from private to public-read
  F004   MEDIUM       best_practice        aws_db_instance.app_db                     deletion_protection is false on the database resource
  F005   MEDIUM       best_practice        aws_db_instance.app_db                     db_instance_class upsized from db.t3.small to db.t3.medium
  F006   LOW          best_practice        general                                    All four resources lack lifecycle prevent_destroy protections

  ────────────────────────────────────────────────────────────────────────
  [F001] ❗ CRITICAL — SSH ingress opened to the entire internet (0.0.0.0/0)

  The code diff explicitly changes ingress_ssh_cidr from 10.0.0.0/8 (a private RFC-1918
  range) to 0.0.0.0/0, exposing SSH (port 22) to all public IPs.

  Code: main.tf (lines 18-19)
  Plan: aws_security_group.web_sg (create)

  Recommendation:
  Revert ingress_ssh_cidr to a specific, restricted CIDR. Consider using AWS Systems
  Manager Session Manager to eliminate SSH exposure entirely.

  ────────────────────────────────────────────────────────────────────────
  [F002] ❗ CRITICAL — RDS database instance set to publicly_accessible=true

  ...
  ────────────────────────────────────────────────────────────────────────
  1,847 tokens in / 412 out · 3.2s · claude-sonnet-4-6 · anthropic
```

## Output Formats

```bash
tfrev review --plan plan.json --output table     # Terminal (default)
tfrev review --plan plan.json --output markdown  # PR comments
tfrev review --plan plan.json --output json      # Machine consumption
```

The `table` and `markdown` outputs include a summary footer showing token usage, review duration, model, and provider:

```
1,847 tokens in / 412 out · 3.2s · claude-sonnet-4-6 · anthropic
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Review passed |
| 1 | Review failed (findings at or above `--fail-on` severity) |
| 2 | Error (API failure, invalid input) |

## Cost

Each review is a single API call. Typical cost is $0.01–$0.10 per review depending on plan size and model. If the combined input exceeds the model's context window, tfrev drops context files to fit — it never splits into multiple calls.

When using AWS Bedrock, pricing is determined by your AWS Bedrock on-demand or provisioned throughput rates rather than the Anthropic API.

## License

MIT
