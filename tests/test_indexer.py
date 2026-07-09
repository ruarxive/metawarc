import duckdb

from metawarc.cmds.dump import Dumper
from metawarc.cmds.indexer import Indexer
from metawarc.dbutil import records_table_path


def test_index_creates_schema(indexed_workspace):
    db = str(indexed_workspace["db"])
    con = duckdb.connect(db)
    try:
        files = con.sql("select * from files").fetchall()
        tables = con.sql("select * from tables").fetchall()
    finally:
        con.close()
    assert len(files) == 1
    assert len(tables) >= 2
    assert indexed_workspace["data_dir"].exists()


def test_calc_stats_returns_rows(indexed_workspace, capsys):
    db = str(indexed_workspace["db"])
    Indexer().calc_stats(db, mode="mimes")
    captured = capsys.readouterr()
    assert "text/html" in captured.out or "application/pdf" in captured.out


def test_listfiles_by_ext(indexed_workspace, capsys):
    db = str(indexed_workspace["db"])
    Dumper().listfiles(dbfile=db, exts="html", silent=True)
    captured = capsys.readouterr()
    assert "text/html" in captured.out


def test_records_table_lookup_by_wf_id(indexed_workspace):
    db = str(indexed_workspace["db"])
    con = duckdb.connect(db)
    try:
        wf_id = con.sql("select id from files").fetchone()[0]
        path = records_table_path(con, wf_id)
    finally:
        con.close()
    assert path is not None
    assert path.endswith("_records.parquet")
