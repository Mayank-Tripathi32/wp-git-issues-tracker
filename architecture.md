1. Problem Statement

The Gutenberg repository contains a large volume of open issues with varying scope, complexity, and requirements. Manually identifying issues suitable for a contributor with limited domain knowledge and a focus on TypeScript, block development, and testing is time-consuming and inefficient. This leads to repeated evaluation of the same issues, reduced effective contribution time, and difficulty planning reliable 6–8 hour work sessions.

2. Goals and Success Criteria
Goals

Reduce time spent identifying suitable issues to under 15 minutes per session

Maintain a persistent record of triage decisions and rationale

Surface issues aligned with current skills (TypeScript, blocks, tests)

Avoid re-triaging unchanged issues

Enable predictable issue selection for time tracking and reporting

Success Criteria

At least 5–10 viable candidate issues identified within one workday

Clear separation between evaluated, skipped, and active issues

Demonstrated reduction in repeated issue reading

At least one issue completed using this system within two weeks

3. Non-Goals

Automated issue assignment or PR creation

General-purpose GitHub analytics platform

Code generation or solution proposals by LLMs

Real-time synchronization with GitHub

Multi-repository or team-wide support

4. High-Level System Overview

The system is a human-in-the-loop triage pipeline consisting of:

GitHub API ingestion of open issues

Rule-based filtering to eliminate unsuitable issues

LLM-based conservative classification

Google Sheets as the persistent triage ledger

Scheduled re-triage detection based on meaningful changes

The system prioritizes transparency, manual override, and low operational overhead.

5. Architecture Diagram (Conceptual)
GitHub Repo
   |
   | (GitHub REST API)
   v
Issue Fetcher
   |
   | (Rule-based filters)
   v
Candidate Issues
   |
   | (LLM classification)
   v
Triage Results
   |
   | (Append / Update)
   v
Google Sheets
   |
   | (Formula-based views)
   v
Active Work List

6. Component Design
6.1 GitHub Issue Ingestion

Responsibilities

Fetch open issues from WordPress/gutenberg

Exclude pull requests

Retrieve minimal necessary metadata

Data Retrieved

Issue ID

Title

URL

Labels

Body (truncated)

updated_at

Assignee (if any)

Linked PR presence (if available)

Design Decisions

Use GitHub REST API for simplicity

Authenticate using a personal access token

Fetch issues in batches to minimize requests

6.2 Rule-Based Filtering Layer

Purpose
Reduce noise before invoking LLMs.

Filtering Criteria

Exclude issues with labels:

blocker

High Priority

Needs Design

Flag issues with labels or keywords:

Needs Tests

Type: Bug

JavaScript

TypeScript

block

Output

Boolean flag: Auto Candidate

Rationale
Cheap, deterministic filtering reduces cost and cognitive load.

6.3 LLM Classification Service

Purpose
Conservatively assess suitability of issues.

Inputs

Issue title

Labels

Truncated issue body

Optional last-update summary

Outputs

Difficulty: Low / Medium / High

Skill match: Yes / Maybe / No

Scope clarity: Clear / Somewhat Clear / Unclear

Test-focused: Yes / No / Unclear

Risk flags (short phrases)

One-line rationale

Constraints

JSON-only output

One issue per call

No solution suggestions

Model Selection

Cheap, fast model via OpenRouter

Accuracy prioritized over creativity

6.4 Google Sheets Persistence Layer

Purpose
Serve as the system’s state store and user interface.

Sheet 1: Triage Ledger

Stores all evaluated issues.

Key Columns

Issue ID

Title

URL

Labels (last seen)

Current Status

LLM Difficulty

LLM Skill Match

Scope Clarity

Test Focused

Manual Confidence

Reason

Last Checked At

Needs Re-triage (boolean)

Sheet 2: Active Candidates

Formula-based view of viable issues.

Selection Criteria

Status = Candidate

Skill Match = Yes or Maybe

Difficulty ≠ High

Design Rationale
Sheets provide transparency, easy manual edits, sorting, and filtering without UI development.

6.5 Re-Triage Detection

Purpose
Avoid re-evaluating unchanged issues.

Triggers for Re-Triage

Issue updated_at changes

Label added or removed

Assignee changed

Linked PR opened or closed

Maintainer comment added

Behavior

Mark Needs Re-triage = true

Update Last Checked At

LLM classification runs only when flagged

7. Execution Model
Initial Run

Populate ledger with existing open issues

Run rule-based filters

Manually triage first batch

Run LLM classification on candidates

Ongoing Operation

Scheduled job runs daily or every 2–3 days

Fetch updates for known issues

Append new issues

Flag changed issues for re-triage

Update Active Candidates sheet

8. Configuration and Secrets

Environment Variables

GITHUB_TOKEN

OPENROUTER_API_KEY

GOOGLE_SHEETS_API_KEY (optional, CSV fallback allowed)

Security

Tokens stored locally or in environment

No credentials committed to version control

9. Operational Constraints

Time-boxed development: 1 working day

Manual override always allowed

System may be paused or abandoned without cleanup

Failures should degrade gracefully (e.g., skip LLM, keep ledger intact)

10. Risks and Mitigations
Risk	Mitigation
Over-automation	Human-in-the-loop design
LLM misclassification	Conservative prompts + manual override
Scope creep	Explicit non-goals
Sheet becoming messy	Early schema stabilization
API rate limits	Low-frequency scheduled runs
11. Metrics and Validation

Primary Metrics

Time to identify a suitable issue

Number of issues completed using the system

Reduction in repeated issue evaluation

Qualitative Signals

Confidence in issue selection

Reduced frustration during start-of-day workflow

12. Decommissioning Plan

If the system no longer provides value:

Stop scheduled jobs

Retain Google Sheets as a static record

No further maintenance required

13. Summary

This system is a pragmatic, low-cost, and human-centered approach to improving contribution efficiency in a large open-source repository. It balances automation with judgment, prioritizes developer experience, and is intentionally scoped to deliver value quickly without long-term maintenance burden.