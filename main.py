#!/usr/bin/env python3
"""
GitHub Issue Triage Bot

A human-in-the-loop triage pipeline for WordPress/Gutenberg issues.

Usage:
    python main.py <command> [options]

Commands:
    init      - First run: fetch issues, filter, classify, populate sheet
    update    - Daily run: check for new/changed issues
    retriage  - Re-evaluate issues marked for re-triage
    test      - Test all connections (GitHub, Sheets, OpenRouter)
    balance   - Check OpenRouter API credit balance
    guide     - Show detailed usage guide

Examples:
    python main.py test                    # Verify setup
    python main.py balance                 # Check API credits
    python main.py init --max-pages 3      # Initial run with 300 issues
    python main.py update                  # Daily update
"""

import argparse
import os
import sys
from dotenv import load_dotenv

from src.orchestrator import TriageOrchestrator
from src.llm_classifier import LLMClassifier


GUIDE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                        GITHUB ISSUE TRIAGE BOT - GUIDE                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

GOAL: Find suitable Gutenberg issues to work on and open PRs.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKFLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. FIRST TIME SETUP
   $ python main.py test      # Verify connections work
   $ python main.py balance   # Check you have API credits
   $ python main.py init      # Populate spreadsheet with issues

2. DAILY USAGE
   $ python main.py update    # Fetch new issues, flag changed ones
   → Open Google Sheet → Go to "Active Candidates" tab
   → Pick an issue with: Difficulty=Low/Medium, Skill Match=Yes/Maybe
   → Update "Current Status" column when you start working

3. FINDING GOOD ISSUES
   In your spreadsheet, look for:
   • Difficulty: Low or Medium (avoid High)
   • Skill Match: Yes or Maybe
   • Test Focused: Yes (easier to verify your fix)
   • Scope Clarity: Clear (well-defined requirements)
   
   Red flags to avoid:
   • Risk flags mentioning "architectural changes" or "breaking changes"
   • Issues with many comments (often contentious)
   • Issues assigned to someone else

4. TRACKING YOUR WORK
   Update the "Current Status" column:
   • Candidate  → Issue looks good to work on
   • In Progress → You're actively working on it
   • PR Opened  → You've submitted a PR
   • Completed  → PR merged
   • Skipped    → Decided not to pursue (update Reason column)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  test                  Test GitHub, Google Sheets, and OpenRouter connections
  balance               Show OpenRouter API credit balance
  init [--max-pages N]  Initial triage (default: 5 pages = 500 issues)
  update [--max-pages N] Check for new/changed issues (default: 3 pages)
  retriage              Re-classify issues flagged for re-evaluation
  guide                 Show this guide

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COST ESTIMATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Using Claude 3 Haiku via OpenRouter:
  • ~$0.001 per issue classified
  • Initial run (100 issues): ~$0.10
  • Daily update (10-20 issues): ~$0.02

Check your balance: python main.py balance
"""


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="GitHub Issue Triage Bot for WordPress/Gutenberg",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run 'python main.py guide' for detailed usage instructions."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Initial triage command
    init_parser = subparsers.add_parser("init", help="Run initial triage on open issues")
    init_parser.add_argument(
        "--max-pages", type=int, default=5,
        help="Maximum pages to fetch (100 issues per page, default: 5)"
    )
    init_parser.add_argument(
        "--all", action="store_true",
        help="Fetch ALL open issues (may take hours, ~$4-5 for full repo)"
    )
    init_parser.add_argument(
        "--no-classify", action="store_true",
        help="Skip LLM classification (just filter)"
    )
    init_parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview only, don't write to Google Sheets"
    )

    # Update command
    update_parser = subparsers.add_parser("update", help="Check for new/changed issues")
    update_parser.add_argument(
        "--max-pages", type=int, default=3,
        help="Maximum pages to fetch (default: 3)"
    )

    # Re-triage command
    subparsers.add_parser("retriage", help="Re-triage issues flagged for re-evaluation")

    # Test connection command
    subparsers.add_parser("test", help="Test all connections (GitHub, Sheets, OpenRouter)")

    # Balance check command
    subparsers.add_parser("balance", help="Check OpenRouter API credit balance")

    # Guide command
    subparsers.add_parser("guide", help="Show detailed usage guide")

    # Quick picks command
    picks_parser = subparsers.add_parser("picks", help="Show top issue picks from your sheet")
    picks_parser.add_argument(
        "--limit", type=int, default=10,
        help="Number of issues to show (default: 10)"
    )

    args = parser.parse_args()

    if args.command == "guide":
        print(GUIDE)
        sys.exit(0)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    github_token = os.getenv("GITHUB_TOKEN")
    openrouter_key = os.getenv("OPEN_ROUTER_KEY")
    spreadsheet_url = os.getenv("SPREADSHEET_URL")
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "google_service_account.json")
    repo = os.getenv("GITHUB_REPO", "WordPress/gutenberg")
    llm_model = os.getenv("LLM_MODEL", "anthropic/claude-3-haiku")

    missing = []
    if not github_token:
        missing.append("GITHUB_TOKEN")
    if not openrouter_key:
        missing.append("OPEN_ROUTER_KEY")
    if not spreadsheet_url:
        missing.append("SPREADSHEET_URL")

    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        print("Please check your .env file.")
        sys.exit(1)

    orchestrator = TriageOrchestrator(
        github_token=github_token,
        openrouter_key=openrouter_key,
        sheets_credentials=credentials_path,
        spreadsheet_url=spreadsheet_url,
        repo=repo,
        llm_model=llm_model,
    )

    if args.command == "balance":
        classifier = LLMClassifier(openrouter_key, model=llm_model)
        remaining, usage, formatted = classifier.check_balance()
        print("\n" + "=" * 50)
        print("OpenRouter Account Balance")
        print("=" * 50)
        print(formatted)
        if remaining < 0.10:
            print("\n⚠️  Warning: Low balance! Add credits at https://openrouter.ai/credits")
        else:
            print("\n✓ Balance OK")
        sys.exit(0)

    if args.command == "test":
        print("Testing connections...")
        try:
            orchestrator.connect()
            print("✓ Google Sheets connection successful")

            issues = orchestrator.fetcher.fetch_open_issues(max_pages=1)
            print(f"✓ GitHub API working ({len(issues)} issues fetched)")

            classifier = LLMClassifier(openrouter_key, model=llm_model)
            remaining, _, balance_str = classifier.check_balance()
            print(f"✓ OpenRouter API working ({balance_str})")

            print("\nAll connections working!")
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            sys.exit(1)

    elif args.command == "init":
        max_pages = None if args.all else args.max_pages
        if args.all:
            print("Running FULL triage (all open issues - this may take hours)...")
            remaining, _, _ = LLMClassifier(openrouter_key, model=llm_model).check_balance()
            if remaining < 5.0:
                print(f"⚠️  Warning: Only ${remaining:.2f} remaining. Full run may cost ~$4-5.")
                response = input("Continue? [y/N]: ")
                if response.lower() != 'y':
                    sys.exit(0)
        else:
            print("Running initial triage...")
        
        stats = orchestrator.run_initial_triage(
            max_pages=max_pages,
            classify_candidates=not args.no_classify,
            dry_run=args.dry_run,
        )
        print("\n" + "=" * 40)
        print("Summary:")
        print(f"  Total fetched:    {stats['total_fetched']}")
        print(f"  New issues:       {stats['new_issues']}")
        print(f"  Passed filters:   {stats['passed_filters']}")
        print(f"  Auto candidates:  {stats['auto_candidates']}")
        print(f"  Classified:       {stats['classified']}")
        print(f"  Written to sheet: {stats['written']}")

    elif args.command == "update":
        print("Running update cycle...")
        stats = orchestrator.run_update(max_pages=args.max_pages)
        print("\n" + "=" * 40)
        print("Summary:")
        print(f"  New issues:     {stats['new_issues']}")
        print(f"  Changed issues: {stats['changed_issues']}")

    elif args.command == "retriage":
        print("Re-triaging flagged issues...")
        stats = orchestrator.retriage_flagged()
        print("\n" + "=" * 40)
        print(f"Re-triaged: {stats['retriaged']} issues")

    elif args.command == "picks":
        print("Fetching top picks from your sheet...")
        orchestrator.connect()
        existing = orchestrator.sheets.get_existing_issues()

        picks = []
        for issue_id, data in existing.items():
            skill_match = data.get("LLM Skill Match", "")
            difficulty = data.get("LLM Difficulty", "")
            status = data.get("Current Status", "")
            title = data.get("Title", "")

            if status in ["In Progress", "PR Opened", "Completed", "Skipped"]:
                continue
            if skill_match not in ["Yes", "Maybe"]:
                continue
            if difficulty == "High":
                continue

            score = 0
            if skill_match == "Yes":
                score += 3
            if difficulty == "Low":
                score += 2
            elif difficulty == "Medium":
                score += 1
            if data.get("Test Focused") == "Yes":
                score += 2
            if data.get("Scope Clarity") == "Clear":
                score += 1
            if "[Flaky Test]" in title:
                score += 3

            picks.append((score, data))

        picks.sort(key=lambda x: x[0], reverse=True)

        print("\n" + "=" * 70)
        print("TOP PICKS - Best issues to work on")
        print("=" * 70)

        for i, (score, data) in enumerate(picks[:args.limit], 1):
            title = data.get("Title", "")[:45]
            difficulty = data.get("LLM Difficulty", "?")
            skill = data.get("LLM Skill Match", "?")
            url = data.get("URL", "")
            test_focused = "✓" if data.get("Test Focused") == "Yes" else " "
            scope = data.get("Scope Clarity", "?")[:5]
            reason = data.get("Reason", "")[:60]

            print(f"\n{i}. [{difficulty}] {title}...")
            print(f"   Skill: {skill} | Test: {test_focused} | Scope: {scope}")
            print(f"   {reason}")
            print(f"   {url}")

        print(f"\n{'=' * 70}")
        print(f"Showing {min(len(picks), args.limit)} of {len(picks)} candidates")


if __name__ == "__main__":
    main()
