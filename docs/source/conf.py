# ============================================
# Sphinx 文件配置
# ============================================

import os
import sys

# 加入專案根目錄
sys.path.insert(0, os.path.abspath('../..'))

# 專案資訊
project = 'TRINITY TWStock'
copyright = '2024, yungtang'
author = 'yungtang'
release = '0.1.0'

# 擴展
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.coverage',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
]

# 模板路徑
templates_path = ['_templates']
exclude_patterns = []

# HTML 主題
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Intersphinx 映射
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'pandas': ('https://pandas.pydata.org/docs/', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
}

# Napoleon 設定 (Google 風格文件字串)
napoleon_google_docstring = True
napoleon_numpy_docstring = False
