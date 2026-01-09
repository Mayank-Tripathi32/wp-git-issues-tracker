# GitHub Issue Triage Bot

A human-in-the-loop triage pipeline for WordPress/Gutenberg issues. Find suitable issues to work on and open PRs.

## Quick Start

```bash
pip install -r requirements.txt
python main.py test      # Verify setup
python main.py balance   # Check API credits
python main.py init      # Populate sheet with issues
python main.py picks     # See top issues to work on
```

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure `.env`** (copy from `.env.example`):
   - `GITHUB_TOKEN` - GitHub personal access token
   - `OPEN_ROUTER_KEY` - OpenRouter API key  
   - `SPREADSHEET_URL` - Google Sheets URL

3. **Share spreadsheet** with service account (Editor access):
   ```
   gshx-29@gen-lang-client-0823594345.iam.gserviceaccount.com
   ```

## Commands

| Command | Description |
|---------|-------------|
| `test` | Test all connections (GitHub, Sheets, OpenRouter) |
| `balance` | Check OpenRouter API credit balance |
| `init` | Initial triage - fetch, filter, classify issues |
| `update` | Daily run - check for new/changed issues |
| `retriage` | Re-evaluate flagged issues |
| `picks` | **Show top issues to work on** |
| `guide` | Show detailed usage guide |

### Examples

```bash
python main.py picks --limit 10    # Top 10 issues
python main.py init --max-pages 3  # Fetch 300 issues
python main.py update              # Daily update
python main.py guide               # Full usage guide
```

## Workflow

1. **Daily:** Run `python main.py picks` to see best issues
2. **Pick an issue:** Look for Low/Medium difficulty, Skill Match = Yes
3. **Track progress:** Update "Current Status" column in spreadsheet
4. **Open PR:** Mark as "PR Opened" when submitted

## What Makes a Good Issue?

The `picks` command scores issues by:
- **Difficulty:** Low > Medium (High excluded)
- **Skill Match:** Yes > Maybe
- **Test Focused:** Yes (easier to verify)
- **Flaky Tests:** Prioritized (clear scope, test-focused)

## Cost

Using Claude 3 Haiku via OpenRouter:
- ~$0.001 per issue classified
- Initial run (100 issues): ~$0.10
- Check balance: `python main.py balance`
