"""Headless browser check using an isolated local SQLite database."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from playwright.sync_api import sync_playwright
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
with TemporaryDirectory(prefix='.test-tmp-web-', dir=root) as directory:
    app = create_app('sqlite:///' + str(Path(directory) / 'web.db'), 'browser-test-key')
    with app.test_client() as client:
        client.post('/reset', headers={'X-API-Key':'browser-test-key'}, json={'slots':[
            dict(id='web-1',provider='Dr Ade',start='2099-12-10T09:00:00Z',end='2099-12-10T09:30:00Z'),
            dict(id='web-2',provider='Dr Obi',start='2099-12-10T10:00:00Z',end='2099-12-10T10:30:00Z'),
        ]})
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1100})
            def route_request(route):
                req = route.request
                parsed = urlsplit(req.url)
                with app.test_client() as client:
                    response = client.open(parsed.path + ('?' + parsed.query if parsed.query else ''), method=req.method, headers=req.headers, data=req.post_data)
                    route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.data)
            page.route('https://clinic.test/**', route_request)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto('https://clinic.test/')
            page.locator('#api-key').fill('browser-test-key')
            page.locator('#connect button').click()
            page.locator('.slot').first.wait_for()
            assert page.locator('.slot').count() == 2
            page.locator('.slot').first.click()
            page.locator('#name').fill('Ada Obi')
            page.locator('#email').fill('ada@example.com')
            page.locator('#book').click()
            page.get_by_text('You’re booked.').wait_for()
            page.locator('#find').click()
            page.locator('#history-results .badge').wait_for()
            assert page.locator('#history-results .badge').inner_text() == 'confirmed'
            page.on('dialog', lambda dialog: dialog.accept())
            page.locator('#history-results button').click()
            page.wait_for_function("document.querySelector('#history-results .badge').textContent === 'cancelled'")
            page.locator('#refresh').click()
            page.wait_for_function("document.querySelectorAll('.slot').length === 2")
            (root / 'artifacts').mkdir(exist_ok=True)
            page.screenshot(path=str(root/'artifacts'/'desktop.png'), full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(root/'artifacts'/'mobile.png'), full_page=True)
            assert not errors, errors
            browser.close()
            print('PASS: connect, choose slot, book, confirmation, history, cancellation, slot release, mobile width; no JavaScript errors')
    finally:
        app.extensions['db_engine'].dispose()
