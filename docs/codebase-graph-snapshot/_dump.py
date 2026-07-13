"""Dump codebase-memory graph (D-twse) to TSV snapshots for plain-text AI review.

ponytail: one-shot dump, no framework, overwrites prior output. Ceiling: if
graph schema changes (column renames), rewrite SELECTs here — not parameterized.
"""

import os
import sqlite3
import sys

DB = os.path.expanduser("~/.cache/codebase-memory-mcp/D-twse.db")
OUT = "D:/twse/docs/codebase-graph-snapshot"
PROJECT = "D-twse"


def main() -> int:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        # nodes.tsv
        nodes_sql = """
            SELECT id, label, name, qualified_name, file_path, start_line, end_line
            FROM nodes
            WHERE project = ?
            ORDER BY file_path, start_line, name
        """
        nodes = conn.execute(nodes_sql, (PROJECT,)).fetchall()

        def esc(v):
            """ponytail: strip CR/LF/TAB so one node/edge never spans multiple TSV rows."""
            if v is None:
                return ""
            s = str(v)
            return s.replace("\r", " ").replace("\n", " ").replace("\t", " ")

        with open(os.path.join(OUT, "02-nodes.tsv"), "w", encoding="utf-8", newline="") as f:
            f.write("id\tlabel\tname\tqualified_name\tfile_path\tstart_line\tend_line\n")
            for r in nodes:
                f.write("\t".join(esc(v) for v in r) + "\n")

        # edges.tsv with qualified_name on both ends (readable without id lookup)
        edges_sql = """
            SELECT e.source_id, sn.qualified_name, e.type, e.target_id,
                   tn.qualified_name, e.properties
            FROM edges e
            JOIN nodes sn ON sn.id = e.source_id AND sn.project = e.project
            JOIN nodes tn ON tn.id = e.target_id AND tn.project = e.project
            WHERE e.project = ?
            ORDER BY e.type, sn.qualified_name, tn.qualified_name
        """
        edges = conn.execute(edges_sql, (PROJECT,)).fetchall()
        with open(os.path.join(OUT, "03-edges.tsv"), "w", encoding="utf-8", newline="") as f:
            f.write(
                "source_id\tsource_qualified_name\tedge_type\t"
                "target_id\ttarget_qualified_name\tproperties\n"
            )
            for r in edges:
                f.write("\t".join(esc(v) for v in r) + "\n")

        print(f"nodes: {len(nodes)} rows")
        print(f"edges: {len(edges)} rows")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
