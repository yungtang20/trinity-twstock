# TRINITY 依賴與可重現環境

支援 Python 3.12。依賴版本以專案根目錄的 requirements 檔為準，文件不再重複維護另一套版本表。

| 檔案 | 用途 |
|---|---|
| `requirements.txt` | 核心執行環境：資料處理、HTTP、Rich、dotenv。 |
| `requirements-dev.txt` | 核心環境加上 pytest、coverage、ruff、mypy。 |
| `requirements-ai.txt` | 僅啟用 vendored Kronos 時所需的可選模型套件。 |

## 建立環境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

需要 Kronos 時，再安裝：

```powershell
python -m pip install -r requirements-ai.txt
```

預設本機模型目錄：

| Hugging Face repository | 本機目錄 |
|---|---|
| `NeoQuasar/Kronos-base` | `models/kronos-base` |
| `NeoQuasar/Kronos-Tokenizer-base` | `models/kronos-tokenizer-base` |

未設定 `KRONOS_DEVICE` 時會自動選擇 CUDA／MPS／CPU；若要強制 CPU，可設定
`KRONOS_DEVICE=cpu`。全市場排行使用 Monte Carlo 快速初篩，只有指定個股才載入
Kronos-base，避免對上千檔股票逐檔執行大型模型。

`torch` 的 CPU／CUDA 安裝檔必須依作業系統、Python 版本與硬體選擇官方相容版本；因此它放在 optional requirements，而不是強制安裝於基本環境。

## 驗證

從專案根目錄執行：

```powershell
python -m pytest
python -m ruff check .
python -m mypy twstock
```

若從專案父目錄執行 package entry point：

```powershell
python -m twstock.main --help
```

本機憑證與 token 放在 `api.env`。先複製 `api.env.example`，填入新取得的值；`api.env` 已被 `.gitignore` 排除，且不應提交或貼到 issue／日誌。
