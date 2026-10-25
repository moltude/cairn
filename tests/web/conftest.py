"""Fixtures for the web e2e tests, shared by every file in tests/web (moved out
of test_web_app.py on 2026-10-25). A file here that needs the dev server skips
cleanly without it, exactly as test_web_app.py always did."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect, sync_playwright

from tests.web.helpers import (  # noqa: F401  (re-exported for the fixtures below)
    BASE_URL, FIXTURE, _EXPLICIT_BASE_URL, _server_reachable,
)

@pytest.fixture(scope="session", autouse=True)
def _require_server():
    """Skip if the local dev server isn't up; fail if an explicit BASE_URL is unreachable.

    A skip is the right call for "you forgot to start the dev server" -- but
    if BASE_URL was set on purpose (pointing at a deployment), an unreachable
    URL must fail the run. Otherwise a mistyped or down URL reports a clean
    green skip, which is worse than no test at all.
    """
    if not _server_reachable():
        if _EXPLICIT_BASE_URL:
            pytest.fail(f"explicit BASE_URL={BASE_URL} is not reachable")
        pytest.skip(
            f"web dev server not reachable at {BASE_URL} "
            "(start it with: uv run python web/serve.py)"
        )


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture(scope="session")
def context(browser):
    """A single browser context, reused across tests so the CDN-fetched
    Pyodide/wheel assets stay in the HTTP cache: the first test pays a cold
    boot, every later test's boot is warm (see perf numbers in the report).
    """
    # bypass_csp: the page now ships a strict Content-Security-Policy (see
    # web/vercel.json, mirrored by serve.py) with no 'unsafe-eval'; Playwright's
    # string-evaluating helpers (wait_for_function etc.) are eval-based and
    # would be blocked by it. The CSP itself is verified by
    # test_page_boots_under_enforced_csp, which uses a non-bypassing context.
    ctx = browser.new_context(bypass_csp=True)
    yield ctx
    ctx.close()


@pytest.fixture()
def fresh_page(context) -> Page:
    """A brand-new page/tab, booted but with nothing loaded yet.

    Each test gets its own page (not a shared one reloaded with the same
    file) because Chromium/Playwright does not fire a `change` event on
    `<input type=file>` when `set_input_files` is called twice with the
    identical path -- confirmed by direct repro. A fresh page sidesteps that
    entirely and is also the more realistic "user opens the app" scenario.
    """
    page = context.new_page()
    page.goto(f"{BASE_URL}/index.html")
    page.wait_for_function("window.__cairnReady === true", timeout=60000)
    yield page
    page.close()


@pytest.fixture()
def loaded(fresh_page: Page) -> Page:
    """fresh_page with the real fixture loaded (no edits, no selection)."""
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    return fresh_page


@pytest.fixture()
def csp_page(browser):
    """A booted page in a context that enforces the production CSP."""
    ctx = browser.new_context(accept_downloads=True)  # deliberately no bypass_csp
    page = ctx.new_page()
    violations = []
    page.on("console", lambda m: violations.append(m.text)
            if "Content Security Policy" in m.text else None)
    page.goto(f"{BASE_URL}/index.html")
    # Not wait_for_function: under the enforced CSP Playwright cannot evaluate
    # page JS (no 'unsafe-eval'), so readiness is read from the DOM.
    expect(page.locator("body")).to_have_attribute("data-engine", "ready", timeout=60000)
    yield page
    ctx.close()
    assert not violations, f"CSP violations: {violations}"

