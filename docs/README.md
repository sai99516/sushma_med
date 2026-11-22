# MediFind documentation

**Purpose:** Index of the project docs, with a suggested reading order.
**Who it is for:** Anyone new to the project (students, reviewers, examiners).
**Last verified:** 2026-11-22 against commit `513e68f`.

Start with the project [README](../README.md) (what MediFind is and how to run it). Then read these,
in this order:

| # | Doc | Read it to learn |
|---|---|---|
| 1 | [USER_GUIDE.md](USER_GUIDE.md) | What each user can do and the rules: approval and its history, requests, stock status, freshness, search order, demo logins |
| 2 | [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Folder map, how a request flows (URL → view → service → template), distance and maps, "where do I find X" |
| 3 | [ROLE_PERMISSION_MATRIX.md](ROLE_PERMISSION_MATRIX.md) | Who can open each of the 40 URLs and what happens to everyone else |
| 4 | [DATABASE_ARCHITECTURE.md](DATABASE_ARCHITECTURE.md) | The 7 models, relations, constraints, indexes and migrations |
| 5 | [SECURITY_FINAL_REVIEW.md](SECURITY_FINAL_REVIEW.md) | Security controls (settings, login rate limit, CSRF, XSS) and known gaps |
| 6 | [ENVIRONMENT_VARIABLES_GUIDE.md](ENVIRONMENT_VARIABLES_GUIDE.md) | Local setup and every environment variable with its default |
| 7 | [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md) | Deploying to Render, production checklist, backups |
| 8 | [TESTING_REPORT.md](TESTING_REPORT.md) | Running the 178 unit tests and 69 browser tests, lint and CI, and what they cover |

Outside this folder:

- [MEDIFIND_REVIEW.md](../MEDIFIND_REVIEW.md): the history log of every review finding, fix and test run.
  It is append-only.
- [MEDIFIND_PRESENTATION.md](../MEDIFIND_PRESENTATION.md): slides outline, 5-minute demo script and likely questions.

Wording rule for all docs: stock is **pharmacy-reported**. Describe it as "what the pharmacy last reported", never as checked by MediFind.
