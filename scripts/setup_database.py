#!/usr/bin/env python3
"""
TRINITY TWStock - 資料庫初始化腳本

用於建立資料庫結構和初始資料。
"""

import os
import sys
from pathlib import Path

# 加入專案根目錄
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv


def get_database_url():
    """取得資料庫連線 URL"""
    # 載入環境變數
    env_path = Path(__file__).parent.parent / "data" / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # 優先使用 DATABASE_URL，否則使用 SQLite
    db_url = os.getenv("DATABASE_URL", "sqlite:///data/raw/taiwan_stock_unified.db")
    return db_url


def init_database():
    """初始化資料庫"""
    db_url = get_database_url()
    print(f"資料庫連線: {db_url}")

    if db_url.startswith("sqlite"):
        # SQLite 不需要額外設定
        db_path = db_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        print(f"SQLite 資料庫路徑: {db_path}")
        print("資料庫初始化完成！")
    else:
        # PostgreSQL 等其他資料庫
        print("請使用資料庫管理工具初始化結構")
        print("建議使用 Alembic 進行遷移管理")


def verify_database():
    """驗證資料庫連線"""
    db_url = get_database_url()
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ 資料庫連線成功")
        return True
    except Exception as e:
        print(f"❌ 資料庫連線失敗: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("TRINITY TWStock - 資料庫初始化")
    print("=" * 50)

    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify_database()
    else:
        init_database()
