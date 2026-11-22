# Status of the files in docs/

The files in this folder were generated during development. Many of them describe
older versions of the code. Nothing was deleted. For the current state of the code
use `README.md`, `MEDIFIND_REVIEW.md` (including its "Fix log" and "Status of all
findings") and the code itself.

Last checked: 2026-11-22, after the fixes on branch `fix/all`.

## Outdated or wrong (do not rely on them)

| File | What is outdated |
|---|---|
| SECURITY_FINAL_REVIEW.md, ADMIN_SECURITY_REVIEW.md, LOCATION_DISCOVERY_REPORT.md | Claim the maps were XSS-safe. They were not (N1); popups are now built with DOM nodes. |
| PRODUCTION_SECURITY_CHECKLIST.md, FINAL_QA_AUDIT_REPORT.md | Claimed no SECRET_KEY fallback and safe DEBUG/ALLOWED_HOSTS defaults. Only true after the fixes. |
| ENVIRONMENT_VARIABLES_GUIDE.md, ENVIRONMENT_AUDIT.md, PASSWORD_MANAGEMENT_REPORT.md | EMAIL_* variables were not read before (N6); defaults for DEBUG, HSTS and SSL redirect differ. Use `.env.example` / `.env.production.example`. |
| CUSTOMER_WORKFLOW_TEST_REPORT.md | Claimed POST logout before it existed (now true). |
| ROLE_PERMISSION_MATRIX.md | Role access, 404 vs redirect, `is_staff` meaning (is_staff alone is no longer an app admin), non-existent catalogue routes. |
| CURRENT_ARCHITECTURE.md, PHARMACY_REQUEST_MANAGEMENT.md, CUSTOMER_REQUEST_TRACKING.md | Request states. Now a request can be answered only once (PENDING only). |
| SERVICE_LAYER_DOCUMENTATION.md, BACKEND_ARCHITECTURE_REPORT.md | Say add-stock "increments" quantity; it **sets/replaces** it ("Set quantity"). Atomic claims, return types. |
| PHARMACY_GOVERNANCE_DOCUMENTATION.md, ADMIN_PORTAL_IMPLEMENTATION_REPORT.md | Approval was a toggle; now explicit approve/revoke with PENDING/APPROVED/REVOKED status, and re-approval after sensitive profile edits. |
| ER_DIAGRAM.md, DATABASE_ARCHITECTURE.md, DATABASE_STRUCTURE_AUDIT.md, INDEXING_STRATEGY.md | Missing `approval_status`, `Medicine.is_active`, Medicine unique constraint, PROTECT on requests; owner is now OneToOne with `related_name='pharmacy'`. |
| PHARMACY_SEARCH_DOCUMENTATION.md, MEDICINE_SEARCH_DOCUMENTATION.md, STOCK_MONITORING_REPORT.md | Sort options, 24h vs 48h freshness, search order (now In Stock, Low Stock, Out of Stock), DB-side pagination. |
| HAVERSINE_IMPLEMENTATION.md, LOCATION_TEST_REPORT.md | Sample distances do not match the formula; distance is now also computed in the database. |
| LANDING_PAGE_IMPLEMENTATION_REPORT.md | Home "City or Pincode" box: digits are now sent as pincode. |
| CUSTOMER_DASHBOARD_REPORT.md | Time zone was UTC; now Asia/Kolkata. |
| CODE_QUALITY_REPORT.md | Claimed no PII in logs (emails were logged; fixed, N27). |
| DEPENDENCY_AUDIT.md | Pillow removed; versions now pinned in requirements.txt. |
| QUERY_OPTIMIZATION_REPORT.md, ORM_OPTIMIZATION_REPORT.md, DATABASE_PERFORMANCE_TEST_REPORT.md, TECHNICAL_DEBT_REPORT.md | Query counts and the "load all rows" search are out of date. |
| TESTING_REPORT.md, FINAL_END_TO_END_QA_REPORT.md, BASELINE_TEST_RESULTS.md and the other *_TEST_REPORT.md files | Test counts and results are historical; tests were not re-run for these docs. |
| SYSTEM_ARCHITECTURE.md, IMPLEMENTATION_PLAN.md | Mention AJAX search, caching and request-trend charts that do not exist; colour palette differs from `static/css/styles.css`. |
| GIT_BACKUP_STRATEGY.md, DATABASE_BACKUP_AND_RECOVERY.md | Reference `scripts/backup_database.py` and `backups/` (do not exist); free Render Postgres has no backups. |
| PRODUCTION_DEPLOYMENT_GUIDE.md, HOSTING_PLATFORM_COMPARISON.md | Use README.md "Deploying to Render" and `render.yaml` instead (no wildcard CSRF origin, EMAIL_* variables). |
| SECURITY_AUDIT_REPORT.md, SECURITY_REMEDIATION_REPORT.md, PHARMACY_DASHBOARD_REPORT.md | Written before the security, approval and freshness fixes; status lists are out of date. |
| USER_GUIDE.md | Logout is a POST button, approval is explicit, requests are answered once, demo logins only show with DEBUG=True. |

## Probably still useful as background

AUTHENTICATION_IMPLEMENTATION_REPORT.md, FRONTEND_IMPLEMENTATION_REPORT.md,
MEDIFIND_BRANDING_REPORT.md, MODULE_DESIGN.md, RESPONSIVE_DESIGN_REPORT.md,
UI_UX_DESIGN_SYSTEM.md, USER_PROFILE_DOCUMENTATION.md, INVENTORY_MANAGEMENT_DOCUMENTATION.md,
CUSTOMER_NOTIFICATION_DOCUMENTATION.md, EXISTING_FEATURES_INVENTORY.md,
PROFESSIONAL_UPGRADE_ROADMAP.md, PROJECT_BASELINE_AUDIT.md (read them with the list above in mind).
