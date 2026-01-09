"""Main orchestrator for the issue triage pipeline."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

from .github_fetcher import GitHubFetcher
from .filters import IssueFilter, FilterResult
from .llm_classifier import LLMClassifier, Classification
from .sheets_persistence import SheetsPersistence


class TriageOrchestrator:
    """Orchestrates the full issue triage pipeline."""

    def __init__(
        self,
        github_token: str,
        openrouter_key: str,
        sheets_credentials: str,
        spreadsheet_url: str,
        repo: str = "WordPress/gutenberg",
        llm_model: str = "anthropic/claude-3-haiku",
        prompts_dir: str = "prompts",
    ):
        self.fetcher = GitHubFetcher(github_token, repo)
        self.filter = IssueFilter()
        self.classifier = LLMClassifier(openrouter_key, prompts_dir, llm_model)
        self.sheets = SheetsPersistence(sheets_credentials, spreadsheet_url)

        self._connected = False

    def connect(self):
        """Connect to Google Sheets and set up worksheets."""
        print("Connecting to Google Sheets...")
        self.sheets.connect()
        self.sheets.setup_sheets()
        self._connected = True
        print("Connected and sheets initialized.")

    def run_initial_triage(
        self,
        max_pages: int = 5,
        classify_candidates: bool = True,
        dry_run: bool = False,
    ) -> dict:
        """
        Run initial triage on open issues.

        Args:
            max_pages: Maximum pages of issues to fetch (100 per page)
            classify_candidates: Whether to run LLM classification
            dry_run: If True, don't write to sheets

        Returns:
            Summary statistics
        """
        if not self._connected:
            self.connect()

        print(f"\nFetching issues (max {max_pages} pages)...")
        issues = self.fetcher.fetch_open_issues(max_pages=max_pages)
        print(f"Fetched {len(issues)} open issues (excluding PRs)")

        existing = self.sheets.get_existing_issues()
        new_issues = [i for i in issues if i["issue_id"] not in existing]
        print(f"Found {len(new_issues)} new issues to process")

        print("\nApplying rule-based filters...")
        filtered = self.filter.filter_batch(new_issues)
        print(f"  {len(filtered)} issues passed filters")

        candidates = [(issue, fr) for issue, fr in filtered if fr.is_auto_candidate]
        non_candidates = [(issue, fr) for issue, fr in filtered if not fr.is_auto_candidate]
        print(f"  {len(candidates)} auto-candidates identified")

        results = []

        if classify_candidates and candidates:
            print(f"\nClassifying {len(candidates)} candidates with LLM (parallel, fetching comments)...")

            def process_candidate(item):
                issue, filter_result = item
                # Fetch comments for issues that have them
                if issue.get("comments_count", 0) > 0:
                    issue["recent_comments"] = self.fetcher.fetch_comments(
                        issue["issue_id"], max_comments=5
                    )
                classification = self.classifier.classify_issue(issue)
                return (issue, classification, filter_result)

            # Process in parallel with 5 workers (balance speed vs rate limits)
            completed = 0
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(process_candidate, item): item for item in candidates}
                for future in as_completed(futures):
                    issue, classification, filter_result = future.result()
                    completed += 1
                    print(f"  [{completed}/{len(candidates)}] #{issue['issue_id']}: {issue['title'][:50]}...")

                    # Post-classification filter: mark as Filtered if skill_match is No
                    classification_dict = self._classification_to_dict(classification)
                    if classification_dict and classification_dict.get("skill_match") == "No":
                        results.append((issue, classification_dict, self._filter_result_to_dict(filter_result), "Filtered"))
                    else:
                        results.append((issue, classification_dict, self._filter_result_to_dict(filter_result), "Candidate"))

        for issue, filter_result in non_candidates:
            results.append((
                issue,
                None,
                self._filter_result_to_dict(filter_result),
                "Filtered",
            ))

        if not dry_run and results:
            print(f"\nWriting {len(results)} issues to Google Sheets...")
            existing_cache = self.sheets.get_existing_issues()
            for i, (issue, classification, filter_result, status) in enumerate(results):
                self.sheets.upsert_issue(issue, classification, filter_result, status, existing_cache)
                if (i + 1) % 10 == 0:
                    print(f"  Written {i + 1}/{len(results)}...")

            print("Updating Active Candidates sheet...")
            self.sheets.update_active_candidates()

        return {
            "total_fetched": len(issues),
            "new_issues": len(new_issues),
            "passed_filters": len(filtered),
            "auto_candidates": len(candidates),
            "classified": len([r for r in results if r[1]]),
            "written": len(results) if not dry_run else 0,
        }

    def run_update(self, max_pages: int = 3) -> dict:
        """
        Run an update cycle: check for changes and re-triage as needed.

        Args:
            max_pages: Maximum pages of issues to fetch

        Returns:
            Summary statistics
        """
        if not self._connected:
            self.connect()

        print("\nFetching recent issues...")
        issues = self.fetcher.fetch_open_issues(max_pages=max_pages)
        existing = self.sheets.get_existing_issues()

        new_issues = []
        changed_issues = []

        for issue in issues:
            issue_id = issue["issue_id"]

            if issue_id not in existing:
                new_issues.append(issue)
            else:
                old = existing[issue_id]
                if self._has_meaningful_change(issue, old):
                    changed_issues.append(issue)

        print(f"Found {len(new_issues)} new, {len(changed_issues)} changed issues")

        if changed_issues:
            changed_ids = [i["issue_id"] for i in changed_issues]
            self.sheets.mark_needs_retriage(changed_ids)
            print(f"Marked {len(changed_ids)} issues for re-triage")

        if new_issues:
            filtered = self.filter.filter_batch(new_issues)
            candidates = [(i, fr) for i, fr in filtered if fr.is_auto_candidate]

            print(f"\nClassifying {len(candidates)} new candidates...")
            for issue, filter_result in candidates:
                classification = self.classifier.classify_issue(issue)
                self.sheets.upsert_issue(
                    issue,
                    self._classification_to_dict(classification),
                    self._filter_result_to_dict(filter_result),
                    "Candidate",
                )

            for issue, filter_result in filtered:
                if not filter_result.is_auto_candidate:
                    self.sheets.upsert_issue(
                        issue,
                        None,
                        self._filter_result_to_dict(filter_result),
                        "Filtered",
                    )

        self.sheets.update_active_candidates()

        return {
            "new_issues": len(new_issues),
            "changed_issues": len(changed_issues),
        }

    def retriage_flagged(self) -> dict:
        """Re-triage issues that have been flagged for re-evaluation."""
        if not self._connected:
            self.connect()

        flagged_ids = self.sheets.get_issues_needing_retriage()
        print(f"Found {len(flagged_ids)} issues needing re-triage")

        if not flagged_ids:
            return {"retriaged": 0}

        existing = self.sheets.get_existing_issues()

        for issue_id in flagged_ids:
            print(f"Re-triaging #{issue_id}...")

            try:
                issue = self.fetcher.fetch_single_issue(issue_id)
            except Exception as e:
                print(f"  Error fetching: {e}")
                continue

            old_data = existing.get(issue_id, {})
            previous = {
                "difficulty": old_data.get("LLM Difficulty"),
                "skill_match": old_data.get("LLM Skill Match"),
            }

            classification = self.classifier.classify_issue(
                issue,
                previous_classification=previous,
            )

            filter_result = self.filter.filter_issue(issue)

            self.sheets.upsert_issue(
                issue,
                self._classification_to_dict(classification),
                self._filter_result_to_dict(filter_result),
                "Re-triaged",
            )

        self.sheets.update_active_candidates()

        return {"retriaged": len(flagged_ids)}

    def _has_meaningful_change(self, issue: dict, old: dict) -> bool:
        """Check if an issue has changed meaningfully since last check."""
        if issue.get("updated_at") != old.get("Updated At (GitHub)"):
            return True

        old_labels = set(old.get("Labels", "").split(", "))
        new_labels = set(issue.get("labels", []))
        if old_labels != new_labels:
            return True

        return False

    def _classification_to_dict(self, c: Classification) -> Optional[dict]:
        """Convert Classification to dict for storage."""
        if c.error:
            return {
                "difficulty": "Error",
                "skill_match": "Error",
                "scope_clarity": "Error",
                "test_focused": "Error",
                "risk_flags": [c.error],
                "one_line_reason": f"Classification failed: {c.error}",
                "summary": "",
            }

        return {
            "difficulty": c.difficulty,
            "skill_match": c.skill_match,
            "scope_clarity": c.scope_clarity,
            "test_focused": c.test_focused,
            "risk_flags": c.risk_flags,
            "one_line_reason": c.one_line_reason,
            "summary": c.summary,
        }

    def _filter_result_to_dict(self, fr: FilterResult) -> dict:
        """Convert FilterResult to dict for storage."""
        return {
            "passed": fr.passed,
            "is_auto_candidate": fr.is_auto_candidate,
            "exclude_reason": fr.exclude_reason,
            "positive_signals": fr.positive_signals,
        }
