Triage the following GitHub issue.

Issue title:
{{TITLE}}

Labels:
{{LABELS}}

Issue description (truncated if long):
{{BODY}}

Recent comments (maintainer feedback is important):
{{COMMENTS}}

Classify the issue based on:
- Implementation scope (how many files/components affected?)
- Required domain knowledge (can someone less familar to the codebase do this?)
- Clarity of requirements (is success clearly defined?)
- PR viability (could this realistically become a merged PR?)

Respond ONLY in JSON with this exact schema:

{
  "difficulty": "Easy | Low | Medium | High | Beyond",
  "skill_match": "Yes | Maybe | No",
  "scope_clarity": "Clear | Somewhat Clear | Unclear",
  "test_focused": "Yes | No | Unclear",
  "risk_flags": ["optional short phrases"],
  "one_line_reason": "single sentence, no suggestions",
  "summary": "2-3 (max 10) sentence summary: what's the problem, what needs to be done, any blockers from comments"
}
