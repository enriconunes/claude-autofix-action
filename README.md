# Claude AutoFix Action

Automatically fixes failing Python tests using Claude AI, integrated with GitHub Actions.

## How to use

### 1. Add the API key to your repository Secrets

`Settings → Secrets and variables → Actions → New repository secret`

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your key from https://console.anthropic.com |

### 2. Create the workflow file in your project

Create the file `.github/workflows/autofix.yml` in your repository:

```yaml
name: Claude AutoFix

on:
  pull_request:
    branches: [ main ]

permissions:
  contents: write
  pull-requests: write

jobs:
  autofix:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Claude AutoFix
        uses: enriconunes/claude-autofix-action@v1
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### 3. Done

From this point on, whenever a PR has failing tests, Claude AI will:
1. Analyse the errors
2. Generate fixes
3. Automatically open a new PR with the corrected code

---

## Available options

```yaml
- uses: enriconunes/claude-autofix-action@v1
  with:
    anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}

    # Maximum number of fixes per run (default: 5)
    max-fixes: "3"

    # Python version to use (default: 3.11)
    python-version: "3.12"

    # Automatically create a PR with the fixes (default: true)
    create-pr: "true"
```

## Project requirements

- Tests using **pytest** following the `test_*.py` naming convention
- Source files in the same directory or accessible by pytest

## Cost estimate

| Usage | Cost/day | Cost/month (20 working days) |
|---|---|---|
| 1 PR/day, 1 failing test | ~$0.07 | ~$1.40 |
| 5 PRs/day, 2 failing tests | ~$0.70 | ~$14.00 |
| 10 PRs/day, 1 failing test | ~$0.69 | ~$13.80 |

> Prices based on the Claude Sonnet 4.5 model. Check [anthropic.com/pricing](https://anthropic.com/pricing) for current rates.
