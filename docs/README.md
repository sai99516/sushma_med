# MediFind documentation

Start with the project [README](../README.md) (what MediFind is and how to run it). Then:

| # | Doc | Read it to learn |
|---|---|---|
| 1 | [USER_GUIDE.md](USER_GUIDE.md) | What each user can do and the rules (approval, requests, stock status, freshness, demo logins) |
| 2 | [ARCHITECTURE.md](ARCHITECTURE.md) | Parts of the system, the database (ER diagram), who may open what, and security |
| 3 | [TESTING.md](TESTING.md) | How to run the 197 unit tests and 70 browser tests, and what they cover |
| 4 | [DEPLOYMENT.md](DEPLOYMENT.md) | Environment variables, deploying to Render, backups |
| – | [REPORT_DRAFT.md](REPORT_DRAFT.md) | Draft of the final-year project report |

Pictures: [diagrams/](diagrams/) (use case, architecture, ER, request sequence, approval flow; `.mmd`
source and `.png`) and [screenshots/](screenshots/) (made by `scripts/take_screenshots.py`).

Outside this folder: [MEDIFIND_PRESENTATION.md](../MEDIFIND_PRESENTATION.md) (slides outline, demo script,
likely questions) and [MEDIFIND_REVIEW.md](../MEDIFIND_REVIEW.md) (append-only log of every review
finding and fix).

Wording rule: stock is **pharmacy-reported**, "what the pharmacy last reported", never checked by MediFind.
