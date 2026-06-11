#!/usr/bin/env python3
from __future__ import annotations

import dossier_download


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeSearchPage:
    def __init__(self) -> None:
        self.scripts: list[str] = []
        self.clicked_selectors: list[str] = []
        self.url = "https://globaldossier.uspto.gov/home"

    def evaluate(self, script: str, arg=None):
        self.scripts.append(script)
        if "document.getElementById('country')" in script and "options.length" in script:
            return True
        if "document.getElementById('office')" in script and "options.length" in script:
            return False
        return None

    def reload(self, **kwargs) -> None:
        return None

    def click(self, selector: str, timeout: int = 0) -> None:
        self.clicked_selectors.append(selector)
        self.url = "https://globaldossier.uspto.gov/result/publication/CN/116621800/1"


def run_current_search_form_selector_case() -> None:
    original_sleep = dossier_download.time.sleep
    dossier_download.time.sleep = lambda _seconds: None
    try:
        page = FakeSearchPage()
        assert_true(dossier_download.wait_angular(page) is True, "wait_angular should accept current #country select")

        page = FakeSearchPage()
        assert_true(dossier_download.angular_search(page, 1, 1, "116621800") is True, "angular_search should submit current form")
        assert_true(
            any("document.getElementById('country')" in script for script in page.scripts),
            "angular_search should set #country rather than removed #office",
        )
        assert_true(
            page.clicked_selectors == ["button[name='search']"],
            "angular_search should click the stable search button name",
        )
    finally:
        dossier_download.time.sleep = original_sleep


def main() -> None:
    run_current_search_form_selector_case()
    print("global-dossier regression checks passed")


if __name__ == "__main__":
    main()
