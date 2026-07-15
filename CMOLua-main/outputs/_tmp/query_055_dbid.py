import json
import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parents[2] / "mcp" / "db" / "DB3K_504.db3"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row

sql = """
SELECT
  ID AS dbid,
  Name AS name,
  Type,
  OperatorCountry,
  YearCommissioned,
  YearDecommissioned,
  Deprecated,
  Comments AS description
FROM DataShip
WHERE Name LIKE '%Type 055%'
   OR Name LIKE '%055 Renhai%'
ORDER BY COALESCE(Deprecated, 0), ID
"""

rows = con.execute(sql).fetchall()
print(json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2))
