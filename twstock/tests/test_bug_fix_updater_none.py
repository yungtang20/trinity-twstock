import os

def test_updater_handles_none_date():
    fpath = os.path.join(os.path.dirname(__file__), '..', 'official', 'updater.py')
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    # 不應有 bare None < str 的模式
    assert 'last_tdcc_date is None or last_tdcc_date <' not in content, \
        "應使用 not last_tdcc_date 或 str() 明確處理"
