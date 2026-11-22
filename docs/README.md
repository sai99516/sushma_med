# MediFind documentation

**Purpose:** Index of the project docs, with a suggested reading order.
**Who it is for:** Anyone new to the project (students, reviewers, examiners).
**Last verified:** 2026-11-22 against commit `dd2f32c`.

Start with the project [README](../README.md) (what MediFind is and how to run it). Then read these,
in this order:

| # | Doc | Read it to learn |
|---|---|---|
| 1 | [USER_GUIDE.md](USER_GUIDE.md) | What each user can do and the rules: approval, requests, stock status, freshness, search order, demo logins |
| 2 | [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Folder map, how a request flows (URL → view → service → template), distance and maps, "where do I find X" |
| 3 | [ROLE_PERMISSION_MATRIX.md](ROLE_PERMISSION_MATRIX.md) | Who can open each of the 40 URLs and what happens to everyone else |
| 4 | [DATABASE_ARCHITECTURE.md](DATABASE_ARCHITECTURE.md) | The 6 models, relations, constraints, indexes and migrations |
| 5 | [SECURITY_FINAL_REVIEW.md](SECURITY_FINAL_REVIEW.md) | Security controls (settings, login rate limit, CSRF, XSS) and known gaps |
| 6 | [ENVIRONMENT_VARIABLES_GUIDE.md](ENVIRONMENT_VARIABLES_GUIDE.md) | Local setup and every environment variable with its default |
| 7 | [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md) | Deploying to Render, production checklist, backups |
| 8 | [TESTING_REPORT.md](TESTING_REPORT.md) | Running the 160 unit tests and 68 browser tests, and what they cover |

Outside this folder:

- [MEDIFIND_REVIEW.md](../MEDIFIND_REVIEW.md): the history log of every review finding, fix and test run.
  It is append-only.
- [MEDIFIND_PRESENTATION.md](../MEDIFIND_PRESENTATION.md): slides outline, 5-minute demo script and likely questions.

## Historical files

The other 60 files in this folder were one-time reports or older specs from development. Each one is now a
3-line note that points to the current doc; the original text is still in git history
(`git show dd2f32c:docs/<FILE>.md`). "Merged" means the parts that were still true were moved into
the current doc.

| Now covered by | Merged | Replaced (one-time reports) |
|---|---|---|
| USER_GUIDE.md | CUSTOMER_NOTIFICATION_DOCUMENTATION, CUSTOMER_REQUEST_TRACKING, INVENTORY_MANAGEMENT_DOCUMENTATION, PHARMACY_GOVERNANCE_DOCUMENTATION, PHARMACY_REQUEST_MANAGEMENT, STOCK_MONITORING_REPORT, USER_PROFILE_DOCUMENTATION | CUSTOMER_DASHBOARD_REPORT, EXISTING_FEATURES_INVENTORY, PHARMACY_DASHBOARD_REPORT |
| SYSTEM_ARCHITECTURE.md | CURRENT_ARCHITECTURE, HAVERSINE_IMPLEMENTATION, LOCATION_DISCOVERY_REPORT, MEDICINE_SEARCH_DOCUMENTATION, MODULE_DESIGN, PHARMACY_SEARCH_DOCUMENTATION, SERVICE_LAYER_DOCUMENTATION, UI_UX_DESIGN_SYSTEM | BACKEND_ARCHITECTURE_REPORT, CODE_QUALITY_REPORT, FRONTEND_IMPLEMENTATION_REPORT, IMPLEMENTATION_PLAN, LANDING_PAGE_IMPLEMENTATION_REPORT, MEDIFIND_BRANDING_REPORT, RESPONSIVE_DESIGN_REPORT |
| ROLE_PERMISSION_MATRIX.md | – | ADMIN_PORTAL_IMPLEMENTATION_REPORT |
| DATABASE_ARCHITECTURE.md | DATABASE_STRUCTURE_AUDIT, ER_DIAGRAM, INDEXING_STRATEGY | ORM_OPTIMIZATION_REPORT, QUERY_OPTIMIZATION_REPORT |
| SECURITY_FINAL_REVIEW.md | AUTHENTICATION_IMPLEMENTATION_REPORT, PASSWORD_MANAGEMENT_REPORT | ADMIN_SECURITY_REVIEW, SECURITY_AUDIT_REPORT, SECURITY_REMEDIATION_REPORT |
| ENVIRONMENT_VARIABLES_GUIDE.md | – | DEPENDENCY_AUDIT, ENVIRONMENT_AUDIT |
| PRODUCTION_DEPLOYMENT_GUIDE.md | DATABASE_BACKUP_AND_RECOVERY, PRODUCTION_SECURITY_CHECKLIST | GIT_BACKUP_STRATEGY, HOSTING_PLATFORM_COMPARISON |
| TESTING_REPORT.md | – | ADMIN_TEST_REPORT, ADMIN_WORKFLOW_TEST_REPORT, AUTHENTICATION_TEST_REPORT, BASELINE_TEST_RESULTS, CUSTOMER_DASHBOARD_TEST_REPORT, CUSTOMER_WORKFLOW_TEST_REPORT, DATABASE_PERFORMANCE_TEST_REPORT, FINAL_END_TO_END_QA_REPORT, FINAL_QA_AUDIT_REPORT, LOCATION_TEST_REPORT, MEDICINE_DISCOVERY_TEST_REPORT, PHARMACY_DASHBOARD_TEST_REPORT, PHARMACY_WORKFLOW_TEST_REPORT, SECURITY_TEST_REPORT |
| ../MEDIFIND_REVIEW.md | – | PROFESSIONAL_UPGRADE_ROADMAP, PROJECT_BASELINE_AUDIT, TECHNICAL_DEBT_REPORT |
| this README | – | README_DOCS_STATUS |

Wording rule for all docs: stock is **pharmacy-reported**. Do not describe it as live, real-time or verified.
