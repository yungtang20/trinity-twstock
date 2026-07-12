# CURRENT TASK

Directive Task ID: TASK-0012 (Final)
State Task ID: TASK-0010 . TASK-0011 . TASK-0012
Match: YES

State: DONE
CurrentStage: COMPLETE

Change Budget:
Files: 3 / 3 (twstock/market_data/cache.py, twstock/tui/render.py)
Lines: ~52 / 45

Snapshot Baseline:
Commit: d16da7b

Deployment Commit: d7842e4

Completed Tasks (all deployed in  commits 4478836 → d7842e4):
  ✅ TASK-0010  Header 時間改採系統時鐘 datetime.now(),不再取 API 的 indices["date"](可以避免週末/雨天狂假仍显舊日期)
  ✅ TASK-0011  市場行情标题列显現 API 資料時間(ROC 民國年),格式例如 「📊 市場:  115/07/09 13:30:00」
  ✅ TASK-0012  市場模式(盤中/盤後)取消時間硬式範圍判底,改取 6 個市場欄位的變化來判断(TAIEX/OTC price, amount, l_up；任一變動即区盤中,全部相同或首次啟動则区盤後)

Blocker: None
