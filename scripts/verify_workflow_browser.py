"""Browser acceptance against a running local app; synthetic seeded accounts only.

Set DESK_HOSPITAL_PASSWORD and DESK_REVIEWER_PASSWORD. Run after seeding accounts
and starting API/worker. A missing index is allowed for this workflow checkpoint:
it must reach review honestly; grounded AI quality is a separate checkpoint.
"""
import json
import os
from datetime import date, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://localhost:8000")

        def login(email, password):
            page.get_by_label("Work email").fill(email)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#workspace")).to_be_visible()

        def logout():
            page.get_by_role("button", name="Sign out").click()
            expect(page.locator("#login")).to_be_visible()

        def open_case(case_id):
            # Refresh list through the UI, then open the exact visible case by its
            # unique synthetic procedure description.
            page.get_by_role("button", name="Refresh", exact=True).click()
            page.locator(".card").filter(has_text=case_id).get_by_role("button", name="Open case").click()

        hospital_password = os.environ["DESK_HOSPITAL_PASSWORD"]
        reviewer_password = os.environ["DESK_REVIEWER_PASSWORD"]
        login("hospital@desk.local", hospital_password)
        page.get_by_role("button", name="New request").click()
        marker = "Synthetic browser cataract " + str(int(__import__('time').time()))
        issue = (date.today() - timedelta(days=900)).isoformat()
        fields = {"policy_number": "SYN-POL-0001", "policy_issue_date": issue,
                  "policy_start_date": issue, "sum_insured": "500000", "patient_age": "44",
                  "planned_admission_date": (date.today()+timedelta(days=7)).isoformat(),
                  "diagnosis_text": "Synthetic cataract diagnosis", "procedure_text": marker,
                  "procedure_code": "SYN-001", "estimated_cost": "75000"}
        for key, value in fields.items():
            page.locator(f'[name="{key}"]').fill(value)
        page.locator('[name="admission_type"]').select_option("day_care")
        page.get_by_role("button", name="Submit for assessment").click()
        expect(page.locator("#detail")).to_be_visible()
        expect(page.locator("#case-detail .badge")).to_have_text("awaiting review", timeout=120000)
        results.append("Hospital form submission and asynchronous review-ready status")
        logout()
        login("reviewer@desk.local", reviewer_password)
        open_case(marker)
        expect(page.locator("#review")).to_be_visible()
        page.locator('[name="outcome"]').select_option("information_requested")
        page.locator('[name="reason"]').fill("Please clarify the synthetic procedure details.")
        page.get_by_role("button", name="Record decision").click()
        expect(page.locator("#case-detail .badge")).to_have_text("information requested")
        logout()
        login("hospital@desk.local", hospital_password)
        open_case(marker)
        page.get_by_role("button", name="Respond and resubmit").click()
        page.locator('[name="notes"]').fill("Clarification: synthetic phacoemulsification with IOL.")
        page.get_by_role("button", name="Submit for assessment").click()
        expect(page.locator("#case-detail .badge")).to_have_text("awaiting review", timeout=120000)
        expect(page.locator("#case-detail")).to_contain_text("REVISION 2")
        results.append("Reviewer clarification and hospital revision/resubmission")
        logout()
        login("reviewer@desk.local", reviewer_password)
        open_case(marker)
        page.locator('[name="outcome"]').select_option("approved")
        page.locator('[name="reason"]').fill("Synthetic workflow acceptance only; human-reviewed one-off approval.")
        page.get_by_role("button", name="Record decision").click()
        expect(page.locator("#case-detail .badge")).to_have_text("approved")
        logout()
        login("hospital@desk.local", hospital_password)
        open_case(marker)
        expect(page.locator("#case-detail")).to_contain_text("human decision")
        expect(page.locator("#revise")).to_be_hidden()
        output = Path("docs/evidence")
        output.mkdir(exist_ok=True)
        page.screenshot(path=str(output / "hospital-case.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path=str(output / "hospital-case-mobile.png"), full_page=True)
        results.append("Final human approval visible to hospital; mobile layout has no horizontal overflow")
        assert not errors, errors
        (output / "workflow-browser.json").write_text(json.dumps({"passed": True, "checks": results,
            "page_errors": errors, "limitation": "Human workflow only; no AI-quality or performance claim."}, indent=2))
        browser.close()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
