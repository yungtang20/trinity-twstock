from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backfill_indicators.py"


def test_no_hardcoded_windows_path():
    content = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "D:\\twse" not in content
    assert "D:/twse" not in content


def test_no_undefined_elapsed1():
    lines = SCRIPT_PATH.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if "total_elapsed" in line and "elapsed1" in line:
            defined = any("elapsed1 =" in src_line for src_line in lines[:i])
            assert defined, f"第 {i+1} 行使用 elapsed1 但未定義"


def test_backfill_uses_get_connection():
    content = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "get_connection" in content
    assert "sqlite3.connect(" not in content
