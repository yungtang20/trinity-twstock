# -*- coding: utf-8 -*-
"""
test_docs_contract.py — 文件規格契約測試

驗證 DB_SCHEMA.md 與 ARCHITECTURE.md 的關鍵規格一致，
避免文件間互相矛盾導致規格漂移。
"""

from __future__ import annotations

from pathlib import Path

# ── DB_SCHEMA.md 規格測試 ──


def test_db_schema_declares_volume_in_shares():
    """DB_SCHEMA.md 應宣告 volume 存股（非張）。"""
    content = Path("twstock/DB_SCHEMA.md").read_text(encoding="utf-8")
    assert "volume" in content
    # 明確標註「股，非張」
    assert "股" in content
    assert "非張" in content or "（股）" in content


def test_db_schema_declares_amount_in_yuan():
    """DB_SCHEMA.md 應宣告 amount 存元（非千萬元）。"""
    content = Path("twstock/DB_SCHEMA.md").read_text(encoding="utf-8")
    assert "amount" in content
    assert "元" in content


def test_db_schema_no_adj_close_in_stock_history():
    """DB_SCHEMA.md 不應再提及 adj_close（前復權功能已完全移除）。"""
    content = Path("twstock/DB_SCHEMA.md").read_text(encoding="utf-8")
    assert "adj_close" not in content, "DB_SCHEMA.md 不應再提及 adj_close（功能已移除）"
    assert "adj_factor" not in content, "DB_SCHEMA.md 不應再提及 adj_factor（功能已移除）"


def test_db_schema_tdcc_shareholding_is_view():
    """DB_SCHEMA.md 應標註 tdcc_shareholding 是 VIEW。"""
    content = Path("twstock/DB_SCHEMA.md").read_text(encoding="utf-8")
    assert "tdcc_shareholding" in content
    assert "VIEW" in content


def test_db_schema_declares_views():
    """DB_SCHEMA.md 應列出所有 VIEW（klines, klines_indicators, institutional_daily）。"""
    content = Path("twstock/DB_SCHEMA.md").read_text(encoding="utf-8")
    assert "klines" in content
    assert "klines_indicators" in content
    assert "institutional_daily" in content


# ── ARCHITECTURE.md 規格測試 ──


def test_architecture_does_not_claim_db_stores_lots():
    """ARCHITECTURE.md 不應宣稱 DB 存張（與 DB_SCHEMA.md 衝突）。"""
    content = Path("twstock/ARCHITECTURE.md").read_text(encoding="utf-8")
    forbidden_phrases = [
        "DB 內所有量值一律為張",
        "成交量以張為單位存入資料庫",
        "amount 存千萬元",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in content, (
            f"ARCHITECTURE.md 有過時規格: '{phrase}'。" f"DB 存股/元，顯示層才轉換。"
        )


def test_architecture_does_not_list_shareholding_data():
    """ARCHITECTURE.md 不應列出 shareholding_data 表（已淘汰）。"""
    content = Path("twstock/ARCHITECTURE.md").read_text(encoding="utf-8")
    # shareholding_data 已被 shareholding_unified 取代
    assert "shareholding_data" not in content, "ARCHITECTURE.md 仍列出已淘汰的 shareholding_data 表"


def test_architecture_tdcc_shareholding_is_view():
    """ARCHITECTURE.md 應標註 tdcc_shareholding 是 VIEW（非 TABLE）。"""
    content = Path("twstock/ARCHITECTURE.md").read_text(encoding="utf-8")
    # 找到 tdcc_shareholding 段落，確認標記為 VIEW
    if "tdcc_shareholding" in content:
        # 檢查是否標記為 VIEW
        assert (
            "VIEW" in content.split("tdcc_shareholding")[1][:500]
        ), "ARCHITECTURE.md 中 tdcc_shareholding 應標記為 VIEW"


def test_architecture_adj_close_is_derived():
    """ARCHITECTURE.md 應說明 adj_close 是派生值（非 stock_history 欄位）。"""
    content = Path("twstock/ARCHITECTURE.md").read_text(encoding="utf-8")
    # 不應在 stock_history 欄位清單中出現 adj_close
    # 找到 stock_history 表格段落
    if "stock_history" in content:
        # 檢查是否有 adj_close 在 stock_history 的欄位描述中
        lines = content.splitlines()
        in_stock_history = False
        stock_history_block = []
        for line in lines:
            if "stock_history" in line and "|" not in line:
                in_stock_history = True
            if in_stock_history:
                stock_history_block.append(line)
                if "索引" in line or "PRIMARY KEY" in line:
                    break
        block = "\n".join(stock_history_block)
        assert (
            "adj_close" not in block
        ), "ARCHITECTURE.md 的 stock_history 表格不應有 adj_close 欄位"
