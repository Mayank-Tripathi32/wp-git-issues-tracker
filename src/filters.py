"""Rule-based filtering for GitHub issues."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FilterResult:
    """Result of applying filters to an issue."""

    passed: bool
    is_auto_candidate: bool
    exclude_reason: Optional[str] = None
    positive_signals: list[str] = None

    def __post_init__(self):
        if self.positive_signals is None:
            self.positive_signals = []


class IssueFilter:
    """Rule-based filter for GitHub issues."""

    EXCLUDE_LABELS = {
        "blocker",
        "[Status] Blocked",
        "[Priority] High",
        "Needs Design",
        "Needs Design Feedback",
        "[Status] Stale",
    }

    POSITIVE_LABELS = {
        "Needs Tests",
        "Good First Issue",
        "good first issue",
        "[Type] Bug",
        "[Type] Enhancement",
        "JavaScript",
        "TypeScript",
        "[Block]",
        "[Package]",
        "Unit Tests",
        "e2e Tests",
        "[Type] Automated Testing",
    }

    HIGH_VALUE_PATTERNS = [
        "[Flaky Test]",
        "Good First Issue",
        "good first issue",
    ]

    POSITIVE_KEYWORDS = {
        "test",
        "tests",
        "testing",
        "block",
        "blocks",
        "typescript",
        "javascript",
        "unit test",
        "e2e",
        "snapshot",
    }

    def filter_issue(self, issue: dict) -> FilterResult:
        """
        Apply rule-based filters to an issue.

        Args:
            issue: Issue dictionary with labels, title, body

        Returns:
            FilterResult with pass/fail status and signals
        """
        labels = set(issue.get("labels", []))
        title = issue.get("title", "")
        title_lower = title.lower()
        body_lower = (issue.get("body") or "").lower()

        for exclude_label in self.EXCLUDE_LABELS:
            if exclude_label in labels:
                return FilterResult(
                    passed=False,
                    is_auto_candidate=False,
                    exclude_reason=f"Excluded label: {exclude_label}",
                )

        positive_signals = []

        for pattern in self.HIGH_VALUE_PATTERNS:
            if pattern.lower() in title_lower or pattern in labels:
                positive_signals.append(f"High-value: {pattern}")

        for pos_label in self.POSITIVE_LABELS:
            for label in labels:
                if pos_label.lower() in label.lower():
                    positive_signals.append(f"Label: {label}")
                    break

        text_content = f"{title_lower} {body_lower}"
        for keyword in self.POSITIVE_KEYWORDS:
            if keyword in text_content:
                positive_signals.append(f"Keyword: {keyword}")

        is_auto_candidate = len(positive_signals) >= 2

        return FilterResult(
            passed=True,
            is_auto_candidate=is_auto_candidate,
            positive_signals=positive_signals,
        )

    def is_high_value(self, issue: dict) -> bool:
        """Check if an issue matches high-value patterns (flaky tests, good first issue)."""
        title = issue.get("title", "")
        labels = set(issue.get("labels", []))

        for pattern in self.HIGH_VALUE_PATTERNS:
            if pattern in title or pattern in labels:
                return True
        return False

    def filter_batch(self, issues: list[dict]) -> list[tuple[dict, FilterResult]]:
        """Filter a batch of issues, returning issues that passed with their results."""
        results = []
        for issue in issues:
            result = self.filter_issue(issue)
            if result.passed:
                results.append((issue, result))
        return results
