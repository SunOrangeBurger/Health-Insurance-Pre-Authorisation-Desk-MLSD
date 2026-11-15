"""Reviewer UI acceptance against the synthetic cases from verify_precedent_flow.py."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    evidence = json.loads(Path('docs/evidence/precedent-flow.json').read_text())
    auto_case = evidence['cases'][1]['case_id']
    source_case = evidence['cases'][4]['case_id']
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://localhost:8000')
        page.get_by_label('Work email').fill('reviewer@desk.local')
        page.get_by_label('Password', exact=True).fill(os.environ['DESK_REVIEWER_PASSWORD'])
        page.get_by_role('button', name='Sign in', exact=True).click()
        expect(page.locator('#workspace')).to_be_visible()
        csrf = context.request.get('http://localhost:8000/v1/auth/me').json()['csrf_token']
        response = context.request.post('http://localhost:8000/v1/cases/'+source_case+'/decision',
            headers={'X-CSRF-Token': csrf}, data={'revision': 1, 'outcome': 'approved', 'reusable': True,
            'reason': 'Synthetic reviewer UI acceptance: enable bounded reuse.'})
        assert response.ok, response.text()
        rows = context.request.get('http://localhost:8000/v1/precedents').json()['items']
        precedent = next(p for p in rows if p['case_id'] == source_case)
        page.get_by_role('button', name='Reusable decisions').click()
        card = page.locator('[data-precedent-id="'+precedent['id']+'"]')
        expect(card).to_contain_text('Active')
        card.get_by_role('button', name='Disable for future cases').click()
        expect(page.locator('[data-precedent-id="'+precedent['id']+'"] .badge')).to_have_text('Disabled')
        page.screenshot(path='docs/evidence/precedent-management.png', full_page=True)
        page.get_by_role('button', name='Back to cases').click()
        target = page.locator('[data-case-id="'+auto_case+'"]')
        for _ in range(5):
            if target.count():
                break
            page.get_by_role('button', name='Load more', exact=True).click()
        target.get_by_role('button', name='Open case').click()
        expect(page.locator('#review')).to_contain_text('Override automatic decision')
        page.locator('[name="outcome"]').select_option('rejected')
        page.locator('[name="reason"]').fill('Synthetic UI override: individual circumstance requires a different outcome.')
        page.get_by_role('button', name='Record decision').click()
        expect(page.locator('#case-detail .badge')).to_have_text('rejected')
        expect(page.locator('#case-detail')).to_contain_text('human decision')
        page.screenshot(path='docs/evidence/precedent-override.png', full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        assert not errors, errors
        Path('docs/evidence/precedent-browser.json').write_text(json.dumps({'passed': True,
            'checks': ['Reviewer inspects and disables reusable decision', 'Reviewer overrides automatic decision',
                       'Human outcome and audit history displayed', 'No page errors or mobile overflow'],
            'source_case_id': source_case, 'overridden_case_id': auto_case}, indent=2))
        browser.close()


if __name__ == '__main__':
    main()
