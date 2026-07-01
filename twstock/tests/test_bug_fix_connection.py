"""Bug Fix: main.py 不應直接使用 sqlite3.connect()，應使用 get_connection()"""
import os

def test_main_py_no_bare_sqlite3_connect():
    """main.py 不應直接使用 sqlite3.connect()"""
    main_path = os.path.join(os.path.dirname(__file__), '..', 'main.py')
    with open(main_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        if 'sqlite3.connect(' in stripped and 'def ' not in stripped:
            violations.append(f"  第 {i} 行: {stripped}")
    assert not violations, \
        "main.py 不應直接使用 sqlite3.connect()，應使用 get_connection()：\n" + "\n".join(violations)
