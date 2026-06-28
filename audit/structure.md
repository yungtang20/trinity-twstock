# TWSE-ANYTARA Directory Structure Map

This document presents a comprehensive lookup map and physical directory scan of the TWSE-ANYTARA workspace to guide internal audit modules and development workflows.

```
/ (Workspace Root)
├── .env.example              # Template for server & client environment variables
├── .gitignore                # Production & container file exclusions
├── README.md                 # Project introduction and execution instructions
├── fetch.cjs                 # Utility script to sync remote sqlite schema.sql
├── index.html                # Frontend primary document entry point
├── metadata.json             # Applet descriptor (capabilities, framework configurations)
├── package-lock.json         # Pinned packages dependency tree
├── package.json              # Applet configurations, build and run scripts
├── schema.sql                # SQL database design documentation for relational db
├── server.ts                 # Full-stack backend Express-Vite engine with SQLite persistence
├── tsconfig.json             # TypeScript compiler settings
└── vite.config.ts            # Vite bundler, React and Tailwind plugins configuration

├── scripts/                  # Data synchronization and setup scripts
│   ├── __init__.py           # Python package marker
│   ├── complete_and_fetch_today.js # Integration sync script for daily market close
│   ├── fetch_today_only.js   # Single-day data fetching automation
│   ├── pull_from_supabase.js # Data pull and backup utility
│   ├── setup_database.py     # Local database builder & index initializer
│   ├── syncData.ts           # Typescript-based database synchronization routine
│   └── sync_to_supabase.py   # Cloud sync coordinator script
│
├── twstock/                  # Python-based financial analytical backtesting engine
│   ├── api_config.py         # Third-party endpoints config (FinMind, Fugle, TWSE)
│   ├── calculator.py         # Advanced technical indicator (MA, RSI, MACD, KD) computer
│   ├── db.py                 # SQLite relational connector
│   ├── db_admin.py           # Database migration and tables administration CLI
│   ├── display.py            # Console output decorator and ASCII UI system
│   ├── fetcher.py            # Async network fetch routines
│   ├── main.py               # TWStock backtester core CLI and analytical entry point
│   ├── polars.py             # Big-data memory-efficient dataframe utility
│   ├── processor.py          # Corporate action and trade-flow processor
│   ├── strategy_runner.py    # Backtester backtesting sandbox coordinator
│   ├── taiwan_stock_unified.db # Main SQLite unified database file
│   ├── official/             # TWSE official crawling and parser modules
│   └── strategy/             # Backtesting strategy rulesets configurations
│
├── src/                      # Frontend architecture (React + Vite + Typescript)
│   ├── App.tsx               # Main component routing and state context provider
│   ├── types.ts              # Global shared typescript interface declarations
│   ├── index.css             # Tailwind stylesheet compilation entry
│   ├── main.tsx              # React mounting file
│   ├── api/                  # Frontend network queries to server.ts proxy
│   │   └── ai.ts             # Gemini-based AI analysis network proxy handler
│   ├── lib/                  # Shared utility code
│   └── components/           # UI elements & custom views
│       ├── BottomNav.tsx     # Adaptive navigation for mobile formats
│       ├── Header.tsx        # Top status bar and branding element
│       ├── Sidebar.tsx       # Navigation drawer designed for desktop layout
│       ├── Layout.tsx        # Main outer visual scaffolding container
│       ├── StatCard.tsx      # Recurrent metric display card
│       ├── MarketChart.tsx   # Recharts index visualizer
│       ├── KlineChart.tsx    # Technical charts showing candles & volume
│       ├── MoversList.tsx    # Daily price gainers & losers list
│       └── views/            # Screen views corresponding to paths
│           ├── DashboardView.tsx     # Home panel, indexes and watchlists
│           ├── MarketsView.tsx       # AI stock research terminal
│           ├── StrategiesView.tsx    # Premium stock scanner & criteria setups
│           ├── AIAnalysisView.tsx    # Copilot fundamental statement compiler
│           ├── SettingsView.tsx      # Superuser workspace configs
│           └── sub-panels...         # Supporting panels for detailed charts
│
└── 股市/                     # Hard specification & briefing assets
    ├── 股票.docx
    ├── 避險基金高級分析師.docx
    └── 頂尖產業分析師.docx
```

## Structural Summary
1. **Full-stack Setup**: Backend operates on Node using an Express runtime within `server.ts` with Vite serving as a dynamic SPA helper.
2. **Double Persistence**: Core system utilizes Supabase for the distributed production app while checking, backing up, and querying a highly optimized local SQLite database (`taiwan_stock_unified.db`) as a fallback or for compute-heavy local indicators calculation.
3. **Dual Language**: High-capability Python scripts back the heavy historical loading and crawler operations under `/twstock` and `/scripts`, while TypeScript powers the web application logic.
