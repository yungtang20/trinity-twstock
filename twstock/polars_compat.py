#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
polars.py - Dynamic Polars to Pandas compatibility layer [AI MOD]
If the native rust-compiled 'polars' package is missing, 
this file acts as a seamless DataFrame/Series/Expr shim using pandas.
"""

import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Critical: Remove twstock dir from sys.path to prevent self-import recursion
_paths = list(sys.path)
if _CURRENT_DIR in sys.path:
    sys.path.remove(_CURRENT_DIR)

# Remove any cached 'polars' module that points to ourselves
_old_polars = sys.modules.get("polars")
if _old_polars is not None:
    # Check if it's ourselves (the shim)
    _our_file = os.path.abspath(__file__)
    _mod_file = getattr(_old_polars, '__file__', '')
    if _mod_file and os.path.abspath(_mod_file) == _our_file:
        del sys.modules["polars"]

try:
    import polars as _pl
    if hasattr(_pl, "DataFrame"):
        _HAS_REAL = True
        # Expose the real polars API
        for _key in dir(_pl):
            if not _key.startswith('_'):
                globals()[_key] = getattr(_pl, _key)
    else:
        _HAS_REAL = False
except ImportError:
    _HAS_REAL = False
finally:
    # Restore original path
    sys.path = _paths

if not _HAS_REAL:
    # Provide seamless pandas fallback
    import pandas as pd
    import numpy as np

    # Type/Dtype mappings
    Utf8 = "str"
    Float64 = "float64"
    Int64 = "int64"

    class Expr:
        def __init__(self, fn):
            self.fn = fn
            self._alias = None
            
        def __call__(self, df):
            return self.fn(df)
            
        def alias(self, name):
            new_expr = Expr(self.fn)
            new_expr._alias = name
            return new_expr
            
        def fill_null(self, value):
            return Expr(lambda df: self.fn(df).fillna(value))
            
        def cast(self, dtype):
            return Expr(lambda df: self.fn(df))
            
        @property
        def str(self):
            class StrNamespace:
                def __init__(self, expr):
                    self.expr = expr
                def strip_chars(self):
                    return Expr(lambda df: self.expr.fn(df).astype(str).str.strip())
            return StrNamespace(self)
            
        def __eq__(self, other):
            return Expr(lambda df: self.fn(df) == other)
        def __ne__(self, other):
            return Expr(lambda df: self.fn(df) != other)
        def __gt__(self, other):
            return Expr(lambda df: self.fn(df) > other)
        def __ge__(self, other):
            return Expr(lambda df: self.fn(df) >= other)
        def __lt__(self, other):
            return Expr(lambda df: self.fn(df) < other)
        def __le__(self, other):
            return Expr(lambda df: self.fn(df) <= other)

        def __and__(self, other):
            if isinstance(other, Expr):
                return Expr(lambda df: self.fn(df) & other.fn(df))
            return Expr(lambda df: self.fn(df) & other)

        def __or__(self, other):
            if isinstance(other, Expr):
                return Expr(lambda df: self.fn(df) | other.fn(df))
            return Expr(lambda df: self.fn(df) | other)

        def __invert__(self):
            return Expr(lambda df: ~self.fn(df))

        def shift(self, periods=1):
            return Expr(lambda df: self.fn(df).shift(periods))

        def __add__(self, other):
            if isinstance(other, Expr):
                return Expr(lambda df: self.fn(df) + other.fn(df))
            return Expr(lambda df: self.fn(df) + other)
            
        def __radd__(self, other):
            if isinstance(other, Expr):
                return Expr(lambda df: other.fn(df) + self.fn(df))
            return Expr(lambda df: other + self.fn(df))

        def __sub__(self, other):
            if isinstance(other, Expr):
                return Expr(lambda df: self.fn(df) - other.fn(df))
            return Expr(lambda df: self.fn(df) - other)
            
        def __rsub__(self, other):
            if isinstance(other, Expr):
                return Expr(lambda df: other.fn(df) - self.fn(df))
            return Expr(lambda df: other - self.fn(df))

        def __mul__(self, other):
            if isinstance(other, Expr):
                return Expr(lambda df: self.fn(df) * other.fn(df))
            return Expr(lambda df: self.fn(df) * other)
            
        def __rmul__(self, other):
            if isinstance(other, Expr):
                return Expr(lambda df: other.fn(df) * self.fn(df))
            return Expr(lambda df: other * self.fn(df))

        def __truediv__(self, other):
            if isinstance(other, Expr):
                return Expr(lambda df: self.fn(df) / other.fn(df))
            return Expr(lambda df: self.fn(df) / other)
            
        def __rtruediv__(self, other):
            if isinstance(other, Expr):
                return Expr(lambda df: other.fn(df) / self.fn(df))
            return Expr(lambda df: other / self.fn(df))

        def abs(self):
            return Expr(lambda df: self.fn(df).abs())

        def rolling_mean(self, window_size):
            return Expr(lambda df: self.fn(df).rolling(window=window_size).mean())
            
        def rolling_std(self, window_size):
            return Expr(lambda df: self.fn(df).rolling(window=window_size).std())

        def is_not_null(self):
            return Expr(lambda df: self.fn(df).notnull())
            
        def is_null(self):
            return Expr(lambda df: self.fn(df).isnull())

    def col(name):
        return Expr(lambda df: df[name])
        
    def lit(value):
        return Expr(lambda df: pd.Series([value] * len(df), index=df.index))

    def max_horizontal(*exprs):
        def compute(df):
            vals = []
            for e in exprs:
                if isinstance(e, Expr):
                    vals.append(e(df))
                elif isinstance(e, str):
                    vals.append(df[e])
            return pd.concat(vals, axis=1).max(axis=1)
        return Expr(compute)

    def min_horizontal(*exprs):
        def compute(df):
            vals = []
            for e in exprs:
                if isinstance(e, Expr):
                    vals.append(e(df))
                elif isinstance(e, str):
                    vals.append(df[e])
            return pd.concat(vals, axis=1).min(axis=1)
        return Expr(compute)

    class WhenThenOtherwise:
        def __init__(self, cond_expr):
            self.cond_expr = cond_expr
            self.then_expr = None
            
        def then(self, expr_or_val):
            self.then_expr = expr_or_val
            return self
            
        def otherwise(self, expr_or_val):
            import numpy as np
            cond_expr = self.cond_expr
            then_expr = self.then_expr
            otherwise_expr = expr_or_val
            
            def compute(df):
                c = cond_expr(df)
                
                if isinstance(then_expr, Expr):
                    t = then_expr(df)
                elif isinstance(then_expr, str):
                    t = df[then_expr]
                else:
                    t = then_expr
                    
                if isinstance(otherwise_expr, Expr):
                    o = otherwise_expr(df)
                elif isinstance(otherwise_expr, str):
                    o = df[otherwise_expr]
                else:
                    o = otherwise_expr
                    
                res = np.where(c, t, o)
                return pd.Series(res, index=df.index)
            return Expr(compute)
            
    def when(condition):
        return WhenThenOtherwise(condition)

    class Series:
        def __init__(self, ps):
            self._ps = ps
            
        def to_list(self):
            return list(self._ps)
            
        def to_numpy(self):
            return self._ps.to_numpy()
            
        def max(self):
            return self._ps.max()
            
        def min(self):
            return self._ps.min()
            
        def mean(self):
            return self._ps.mean()

        def sum(self):
            return self._ps.sum()
            
        def std(self):
            return self._ps.std()
            
        def fill_null(self, value):
            return Series(self._ps.fillna(value))
            
        def drop_nulls(self):
            return Series(self._ps.dropna())

        def unique(self):
            return Series(self._ps.unique())

        def is_not_null(self):
            return Series(self._ps.notnull())
            
        def is_null(self):
            return Series(self._ps.isnull())

        def pct_change(self):
            return Series(self._ps.pct_change())

        def rolling_mean(self, window_size):
            return Series(self._ps.rolling(window=window_size).mean())
            
        def rolling_std(self, window_size):
            return Series(self._ps.rolling(window=window_size).std())

        def arg_max(self):
            return self._ps.values.argmax()
            
        def arg_min(self):
            return self._ps.values.argmin()

        def slice(self, offset, length=None):
            if length is None:
                return Series(self._ps.iloc[offset:])
            return Series(self._ps.iloc[offset:offset + length])
            
        def __len__(self):
            return len(self._ps)
            
        def __getitem__(self, key):
            if isinstance(key, (int, np.integer)):
                idx = int(key) if key >= 0 else len(self._ps) + int(key)
                return self._ps.iloc[idx]
            return Series(self._ps.iloc[key])

        def __add__(self, other):
            if isinstance(other, Series):
                return Series(self._ps + other._ps)
            return Series(self._ps + other)
            
        def __radd__(self, other):
            if isinstance(other, Series):
                return Series(other._ps + self._ps)
            return Series(other + self._ps)

        def __sub__(self, other):
            if isinstance(other, Series):
                return Series(self._ps - other._ps)
            return Series(self._ps - other)
            
        def __rsub__(self, other):
            if isinstance(other, Series):
                return Series(other._ps - self._ps)
            return Series(other - self._ps)

        def __mul__(self, other):
            if isinstance(other, Series):
                return Series(self._ps * other._ps)
            return Series(self._ps * other)
            
        def __rmul__(self, other):
            if isinstance(other, Series):
                return Series(other._ps * self._ps)
            return Series(other * self._ps)

        def __truediv__(self, other):
            if isinstance(other, Series):
                return Series(self._ps / other._ps)
            return Series(self._ps / other)
            
        def __rtruediv__(self, other):
            if isinstance(other, Series):
                return Series(other._ps / self._ps)
            return Series(other / self._ps)

    class DataFrame:
        def __init__(self, pdf=None, schema=None):
            if pdf is not None:
                if isinstance(pdf, pd.DataFrame):
                    self._pdf = pdf
                elif isinstance(pdf, DataFrame):
                    self._pdf = pdf._pdf
                else:
                    self._pdf = pd.DataFrame(pdf)
            elif schema is not None:
                cols = list(schema.keys()) if isinstance(schema, dict) else list(schema)
                self._pdf = pd.DataFrame(columns=cols)
            else:
                self._pdf = pd.DataFrame()
            
        @property
        def columns(self):
            return list(self._pdf.columns)
            
        @property
        def height(self):
            return len(self._pdf)
            
        def is_empty(self):
            return self._pdf.empty

        def unique(self, subset=None, keep="first", maintain_order=False):
            return DataFrame(self._pdf.drop_duplicates(subset=subset, keep=keep).copy())

        def to_dicts(self):
            return self._pdf.to_dict(orient="records")
            
        def tail(self, n=5):
            return DataFrame(self._pdf.tail(n).copy())
            
        def head(self, n=5):
            return DataFrame(self._pdf.head(n).copy())

        def slice(self, offset, length=None):
            if length is None:
                return DataFrame(self._pdf.iloc[offset:].copy())
            return DataFrame(self._pdf.iloc[offset:offset + length].copy())
            
        def sort(self, by, descending=False):
            if isinstance(descending, (list, tuple)):
                ascending = [not d for d in descending]
            else:
                ascending = not descending
            return DataFrame(self._pdf.sort_values(by=by, ascending=ascending).copy())
            
        def drop_nulls(self, subset=None):
            return DataFrame(self._pdf.dropna(subset=subset).copy())

        def drop(self, columns):
            if isinstance(columns, str):
                columns = [columns]
            valid_cols = [c for c in columns if c in self._pdf.columns]
            return DataFrame(self._pdf.drop(columns=valid_cols).copy())
            
        def filter(self, expr):
            if isinstance(expr, Expr):
                mask = expr(self._pdf)
                return DataFrame(self._pdf[mask].copy())
            else:
                return DataFrame(self._pdf[expr].copy())
                
        def select(self, exprs):
            if isinstance(exprs, (str, Expr)):
                exprs = [exprs]
            new_pdf = pd.DataFrame()
            for expr in exprs:
                if isinstance(expr, Expr):
                    col_data = expr(self._pdf)
                    name = expr._alias or col_data.name or "column"
                    new_pdf[name] = col_data
                elif isinstance(expr, str):
                    new_pdf[expr] = self._pdf[expr]
            return DataFrame(new_pdf)
            
        def with_columns(self, exprs):
            new_pdf = self._pdf.copy()
            if not isinstance(exprs, list):
                exprs = [exprs]
            for expr in exprs:
                if isinstance(expr, Expr):
                    col_data = expr(new_pdf)
                    name = expr._alias or col_data.name or "column"
                    new_pdf[name] = col_data
                elif isinstance(expr, str):
                    pass
            return DataFrame(new_pdf)
            
        def rename(self, mapping):
            return DataFrame(self._pdf.rename(columns=mapping).copy())
            
        def join(self, other, on, how="inner"):
            res_pdf = self._pdf.merge(other._pdf, on=on, how=how)
            return DataFrame(res_pdf)
            
        def iter_rows(self, named=True):
            for idx, row in self._pdf.iterrows():
                yield dict(row)
                
        def __getitem__(self, key):
            if isinstance(key, int):
                idx = key if key >= 0 else len(self._pdf) + key
                return DataFrame(self._pdf.iloc[idx:idx+1])
            return Series(self._pdf[key])
            
        def __len__(self):
            return len(self._pdf)

    def read_database(query, connection, execute_options=None):
        params = None
        if execute_options and "parameters" in execute_options:
            params = execute_options["parameters"]
        pdf = pd.read_sql_query(query, connection, params=params)
        return DataFrame(pdf)