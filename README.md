# Claude AutoFix Action

Automatically detects failing Python tests in Pull Requests, posts a diagnosis comment, generates a fix using Claude AI, and opens a new PR with the corrected code.

---

## How it works

```
1. You open a PR with a bug → tests fail
2. Claude analyses the failures → posts a comment with the diagnosis
3. Claude generates the fix → opens a new PR with the corrected code
4. You review and merge the fix PR
```

---

## Step 1 — Create a GitHub repository

Go to [github.com](https://github.com) and create a new repository. Make it **public**.

After creating it, configure two permissions:

**1.1 — Allow Actions to write to the repository**

`Settings → Actions → General → Workflow permissions`

- Select **"Read and write permissions"**
- Check **"Allow GitHub Actions to create and approve pull requests"**
- Click **Save**

**1.2 — Add your Anthropic API key**

`Settings → Secrets and variables → Actions → New repository secret`

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your key from [console.anthropic.com](https://console.anthropic.com) |

> **How to get the API key:** create a free account at [console.anthropic.com](https://console.anthropic.com), go to **API Keys → Create Key**, copy the key and paste it as the secret value.

---

## Step 2 — Set up your Python project

Your project must follow this structure:

```
my-project/
├── .github/
│   └── workflows/
│       └── autofix.yml       ← workflow file (created below)
├── functions/
│   └── my_module.py          ← your source code
├── tests/
│   └── test_my_module.py     ← your tests
└── pytest.ini                ← pytest configuration
```

**`pytest.ini`** — required so pytest finds your tests:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

**`.github/workflows/autofix.yml`** — the workflow that triggers the action:

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

---

## Step 3 — Basic Git workflow

If you are new to Git, follow these steps every time you want to test a change.

**Clone your repository locally (first time only):**

```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

**Create a new branch for your changes:**

```bash
git checkout -b branch-with-error
```

**Make your changes** (edit files, introduce a bug to test, etc.)

**Stage and commit your changes:**

```bash
git add .
git commit -m "add my changes"
```

**Push the branch to GitHub:**

```bash
git push -u origin branch-with-error
```

**Open a Pull Request on GitHub:**

1. Go to your repository on GitHub
2. Click **"Compare & pull request"** (yellow banner) or go to **Pull requests → New pull request**
3. Set base: `main` ← compare: `branch-with-error`
4. Click **"Create pull request"**

The Claude AutoFix Action will trigger automatically when the PR is opened.

---

## Step 4 — What happens after you open the PR

**If tests pass:** nothing happens, the action completes silently.

**If tests fail:**

1. Claude posts a comment on your PR with the diagnosis:
   ```
   **File:** `functions/dividir.py` | **Line:** 2
   **Error:** expected `5`, got `8`
   **Cause:** The function uses subtraction (-) instead of division (/).
   **Fix:** change `return a - b` to `return a / b`
   ```

2. Claude opens a new PR with the corrected code (e.g. `claude-auto-fix-20260308-172609`)

3. A second comment is posted on your PR with a link to the fix PR

---

## Step 5 — Merging the fix

When Claude opens a fix PR, you have two options:

**Option A — Merge the fix into your branch, then merge to main:**

```bash
# Switch to your branch
git checkout branch-with-error

# Merge the fix branch into your branch
git merge claude-auto-fix-TIMESTAMP

# Push the updated branch
git push origin branch-with-error
```

Then go to GitHub and merge `branch-with-error` → `main`.

**Option B — Merge the fix PR directly into main (via GitHub UI)**

Review the fix PR, confirm the changes look correct, and click **"Merge pull request"**.

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

---

## Requirements

- Tests written with **pytest** following the `test_*.py` naming convention
- Test files in a `tests/` folder (or root directory)
- Source files in a `functions/`, `src/`, or root directory

---

## Cost estimate

Each failing test generates ~2 API calls to Claude (analysis + fix).

| Usage | Cost/day | Cost/month (20 working days) |
|---|---|---|
| 1 PR/day, 1 failing test | ~$0.07 | ~$1.40 |
| 5 PRs/day, 2 failing tests | ~$0.70 | ~$14.00 |
| 10 PRs/day, 1 failing test | ~$0.69 | ~$13.80 |

> Prices based on Claude Sonnet 4.5. Check [anthropic.com/pricing](https://anthropic.com/pricing) for current rates.
