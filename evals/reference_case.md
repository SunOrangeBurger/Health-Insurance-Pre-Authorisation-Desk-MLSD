# HDFC ERGO my: Optima Secure — Reference Case Clauses

**Corpus Document:** HDFC ERGO my: Optima Secure Policy Wording  
**UIN:** HDFHLIP26058V082526  
**Pages:** 69  
**Source URL:** https://customer-portal-assets.hdfcergo.com/documents/PolicyWordings_myOptimaSecure-76673175551.pdf  

> ⚠️ These passages are extracted verbatim from the PDF. Clause IDs are assigned by our ingestion pipeline using the document's section numbering. Confirm with lecturer before freezing.

---

## Reference Case 4.1: Cataract Surgery — Policy issued 11 months ago

### Test Request Parameters
| Field | Value |
|---|---|
| `admission_type` | `day_care` |
| `procedure_text` | `Phacoemulsification with IOL, right eye` |
| `diagnosis_text` | `Cataract, right eye` |
| `policy_issue_date` | `<admission_date> minus 11 months` |
| `policy_start_date` | same as `policy_issue_date` |
| `planned_admission_date` | synthetic future date |

### Clause 1 — Day Care & Hospitalization Cover (Section B-1.1, Page 11)
**Clause ID:** `B.1.1`  
**Section:** SECTION B. BENEFITS > 1. Base Coverage > 1.1 Hospitalization Expenses  
**Page:** 11  

**Verbatim Text:**
> "The Company shall indemnify Medical Expenses necessarily incurred by the Insured Person for Hospitalization of the Insured Person during the Policy Year due to Illness or Injury, up to the Sum Insured specified in the Policy Schedule..."
>
> "iv. All Day Care Treatments."
>
> Note: "However, the time limit shall not apply in respect of Day Care Treatment."

**Relevance:** Establishes that cataract (phacoemulsification) is covered as a Day Care Treatment under the base hospitalisation benefit — the "cover clause".

---

### Clause 2 — Specified Disease / Procedure Waiting Period (Section C.1.b, Page 31)
**Clause ID:** `C.1.b`  
**Section:** SECTION C. WAITING PERIOD AND EXCLUSIONS > 1. Waiting Periods > b. Specified Disease/Procedure waiting period  
**Code:** Excl02  
**Page:** 31  

**Verbatim Text:**
> "Specified Disease/Procedure waiting period: Code – Excl02
> i. Expenses related to the treatment of the listed Conditions, surgeries/treatments shall be excluded until the expiry of **24 months** of continuous coverage after the date of inception of the first Policy with us. This exclusion shall not be applicable for claims arising due to an Accident.
> ii. In case of enhancement of sum insured the exclusion shall apply afresh to the extent of Sum Insured increase.
> iii. If any of the specified disease/procedure falls under the waiting period specified for Pre-Existing diseases, then the longer of the two waiting periods shall apply.
> ...
> vi. List of specific diseases/procedures is provided below:
> ...
> **Cataract and other disorders of lens and Retina**"

**Relevance:** The specific waiting period for cataract is **24 months**. A policy issued 11 months ago has only served 11 months → waiting period **NOT served** → claim is not admissible.

---

### Clause 3 — 30-Day Initial Waiting Period (Section C.1.c, Page 32)
**Clause ID:** `C.1.c`  
**Section:** SECTION C. WAITING PERIOD AND EXCLUSIONS > 1. Waiting Periods > c. 30-day waiting period  
**Code:** Excl03  
**Page:** 32  

**Verbatim Text:**
> "30-day waiting period: Code – Excl03
> i. Expenses related to the treatment of any illness within 30 days from the first Policy commencement date shall be excluded except claims arising due to an accident, provided the same are covered.
> ii. This exclusion shall not, however, apply if the Insured Person has continuous coverage for more than twelve months."

**Relevance:** At 11 months, the 30-day waiting period IS served (>30 days). However the 24-month specific disease waiting period for cataract is NOT served.

---

### Clause 4 — Pre-Existing Disease Waiting Period (Section C.1.a, Page 30)
**Clause ID:** `C.1.a`  
**Section:** SECTION C. WAITING PERIOD AND EXCLUSIONS > 1. Waiting Periods > a. Pre-Existing Diseases  
**Code:** Excl01  
**Page:** 30  

**Verbatim Text:**
> "Pre-Existing Diseases: Code – Excl01
> i. Expenses related to the treatment of a pre-existing disease (PED) and its direct complications shall be excluded until the expiry of **36 months** (Unless specified otherwise in the Policy Schedule) of continuous coverage after the date of inception of the first policy with insurer."

**Relevance:** If cataract was a pre-existing condition, a 36-month waiting period applies (longer than the 24-month specific WP). At 11 months, PED waiting period also NOT served.

---

## Expected Answer (Reference Case)

| Scenario | Expected Route | Expected Position | Required Citations |
|---|---|---|---|
| Policy issued **11 months** ago | `medical-review` | `waiting_period_not_served` (24-month specific WP for cataract not yet complete) | `C.1.b` (cataract-specific WP) + `B.1.1` (cover clause) |
| Policy issued **30 months** ago | `approve-recommended` OR `query-to-hospital` | `waiting_period_served` (24-month WP complete); indicative limit = Sum Insured | `C.1.b` (WP served) + `B.1.1` (cover clause) |

**Variant test:** A policy issued 30 months ago has served the 24-month specific waiting period. The agent should flip the recommendation to `approve-recommended` (if no PED concern) or `query-to-hospital` (if more information needed on room category / estimated cost vs sub-limits).

---

## Important Notes for Verifier Agent
1. The agent MUST retrieve BOTH `C.1.b` (the specific waiting period listing cataract) AND `B.1.1` (the cover clause) in the same run.
2. The agent must NOT assume cataract is covered without explicitly checking Section C waiting periods.
3. If only the cover clause is found and the waiting-period table is not retrieved, the run MUST trigger a re-search using `type="waiting_period"` filter and/or `get_clause("C.1.b")` before returning a result.
4. No sub-limit for cataract appears in the base policy text for Optima Secure (unlike some other products). The indicative limit = Sum Insured (no explicit cataract sub-limit found). Confirm this with the lecturer.

---

> **LECTURER CONFIRMATION REQUIRED** before freezing this as the reference answer.  
> Please verify:  
> 1. The 24-month waiting period for cataract in your policy version.  
> 2. Whether any sub-limit applies to cataract (none found in base policy text).  
> 3. The admission type — we've set `day_care` per the "All Day Care Treatments" clause.
