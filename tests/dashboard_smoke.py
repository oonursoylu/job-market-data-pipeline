"""Open the Streamlit dashboard headlessly and fail on any exception or error message.

Run from the repository root after dbt build:  python -m tests.dashboard_smoke
"""
import faulthandler
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


def problems(app_test) -> list[str]:
    return [str(item.value) for item in app_test.exception] + [str(item.value) for item in app_test.error]


def main() -> int:
    faulthandler.enable()  # if native code crashes (exit code 139), print where it happened
    sys.path.insert(0, str(APP.parent))  # the app imports queries.py from its own folder
    app_test = AppTest.from_file(str(APP), default_timeout=120).run()
    found = problems(app_test)
    if not found:
        app_test.radio[0].set_value("All observed dates").run()  # the multi-day skill window
        found = problems(app_test)
    for problem in found:
        print(f"Dashboard problem: {problem}")
    print("Dashboard smoke test:", "failed" if found else "passed")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
