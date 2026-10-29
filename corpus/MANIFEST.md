# Corpus Manifest

This document records the provenance, version, and cryptographic hash of all raw policy documents ingested into the system.

## Insurer & Product

| Field | Details |
|---|---|
| **Insurer** | HDFC ERGO General Insurance Company Limited |
| **Product Name** | my: Optima Secure |
| **IRDAI UIN** | HDFHLIP26058V082526 |
| **Registered Office** | 6th Floor, Leela Business Park, Andheri-Kurla Road, Andheri (East), Mumbai – 400 059 |
| **Document Type** | Policy Wording |

## Raw Documents

| File Name | Purpose | SHA-256 Checksum | Size (Bytes) | Source URL | Notes |
|---|---|---|---|---|---|
| `optima_secure_policy_wording.pdf` | Complete Policy Wording (69 pages) | `195eb0499db969c6789472e7f87ef1c72da110e2a8c7761ecb5add378fe964c1` | 925,936 | https://customer-portal-assets.hdfcergo.com/documents/PolicyWordings_myOptimaSecure-76673175551.pdf | Text layer present; no OCR needed |

## Key Clause Locations (Confirmed)

| Clause ID | Section | Page | Description |
|---|---|---|---|
| `B.1.1` | SECTION B — Benefits > Base Coverage > Hospitalization Expenses | 11 | Cover clause — includes "All Day Care Treatments" |
| `C.1.a` | SECTION C — Waiting Periods > Pre-Existing Diseases (Excl01) | 30 | 36-month PED waiting period |
| `C.1.b` | SECTION C — Waiting Periods > Specified Disease/Procedure (Excl02) | 31 | **24-month specific waiting period** — list includes "Cataract and other disorders of lens and Retina" |
| `C.1.c` | SECTION C — Waiting Periods > 30-day waiting period (Excl03) | 32 | 30-day initial waiting period (standard) |

## Notes
- Optima Secure covers **all** Day Care treatments (open list — no restricted procedure schedule). Day Care coverage is part of Section B.1.1.
- No explicit per-eye or INR sub-limit for cataract found in base policy text. Confirm with lecturer.
- No separate Day Care procedure list PDF exists for this product per HDFC ERGO's official communications.
