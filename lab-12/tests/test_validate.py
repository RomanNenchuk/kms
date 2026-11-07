"""AST-перевірка text-to-SQL: лише SELECT, whitelist таблиць, заборонені функції, LIMIT, тайм-аут."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from text2sql.pipeline import (InvalidSQL, PolicyViolation, QueryTimeout, execute_safe,  # noqa: E402
                               open_readonly, validate)


def test_select_gets_limit():
    assert "LIMIT 1000" in validate("SELECT COUNT(*) FROM fact_flight").upper()


def test_big_limit_is_capped():
    assert "LIMIT 1000" in validate("SELECT * FROM fact_flight LIMIT 999999").upper()


def test_small_limit_kept():
    assert "LIMIT 5" in validate("SELECT * FROM fact_flight LIMIT 5").upper()


def test_cte_allowed():
    validate("WITH a AS (SELECT airline_key FROM fact_flight) SELECT * FROM a")


@pytest.mark.parametrize("bad", [
    "DROP TABLE fact_flight", "DELETE FROM fact_flight", "INSERT INTO dim_airline VALUES (1)",
    "UPDATE fact_flight SET cancelled = 0", "CREATE TABLE x AS SELECT 1", "COPY fact_flight TO 'x.csv'",
    "PRAGMA database_list", "ATTACH 'x.db'", "SET enable_external_access = true",
    "SELECT 1; DROP TABLE fact_flight",
    "SELECT * FROM read_csv('/etc/passwd')", "SELECT read_text('/etc/passwd')", "SELECT getenv('HOME')",
    "SELECT * FROM information_schema.tables", "SELECT * FROM secret_table",
    "SELECT * INTO copy_t FROM fact_flight",
])
def test_policy_rejects(bad):
    with pytest.raises(PolicyViolation):
        validate(bad)


def test_syntax_error_is_invalid():
    with pytest.raises(InvalidSQL):
        validate("SELEC FROM WHERE")


@pytest.mark.skipif(not (ROOT / "data" / "hub.duckdb").exists(), reason="спочатку python etl/load.py")
class TestExecution:
    def test_readonly_connection_cannot_write(self):
        con = open_readonly()
        with pytest.raises(Exception):
            con.execute("DELETE FROM fact_flight")

    def test_timeout(self):
        con = open_readonly()
        sql = validate("SELECT COUNT(*) FROM fact_flight a, fact_flight b, fact_flight c, fact_flight d")
        with pytest.raises(QueryTimeout):
            execute_safe(con, sql, timeout=1)

    def test_row_cap_applied(self):
        con = open_readonly()
        df = execute_safe(con, validate("SELECT * FROM fact_flight"))
        assert len(df) == 1000
