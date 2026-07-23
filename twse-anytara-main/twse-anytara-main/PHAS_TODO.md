# Phase TODO

## ✅ 已交付
1. FinMind 9 datasets + MCP backup + LongCat 报告
2. `/api/job/batch` + `/api/job/:id` job queue (切換分頁不中断)
3. `/api/tdcc/sync` + `/api/tdcc/status` + 每六排程
4. `POST /api/settings` 雙写 .env + Supabase `user_settings`
5. `StepFlow` 统壹 5 页共用
6. AI 分析新前端 (5-step + polling)
7. 修正 ai.ts `LongCat-2.0-Preview` → `LongCat-2.0`
8. 封存 12 个临时 scripts 至 `scripts/_archive/`

## 🟡 未完成
1. Supabase `user_settings` table 需要手动建
2. Supabase cleanup fallback (同步/清理策略)
3. FinMind/Supabase 双向同步一致性
4. 重复 LongCat-2.0-Preview 字串仍存在于 scripts/_archive/ 中
5. 确认 AIAnalysisView TSC 编译无错误 (需再跑一次)
6. 完整 vite build + server.ts 启动端到端测试

## 🔥 高优先级下一版本
- 前端 4 页面 (Dashboard, Markets, Strategies, Settings) 接入 `StepFlow` 组件
- Settings page 的 Supabase + .env 测试
- FinMind/Supabase 双向同步桥接
- FinMind Basic 付费昇级 (NT$499/月) 测试
