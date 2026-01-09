Triage the following GitHub issue.

Issue title:
{{TITLE}}

Labels:
{{LABELS}}

Last update summary (if any):
{{LAST_UPDATE_SUMMARY}}

Issue description (truncated if long):
{{BODY}}

Classify the issue based on:
- Implementation scope (how many files/components affected?)
- Required domain knowledge (can someone new to the codebase do this?)
- Clarity of requirements (is success clearly defined?)
- PR viability (could this realistically become a merged PR?)

Respond ONLY in JSON with this exact schema:

{
  "difficulty": "Low | Medium | High",
  "skill_match": "Yes | Maybe | No",
  "scope_clarity": "Clear | Somewhat Clear | Unclear",
  "test_focused": "Yes | No | Unclear",
  "risk_flags": ["optional short phrases"],
  "one_line_reason": "single sentence, no suggestions"
}
