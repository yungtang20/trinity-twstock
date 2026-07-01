import os

# 從 twstock/ 內執行 pytest 時，自動回到專案根目錄
if os.path.basename(os.getcwd()) == "twstock":
    os.chdir(os.path.dirname(os.getcwd()))
