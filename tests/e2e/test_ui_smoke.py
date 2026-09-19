from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

pytestmark = pytest.mark.browser

RUN_BROWSER_TESTS = os.environ.get("RUN_BROWSER_TESTS") == "1"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def server_url() -> str:
    if not RUN_BROWSER_TESTS:
        pytest.skip("Set RUN_BROWSER_TESTS=1 to run browser tests")

    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tests.e2e.fake_server",
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    url = f"http://127.0.0.1:{port}"
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
        raise RuntimeError(
            f"Server failed to start.\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}"
        )

    yield url

    proc.terminate()
    proc.wait(timeout=5)


@pytest.mark.skipif(not RUN_BROWSER_TESTS, reason="Set RUN_BROWSER_TESTS=1 to run browser tests")
def test_two_turn_conversation_and_provenance(server_url: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(server_url)

        page.fill("#passphrase", "test-passphrase")
        page.click("#login-form button[type='submit']")
        page.wait_for_selector("#chat-view:not(.hidden)")

        page.fill("#message-input", "What is the population of Texas?")
        page.click("#send-button")
        page.wait_for_selector(".message.assistant", timeout=30000)

        page.fill("#message-input", "and in Florida?")
        page.click("#send-button")
        page.locator(".message.assistant").nth(1).wait_for(timeout=30000)

        assistant_messages = page.locator(".message.assistant")
        assert assistant_messages.count() == 2

        second_text = assistant_messages.nth(1).locator(".message-text").inner_text()
        assert "Florida" in second_text

        page.locator(".message.assistant").first.locator("details summary").click()
        page.wait_for_selector(".provenance-sql", timeout=5000)
        sql_text = page.locator(".provenance-sql").first.inner_text()
        assert sql_text

        browser.close()
