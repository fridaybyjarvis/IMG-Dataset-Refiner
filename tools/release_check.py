"""Small release smoke checks for IMG Dataset Refiner.

Run from the repository root:
    python tools/release_check.py
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import py_compile
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "lora_manager.py"
LANG_DIR = ROOT / "languages"


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"[OK] {message}")


def load_json(path: pathlib.Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        fail(f"{path.name} is not valid JSON: {exc}")


def import_app_module():
    spec = importlib.util.spec_from_file_location("lora_manager_release_check", APP_FILE)
    if spec is None or spec.loader is None:
        fail("Could not create import spec for lora_manager.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    py_compile.compile(str(APP_FILE), doraise=True)
    ok("lora_manager.py compiles")

    fr = load_json(LANG_DIR / "fr.json")
    en = load_json(LANG_DIR / "en.json")
    ok("FR/EN language files parse")

    for section in ("MSG", "UI_T"):
        fr_keys = set(fr.get(section, {}))
        en_keys = set(en.get(section, {}))
        missing_en = sorted(fr_keys - en_keys)
        missing_fr = sorted(en_keys - fr_keys)
        if missing_en or missing_fr:
            fail(
                f"{section} keys differ. Missing EN: {missing_en[:10]} "
                f"Missing FR: {missing_fr[:10]}"
            )
    ok("FR/EN language keys are symmetric")

    app = import_app_module()
    ok(f"module imports ({getattr(app, 'APP_VERSION', 'unknown version')})")

    updates = app.change_language(
        "EN",
        app.pd.DataFrame(),
        app.pd.DataFrame(),
        [],
        "Classic Filter",
    )
    if len(updates) < 170:
        fail(f"change_language returned only {len(updates)} updates")
    ok(f"change_language returns {len(updates)} updates")

    if not getattr(app, "HAS_TIKTOKEN", False):
        ok("tiktoken not installed: fallback token counter will be used")

    print("\nRelease smoke check passed.")


if __name__ == "__main__":
    main()
