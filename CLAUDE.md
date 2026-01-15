# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository implements **AI-powered automated test fixing** using Claude AI (Anthropic API) integrated into GitHub Actions workflows. The system automatically analyzes failing tests in Pull Requests, generates fixes, and creates new PRs with the corrections.

**Key Concept**: The Python files in the root directory (`dividir.py`, `media.py`, etc.) are **test fixtures** used to demonstrate and validate the workflows. They are intentionally simple and contain bugs to trigger the auto-fix workflows. The real value of this repository is the **reusable GitHub Actions workflows** that can be integrated into any Python project.

## Architecture

### Workflow Execution Flow

```
1. Developer creates PR → main
2. claude-ci.yml triggers:
   - Runs pytest with JSON reporting
   - Sends failures to Claude AI for analysis
   - Posts analysis comment on PR

3. If tests fail → claude-auto-fix.yml triggers:
   - Detects the failing branch
   - Runs tests again to generate failure report
   - Sends failures to Claude AI for code fixes
   - Applies fixes to actual source files
   - Creates new fix branch (claude-auto-fix-TIMESTAMP)
   - Creates PR with fixes → original failing branch
   - Comments on original PR with link to fix PR
```

### Core Components

#### 1. GitHub Actions Workflows (`.github/workflows/`)

**`claude-ci.yml`** - Main CI workflow
- Triggers: Pull requests to `main`
- Runs pytest with JSON report generation
- Calls `ci/claude_report.py` to analyze failures
- Posts AI analysis as PR comment
- Uses: `ANTHROPIC_API_KEY` secret

**`claude-auto-fix.yml`** - Auto-fix workflow
- Triggers: When `claude-ci.yml` fails OR manual dispatch
- Detects the source branch that failed
- Generates fixes using `ci/claude_fix.py`
- **Critical**: Uses `git add -u` (only tracked files) to avoid committing temporary files
- Creates PR with fixes automatically
- Posts comment with PR link on original PR
- Uses: `ANTHROPIC_API_KEY` secret

#### 2. Python Scripts (`ci/`)

**`claude_report.py`** - Test failure analyzer
- Parses pytest JSON report (`.report.json`)
- Sends failures to Claude API with full context (source code, traceback, test info)
- Generates markdown analysis for PR comments
- Uses Claude Sonnet 4.5 by default
- Fallback models: Sonnet 4, Claude 3.5 Sonnet

**`claude_fix.py`** - Automated code fixer
- Reads pytest failures
- Infers source files from test names (e.g., `test_dividir.py` → `dividir.py`)
- Requests complete corrected files from Claude AI
- Applies fixes directly to source files (when `--apply` flag used)
- Saves debug info to `claude-patches/` directory
- Limits to 5 fixes per run to prevent overwhelming changes

### Key Technical Details

#### File Inference Logic
The auto-fix script automatically infers which source file to fix from test file names:
- Pattern: `test_<module>.py` → `<module>.py`
- Example: `test_dividir.py::test_dividir_ok` → fixes `dividir.py`
- Falls back to traceback inspection if inference fails

#### Temporary Files Management
The following files are generated but **intentionally not committed**:
- `.report.json` - pytest JSON report
- `claude_comment.md` - PR comment content
- `claude-patches/` - debug info and fix previews

These are defined in `.gitignore` and the workflow uses `git add -u` (update tracked files only) to ensure they're never accidentally committed.

#### Claude API Integration
- Endpoint: `https://api.anthropic.com/v1/messages`
- Model: `claude-sonnet-4-5-20250929` (Sonnet 4.5)
- API version: `2023-06-01`
- Max tokens: 4096 per response
- Retry logic: Automatic fallback to older models if primary fails
- Rate limiting: Built-in retry with 2-second delay for 529 errors

## Setup Instructions for New Projects

### 1. Required GitHub Secret
Add `ANTHROPIC_API_KEY` to repository secrets:
- Go to: Settings → Secrets and variables → Actions
- Create secret: `ANTHROPIC_API_KEY`
- Value: Your Anthropic API key from https://console.anthropic.com/

### 2. Copy Required Files
```bash
# Copy workflows
cp -r .github/workflows/claude-*.yml <target-project>/.github/workflows/

# Copy Python scripts
cp -r ci/ <target-project>/ci/

# Update .gitignore
cat >> <target-project>/.gitignore << EOF
# Claude CI temporary files
.report.json
claude_comment.md
claude-patches/
EOF
```

### 3. Dependencies
Add to target project's test environment:
```bash
pip install pytest pytest-json-report
```

### 4. Verify Configuration
- Ensure tests are runnable with: `pytest --json-report`
- Verify test files follow `test_*.py` naming convention
- Ensure source files are in same directory or predictable location

## Development Commands

### Testing Workflows Locally

```bash
# Generate test report (simulates what CI does)
pytest --json-report

# Test Claude analysis (requires ANTHROPIC_API_KEY env var)
export ANTHROPIC_API_KEY="your-key"
python ci/claude_report.py --report .report.json --comment-file claude_comment.md

# Test auto-fix generation (dry run - doesn't apply)
python ci/claude_fix.py --report .report.json --output-dir claude-patches

# Test auto-fix with application
python ci/claude_fix.py --report .report.json --apply --max-fixes 5
```

### Manual Workflow Trigger

To manually trigger auto-fix on a specific branch:
1. Go to: Actions → Claude Auto-Fix → Run workflow
2. Select the branch
3. Click "Run workflow"

## Workflow Customization

### Changing Claude Model
Set environment variable `CLAUDE_MODEL` in workflow:
```yaml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  CLAUDE_MODEL: "claude-opus-4-5-20251101"  # Use Opus instead
```

### Adjusting Fix Limit
Modify `--max-fixes` parameter in `claude-auto-fix.yml`:
```yaml
python ci/claude_fix.py --report .report.json --apply --max-fixes 10
```

### Changing Target Branch
By default, workflows target `main`. To change:
```yaml
on:
  pull_request:
    branches: [ main, develop ]  # Add more branches
```

## Important Notes

### Git Operations
- The workflow uses `git add -u` instead of `git add .` to avoid committing temporary files
- Only modified tracked files are included in fix commits
- Fix branches are named: `claude-auto-fix-YYYYMMDD-HHMMSS`

### API Costs
- Each failing test generates ~2 API calls (analysis + fix)
- Sonnet 4.5 pricing applies (check Anthropic pricing)
- Consider setting `--max-fixes` to control costs on large test suites

### Limitations
- Currently Python/pytest only
- Requires test files to follow `test_*.py` convention
- Source file inference may fail for complex project structures
- Claude may not always generate correct fixes (review required)

### Security
- Never commit `ANTHROPIC_API_KEY` to repository
- Store only in GitHub Secrets
- Workflows run with minimum required permissions
- Fix PRs require manual review and approval before merging
