"""Google Sheets persistence layer for issue triage."""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import Optional


class SheetsPersistence:
    """Manages issue triage data in Google Sheets."""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    LEDGER_HEADERS = [
        "Issue ID",
        "Title",
        "URL",
        "Labels",
        "Current Status",
        "LLM Difficulty",
        "LLM Skill Match",
        "Scope Clarity",
        "Test Focused",
        "Risk Flags",
        "Manual Confidence",
        "Reason",
        "Summary",
        "Last Checked At",
        "Updated At (GitHub)",
        "Needs Re-triage",
        "Auto Candidate",
        "Positive Signals",
    ]

    ACTIVE_HEADERS = ["Issue ID", "Title", "URL", "Difficulty", "Skill Match", "Summary", "Reason"]

    def __init__(
        self,
        credentials_path: str,
        spreadsheet_url: str,
    ):
        self.credentials_path = credentials_path
        self.spreadsheet_url = spreadsheet_url
        self._client = None
        self._spreadsheet = None

    def connect(self):
        """Establish connection to Google Sheets."""
        creds = Credentials.from_service_account_file(
            self.credentials_path,
            scopes=self.SCOPES,
        )
        self._client = gspread.authorize(creds)
        self._spreadsheet = self._client.open_by_url(self.spreadsheet_url)

    def setup_sheets(self):
        """Create required sheets if they don't exist, using Google Sheets Tables."""
        existing = [ws.title for ws in self._spreadsheet.worksheets()]

        if "Triage Ledger" not in existing:
            ledger = self._spreadsheet.add_worksheet("Triage Ledger", rows=1000, cols=len(self.LEDGER_HEADERS))
            ledger.update("A1", [self.LEDGER_HEADERS])
            ledger.freeze(rows=1)
            # Add dropdown validation for key columns
            self._add_dropdown_validation(ledger, "E", ["New", "Candidate", "In Progress", "PR Opened", "Completed", "Skipped", "Filtered"])
            self._add_dropdown_validation(ledger, "F", ["Easy", "Low", "Medium", "High", "Beyond"])
            self._add_dropdown_validation(ledger, "G", ["Yes", "Maybe", "No"])
        else:
            ledger = self._spreadsheet.worksheet("Triage Ledger")
            current_headers = ledger.row_values(1)
            if current_headers != self.LEDGER_HEADERS:
                ledger.update("A1", [self.LEDGER_HEADERS])

        if "Active Candidates" not in existing:
            active = self._spreadsheet.add_worksheet("Active Candidates", rows=500, cols=len(self.ACTIVE_HEADERS))
            active.update("A1", [self.ACTIVE_HEADERS])
            active.freeze(rows=1)
            self._add_dropdown_validation(active, "D", ["Easy", "Low", "Medium", "High", "Beyond"])
            self._add_dropdown_validation(active, "E", ["Yes", "Maybe", "No"])

        default_sheet = self._spreadsheet.worksheet("Sheet1") if "Sheet1" in existing else None
        if default_sheet and len(existing) > 1:
            try:
                self._spreadsheet.del_worksheet(default_sheet)
            except Exception:
                pass

    def _add_dropdown_validation(self, worksheet, column: str, options: list[str]):
        """Add dropdown data validation to a column."""
        sheet_id = worksheet.id
        col_index = ord(column.upper()) - ord('A')

        request = {
            "setDataValidation": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,  # Skip header
                    "endRowIndex": 1000,
                    "startColumnIndex": col_index,
                    "endColumnIndex": col_index + 1,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": opt} for opt in options]
                    },
                    "showCustomUi": True,
                    "strict": False,
                }
            }
        }

        try:
            self._spreadsheet.batch_update({"requests": [request]})
        except Exception as e:
            print(f"  Note: Could not add dropdown validation ({e}).")

    def get_existing_issues(self) -> dict[int, dict]:
        """Get all existing issues from the ledger as a dict keyed by issue ID."""
        ledger = self._spreadsheet.worksheet("Triage Ledger")
        try:
            records = ledger.get_all_records(expected_headers=self.LEDGER_HEADERS)
        except Exception:
            # Fallback: read raw values if headers don't match
            all_values = ledger.get_all_values()
            if len(all_values) <= 1:
                return {}
            headers = self.LEDGER_HEADERS
            records = []
            for row in all_values[1:]:
                record = {}
                for i, h in enumerate(headers):
                    record[h] = row[i] if i < len(row) else ""
                records.append(record)

        result = {}
        for record in records:
            issue_id = record.get("Issue ID")
            if issue_id:
                try:
                    result[int(issue_id)] = record
                except ValueError:
                    pass
        return result

    def upsert_issue(
        self,
        issue: dict,
        classification: Optional[dict] = None,
        filter_result: Optional[dict] = None,
        status: str = "New",
        existing_cache: Optional[dict] = None,
    ):
        """Insert or update an issue in the ledger."""
        ledger = self._spreadsheet.worksheet("Triage Ledger")
        existing = existing_cache if existing_cache is not None else self.get_existing_issues()
        issue_id = issue["issue_id"]

        row_data = self._build_row(issue, classification, filter_result, status)

        if issue_id in existing:
            row_num = self._find_row_by_issue_id(ledger, issue_id)
            if row_num:
                ledger.update(f"A{row_num}", [row_data])
        else:
            ledger.append_row(row_data)

    def _build_row(
        self,
        issue: dict,
        classification: Optional[dict],
        filter_result: Optional[dict],
        status: str,
    ) -> list:
        """Build a row for the ledger."""
        now = datetime.utcnow().isoformat()

        labels_str = ", ".join(issue.get("labels", []))
        risk_flags = ""
        positive_signals = ""

        if classification:
            risk_flags = ", ".join(classification.get("risk_flags", []))

        if filter_result:
            positive_signals = ", ".join(filter_result.get("positive_signals", []))

        return [
            issue.get("issue_id"),
            issue.get("title", "")[:100],
            issue.get("url", ""),
            labels_str,
            status,
            classification.get("difficulty", "") if classification else "",
            classification.get("skill_match", "") if classification else "",
            classification.get("scope_clarity", "") if classification else "",
            classification.get("test_focused", "") if classification else "",
            risk_flags,
            "",  # Manual Confidence - user fills
            classification.get("one_line_reason", "") if classification else "",
            classification.get("summary", "") if classification else "",
            now,
            issue.get("updated_at", ""),
            "FALSE",
            "TRUE" if filter_result and filter_result.get("is_auto_candidate") else "FALSE",
            positive_signals,
        ]

    def _find_row_by_issue_id(self, worksheet, issue_id: int) -> Optional[int]:
        """Find the row number for a given issue ID."""
        try:
            cell = worksheet.find(str(issue_id), in_column=1)
            return cell.row if cell else None
        except Exception:
            return None

    def mark_needs_retriage(self, issue_ids: list[int]):
        """Mark issues as needing re-triage."""
        ledger = self._spreadsheet.worksheet("Triage Ledger")

        for issue_id in issue_ids:
            row_num = self._find_row_by_issue_id(ledger, issue_id)
            if row_num:
                ledger.update(f"O{row_num}", [["TRUE"]])

    def update_active_candidates(self):
        """Update the Active Candidates sheet based on ledger data."""
        ledger = self._spreadsheet.worksheet("Triage Ledger")
        active = self._spreadsheet.worksheet("Active Candidates")

        # Use expected_headers to avoid duplicate header errors
        try:
            records = ledger.get_all_records(expected_headers=self.LEDGER_HEADERS)
        except Exception:
            records = self.get_existing_issues().values()

        candidates = []
        for record in records:
            status = record.get("Current Status", "")
            skill_match = record.get("LLM Skill Match", "")
            difficulty = record.get("LLM Difficulty", "")

            is_candidate = (
                status in ["New", "Candidate", ""]
                and skill_match in ["Yes", "Maybe"]
                and difficulty not in ["High", "Beyond"]
            )

            if is_candidate:
                candidates.append([
                    record.get("Issue ID"),
                    record.get("Title"),
                    record.get("URL"),
                    difficulty,
                    skill_match,
                    record.get("Summary", "")[:200],  # Truncate for readability
                    record.get("Reason"),
                ])

        active.clear()
        active.update("A1", [self.ACTIVE_HEADERS])

        if candidates:
            active.update("A2", candidates)

        active.freeze(rows=1)

    def get_issues_needing_retriage(self) -> list[int]:
        """Get list of issue IDs that need re-triage."""
        ledger = self._spreadsheet.worksheet("Triage Ledger")
        try:
            records = ledger.get_all_records(expected_headers=self.LEDGER_HEADERS)
        except Exception:
            records = self.get_existing_issues().values()

        return [
            int(r["Issue ID"])
            for r in records
            if r.get("Needs Re-triage", "").upper() == "TRUE"
        ]

    def batch_upsert(
        self,
        items: list[tuple[dict, dict, dict]],
        status: str = "New",
    ):
        """
        Batch upsert multiple issues.

        Args:
            items: List of (issue, classification, filter_result) tuples
            status: Default status for new issues
        """
        for issue, classification, filter_result in items:
            self.upsert_issue(issue, classification, filter_result, status)
