"""LLM-based issue classification using OpenRouter."""

import json
import requests
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass
class Classification:
    """LLM classification result for an issue."""

    difficulty: str  # Low | Medium | High
    skill_match: str  # Yes | Maybe | No
    scope_clarity: str  # Clear | Somewhat Clear | Unclear
    test_focused: str  # Yes | No | Unclear
    risk_flags: list[str]
    one_line_reason: str
    summary: str = ""  # 2-3 sentence problem summary
    raw_response: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict, raw: str = None) -> "Classification":
        return cls(
            difficulty=data.get("difficulty", "Unknown"),
            skill_match=data.get("skill_match", "Unknown"),
            scope_clarity=data.get("scope_clarity", "Unknown"),
            test_focused=data.get("test_focused", "Unknown"),
            risk_flags=data.get("risk_flags", []),
            one_line_reason=data.get("one_line_reason", ""),
            summary=data.get("summary", ""),
            raw_response=raw,
        )

    @classmethod
    def error_result(cls, error_msg: str) -> "Classification":
        return cls(
            difficulty="Unknown",
            skill_match="Unknown",
            scope_clarity="Unknown",
            test_focused="Unknown",
            risk_flags=[],
            one_line_reason="",
            summary="",
            error=error_msg,
        )


class LLMClassifier:
    """Classifies GitHub issues using OpenRouter API."""

    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"
    DEFAULT_MODEL = "deepseek/deepseek-chat"  # Cheapest with excellent reasoning

    def __init__(
        self,
        api_key: str,
        prompts_dir: str = "prompts",
        model: str = DEFAULT_MODEL,
    ):
        self.api_key = api_key
        self.model = model
        self.prompts_dir = Path(prompts_dir)
        self._load_prompts()

    def check_balance(self) -> Tuple[float, float, str]:
        """
        Check OpenRouter account balance.

        Returns:
            Tuple of (balance, usage, formatted_string)
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            response = requests.get(self.OPENROUTER_CREDITS_URL, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json().get("data", {})

            balance = data.get("total_credits", 0) or 0
            usage = data.get("total_usage", 0) or 0
            remaining = balance - usage

            formatted = f"Balance: ${balance:.4f} | Used: ${usage:.4f} | Remaining: ${remaining:.4f}"
            return remaining, usage, formatted
        except Exception as e:
            return 0, 0, f"Error checking balance: {e}"

    def _load_prompts(self):
        """Load prompt templates from files."""
        self.system_prompt = (self.prompts_dir / "system.md").read_text()
        self.user_template = (self.prompts_dir / "user-template.md").read_text()
        self.retriage_template = (self.prompts_dir / "re-triage.md").read_text()

    def classify_issue(
        self,
        issue: dict,
        last_update_summary: str = "",
        previous_classification: Optional[dict] = None,
    ) -> Classification:
        """
        Classify a single issue using the LLM.

        Args:
            issue: Issue dictionary with title, labels, body
            last_update_summary: Optional summary of recent changes
            previous_classification: Previous classification for re-triage

        Returns:
            Classification result
        """
        user_prompt = self._build_user_prompt(issue, last_update_summary)

        if previous_classification:
            user_prompt += "\n\n" + self.retriage_template.replace(
                "{{OLD_DIFFICULTY}}", previous_classification.get("difficulty", "Unknown")
            ).replace(
                "{{OLD_MATCH}}", previous_classification.get("skill_match", "Unknown")
            )

        try:
            response = self._call_api(user_prompt)
            return self._parse_response(response)
        except Exception as e:
            return Classification.error_result(str(e))

    def _build_user_prompt(self, issue: dict, last_update_summary: str) -> str:
        """Build the user prompt from template and issue data."""
        labels_str = ", ".join(issue.get("labels", [])) or "None"

        comments_str = "None"
        if issue.get("recent_comments"):
            comment_lines = []
            for c in issue["recent_comments"][:5]:
                prefix = "[MAINTAINER] " if c.get("is_maintainer") else ""
                comment_lines.append(f"- {prefix}{c['author']}: {c['body'][:300]}")
            comments_str = "\n".join(comment_lines) if comment_lines else "None"

        return (
            self.user_template.replace("{{TITLE}}", issue.get("title", ""))
            .replace("{{LABELS}}", labels_str)
            .replace("{{COMMENTS}}", comments_str)
            .replace("{{BODY}}", issue.get("body", "")[:2000])
        )

    def _call_api(self, user_prompt: str) -> str:
        """Call the OpenRouter API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 500,
        }

        response = requests.post(
            self.OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _parse_response(self, response: str) -> Classification:
        """Parse the LLM response into a Classification."""
        content = response.strip()

        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        try:
            data = json.loads(content)
            return Classification.from_json(data, response)
        except json.JSONDecodeError as e:
            return Classification.error_result(f"JSON parse error: {e}\nRaw: {response[:200]}")

    def classify_batch(
        self,
        issues: list[dict],
        on_progress: callable = None,
    ) -> list[tuple[dict, Classification]]:
        """
        Classify a batch of issues.

        Args:
            issues: List of issue dictionaries
            on_progress: Optional callback(current, total, issue)

        Returns:
            List of (issue, classification) tuples
        """
        results = []
        total = len(issues)

        for i, issue in enumerate(issues):
            if on_progress:
                on_progress(i + 1, total, issue)

            classification = self.classify_issue(issue)
            results.append((issue, classification))

        return results
