# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: real-data.spec.ts >> Dashboard sections 至少一個有數據或正確空狀態
- Location: tests\real-data.spec.ts:51:1

# Error details

```
Error: 至少一個 dashboard section 應該有數據

expect(received).toBeGreaterThan(expected)

Expected: > 0
Received:   0
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - complementary [ref=e4]:
    - heading "TRINITY" [level=1] [ref=e6] [cursor=pointer]
    - navigation [ref=e7]:
      - button "儀表板" [ref=e8]:
        - img [ref=e9]
        - text: 儀表板
      - button "市場分析" [ref=e14]:
        - img [ref=e15]
        - text: 市場分析
      - button "策略模組" [ref=e18]:
        - img [ref=e19]
        - text: 策略模組
      - button "AI 深度分析" [ref=e21]:
        - img [ref=e22]
        - text: AI 深度分析
      - paragraph [ref=e26]: 系統
      - button "設定" [ref=e27]:
        - img [ref=e28]
        - text: 設定
    - generic [ref=e31]: v1.0.0-beta
  - generic [ref=e32]:
    - banner [ref=e33]:
      - generic [ref=e34]:
        - generic [ref=e35]:
          - img [ref=e36]
          - textbox "搜尋股票代號或名稱..." [ref=e39]
        - button [ref=e40]:
          - img [ref=e41]
        - generic [ref=e45]: A
    - main [ref=e46]:
      - generic [ref=e48]:
        - generic [ref=e49]:
          - generic [ref=e50]:
            - generic [ref=e51]:
              - img [ref=e52]
              - text: 2026-06-26 (五) 21:23:00
            - generic [ref=e55]: 收盤
            - generic [ref=e57]: "基準日: 2026-06-26"
          - generic [ref=e58]:
            - img [ref=e59]
            - generic [ref=e62]: SQLite 正常
        - generic [ref=e63]:
          - generic [ref=e64]:
            - generic [ref=e65]: 加權指數 44,571.76
            - generic [ref=e66]: +1683.50 (-3.64%)
            - generic [ref=e67]:
              - generic [ref=e68]: ↑75
              - generic [ref=e69]: 平20
              - generic [ref=e70]: ↓969
              - generic [ref=e71]: 停7
              - generic [ref=e72]: 停18
          - generic [ref=e73]:
            - generic [ref=e74]: 櫃買指數 415.26
            - generic [ref=e75]: "-24.58 (-5.59%)"
            - generic [ref=e76]:
              - generic [ref=e77]: ↑159
              - generic [ref=e78]: 平69
              - generic [ref=e79]: ↓750
              - generic [ref=e80]: 停11
              - generic [ref=e81]: 停22
        - generic [ref=e82]:
          - generic [ref=e83]:
            - generic [ref=e84] [cursor=pointer]:
              - generic [ref=e85]:
                - generic [ref=e86]: 💰
                - generic [ref=e87]: 接下來一週發放股利
                - generic [ref=e88]: (0 檔)
              - img [ref=e90]
            - generic [ref=e93]: 暫無資料
          - generic [ref=e94]:
            - generic [ref=e95] [cursor=pointer]:
              - generic [ref=e96]:
                - generic [ref=e97]: 📈
                - generic [ref=e98]: 投信連買二日
                - generic [ref=e99]: (0 檔)
              - img [ref=e101]
            - generic [ref=e104]: 暫無資料
          - generic [ref=e105]:
            - generic [ref=e106] [cursor=pointer]:
              - generic [ref=e107]:
                - generic [ref=e108]: 🚀
                - generic [ref=e109]: 突破 MA200
                - generic [ref=e110]: (0 檔)
              - img [ref=e112]
            - generic [ref=e115]: 暫無資料
          - generic [ref=e116]:
            - generic [ref=e117] [cursor=pointer]:
              - generic [ref=e118]:
                - generic [ref=e119]: 🔴
                - generic [ref=e120]: 昨日漲跌停
                - generic [ref=e121]: (0 檔)
              - img [ref=e123]
            - generic [ref=e126]: 暫無資料
```

# Test source

```ts
  1   | import { test, expect, type Page, type Response } from '@playwright/test';
  2   | 
  3   | // ── 收集所有 API 回應 ───────────────────────────────────────
  4   | 
  5   | async function collectApiResponses(page: Page) {
  6   |   const responses: { url: string; status: number; body: any }[] = [];
  7   |   page.on('response', async (response: Response) => {
  8   |     const url = response.url();
  9   |     if (url.includes('/api/')) {
  10  |       try {
  11  |         const body = await response.json();
  12  |         responses.push({ url, status: response.status(), body });
  13  |       } catch { /* non-JSON */ }
  14  |     }
  15  |   });
  16  |   return responses;
  17  | }
  18  | 
  19  | // ── 測試 1: 首頁應顯示 Dashboard ─────────────────────────────
  20  | 
  21  | test('首頁應顯示 Dashboard 或載入中狀態', async ({ page }) => {
  22  |   await page.goto('/');
  23  |   const mainContent = page.locator('[data-testid="main-content"]');
  24  |   await expect(mainContent).toBeVisible({ timeout: 15000 });
  25  |   const dashboard = page.locator('[data-testid="dashboard-view"]');
  26  |   await expect(dashboard).toBeVisible({ timeout: 15000 });
  27  | });
  28  | 
  29  | // ── 測試 2: 指數 API 應返回真實數據 ─────────────────────────
  30  | 
  31  | test('指數 API 應返回真實數據', async ({ page }) => {
  32  |   const responses = await collectApiResponses(page);
  33  |   await page.goto('/');
  34  |   await page.waitForTimeout(5000);
  35  | 
  36  |   const apiMap = new Map(responses.map(r => [r.url.split('/').pop()!, r.body]));
  37  | 
  38  |   const twse = apiMap.get('twse-stats');
  39  |   expect(twse).toBeDefined();
  40  |   expect(twse!.success).toBe(true);
  41  |   expect(twse!.index).toBeGreaterThan(0);
  42  | 
  43  |   const otc = apiMap.get('otc-stats');
  44  |   expect(otc).toBeDefined();
  45  |   expect(otc!.success).toBe(true);
  46  |   expect(otc!.index).toBeGreaterThan(0);
  47  | });
  48  | 
  49  | // ── 測試 3: Dashboard sections 不能全部為空 ──────────────────
  50  | 
  51  | test('Dashboard sections 至少一個有數據或正確空狀態', async ({ page }) => {
  52  |   const responses = await collectApiResponses(page);
  53  |   await page.goto('/');
  54  |   await page.waitForTimeout(5000);
  55  | 
  56  |   const apiMap = new Map(responses.map(r => [r.url.split('/').pop()!, r.body]));
  57  | 
  58  |   // 檢查 4 個 dashboard sections
  59  |   const sections = [
  60  |     { name: 'recent-dividend', api: apiMap.get('recent-dividend') },
  61  |     { name: 'trust-buy-2day', api: apiMap.get('trust-buy-2day') },
  62  |     { name: 'break-ma200', api: apiMap.get('break-ma200') },
  63  |     { name: 'limit-up-yesterday', api: apiMap.get('limit-up-yesterday') },
  64  |   ];
  65  | 
  66  |   // 計算有數據的 section 數量
  67  |   const withData = sections.filter(s => s.api?.data?.length > 0).length;
  68  |   const empty = sections.filter(s => s.api?.data?.length === 0).length;
  69  | 
  70  |   console.log(`Dashboard sections: ${withData} with data, ${empty} empty`);
  71  | 
  72  |   // 至少要有一個 section 有數據，不然代表 DB 有問題
> 73  |   expect(withData, '至少一個 dashboard section 應該有數據').toBeGreaterThan(0);
      |                                                    ^ Error: 至少一個 dashboard section 應該有數據
  74  | });
  75  | 
  76  | // ── 測試 4: 畫面應顯示真實數字 ─────────────────────────────
  77  | 
  78  | test('畫面應顯示真實指數數字', async ({ page }) => {
  79  |   await page.goto('/');
  80  |   await page.waitForTimeout(3000);
  81  | 
  82  |   const body = page.locator('body');
  83  |   const text = await body.textContent();
  84  |   expect(text).toBeTruthy();
  85  | 
  86  |   const hasRealIndex = text!.match(/[\d,]{2,}\.\d{2}/) !== null;
  87  |   expect(hasRealIndex, '應顯示真實指數數字').toBe(true);
  88  | 
  89  |   const hasDate = text!.match(/\d{4}-\d{2}-\d{2}/) !== null;
  90  |   expect(hasDate, '應顯示日期').toBe(true);
  91  | });
  92  | 
  93  | // ── 測試 5: 假資料檢測 ─────────────────────────────────────
  94  | 
  95  | test('頁面不應出現假資料關鍵字', async ({ page }) => {
  96  |   await page.goto('/');
  97  |   await page.waitForTimeout(3000);
  98  | 
  99  |   const forbiddenTexts = ['Mock', '假資料', 'Lorem', 'Test Data', 'mock', 'lorem'];
  100 |   for (const text of forbiddenTexts) {
  101 |     await expect(page.locator(`text=${text}`)).toHaveCount(0);
  102 |   }
  103 | });
  104 | 
  105 | // ── 測試 6: API 錯誤時應顯示錯誤提示 ─────────────────────────
  106 | 
  107 | test('API 錯誤時應顯示錯誤提示與重試按鈕', async ({ page }) => {
  108 |   await page.route('**/api/dashboard/**', route => route.fulfill({
  109 |     status: 500,
  110 |     body: JSON.stringify({ error: 'Internal Server Error' })
  111 |   }));
  112 | 
  113 |   await page.goto('/');
  114 |   const errorDisplay = page.locator('[data-testid="error-display"]');
  115 |   await expect(errorDisplay.first()).toBeVisible({ timeout: 15000 });
  116 |   const retryButton = errorDisplay.first().locator('button');
  117 |   await expect(retryButton.first()).toBeVisible();
  118 | });
  119 | 
  120 | // ── 測試 7: 頁面應有實際內容 ─────────────────────────────────
  121 | 
  122 | test('頁面應有實際內容，不能全空', async ({ page }) => {
  123 |   await page.goto('/');
  124 |   await page.waitForTimeout(3000);
  125 | 
  126 |   const body = page.locator('body');
  127 |   const text = await body.textContent();
  128 |   expect(text?.trim().length).toBeGreaterThan(100);
  129 | 
  130 |   const indexCard = page.locator('[data-testid="index-card"]');
  131 |   await expect(indexCard.first()).toBeVisible({ timeout: 10000 });
  132 | 
  133 |   const indexText = await indexCard.first().textContent();
  134 |   expect(indexText).toMatch(/\d/);
  135 | });
  136 | 
```