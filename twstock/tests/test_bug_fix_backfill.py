def test_no_hardcoded_windows_path():
    import os

    fpath = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "backfill_indicators.py")
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    assert "D:\\twse" not in content
    assert "D:/twse" not in content


def test_no_undefined_elapsed1():
    import os

    fpath = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "backfill_indicators.py")
    with open(fpath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "total_elapsed" in line and "elapsed1" in line:
            defined = any("elapsed1 =" in src_line for src_line in lines[:i])
            assert defined, f"第 {i+1} 行使用 elapsed1 但未定義"


def test_backfill_uses_get_connection():
    import os

    fpath = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "backfill_indicators.py")
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    assert "get_connection" in content
    assert "sqlite3.connect(" not in content
