TRINITY TWStock 文件
===================

.. toctree::
   :maxdepth: 2
   :caption: 目錄:

   getting-started
   api-reference
   contributing

簡介
----

TRINITY TWStock 是一個高效的台灣股市數據抓取與分析工具。

功能特色
--------

- **即時數據**: 即時查詢台灣股市股價
- **歷史分析**: 抓取並分析歷史股價數據
- **技術指標**: 計算各種技術分析指標
- **策略回測**: 回測交易策略

快速開始
--------

.. code-block:: bash

   # 安裝
   pip install -r requirements.txt

   # 執行
   python twstock/main.py

API 參考
--------

.. automodule:: twstock.fetcher
   :members:

.. automodule:: twstock.calculator
   :members:

貢獻指南
--------

請參閱 `CONTRIBUTING.md <CONTRIBUTING.md>`_ 了解如何貢獻此專案。
