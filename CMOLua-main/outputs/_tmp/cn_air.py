import sqlite3
DB = r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3"
con = sqlite3.connect(DB)
cur = con.cursor()

# 看 Deprecated 存的是什么
print("=== DataFacility.Deprecated distinct / types ===")
rows = list(cur.execute("SELECT Deprecated, COUNT(*) FROM DataFacility GROUP BY Deprecated"))
for r in rows: print(" Deprecated=", repr(r[0]), " n=", r[1])

# 2018 不加 Deprecated 限定的总数
print("\n=== 2018 总数 ===")
print(" all:", cur.execute("SELECT COUNT(*) FROM DataFacility WHERE OperatorCountry=2018").fetchone())
print(" Deprecated='No':", cur.execute("SELECT COUNT(*) FROM DataFacility WHERE OperatorCountry=2018 AND Deprecated='No'").fetchone())
print(" Deprecated='False':", cur.execute("SELECT COUNT(*) FROM DataFacility WHERE OperatorCountry=2018 AND Deprecated='False'").fetchone())
print(" IS NOT TRUE:", cur.execute("SELECT COUNT(*) FROM DataFacility WHERE OperatorCountry=2018 AND NOT Deprecated").fetchone())
print(" NOT 1:", cur.execute("SELECT COUNT(*) FROM DataFacility WHERE OperatorCountry=2018 AND Deprecated != 1").fetchone())

# 直接看中国 (2018) 设施类型分布
print("\n=== 2018 设施 Cat=9001 (Air Base) 全部 ===")
rows = list(cur.execute("SELECT ID, Name, Category, Type, OperatorService, Length, Width FROM DataFacility WHERE OperatorCountry=2018 AND Category=9001"))
print(" count:", len(rows))
for r in rows:
    print(f"  DBID={r[0]} Cat={r[2]} Type={r[3]} Svc={r[4]} L={r[5]}W={r[6]}  {r[1]}")

# 跑道类 (2001/2002/2003)
print("\n=== 2018 Cat=2001 (Runway) 全部 ===")
rows = list(cur.execute("SELECT ID, Name, Type, OperatorService, Length, Width FROM DataFacility WHERE OperatorCountry=2018 AND Category=2001"))
print(" count:", len(rows))
for r in rows[:30]:
    print(f"  DBID={r[0]} Type={r[2]} Svc={r[3]} L={r[4]}m W={r[5]}m  {r[1]}")

# Cat=2002 Taxiway / 2003 RAP
print("\n=== 2018 Cat=2002 全部 ===")
rows = list(cur.execute("SELECT ID, Name, Type, OperatorService, Length, Width FROM DataFacility WHERE OperatorCountry=2018 AND Category=2002"))
print(" count:", len(rows))
for r in rows[:30]:
    print(f"  DBID={r[0]} Type={r[2]} Svc={r[3]} L={r[4]}m W={r[5]}m  {r[1]}")

print("\n=== 2018 Cat=2003 全部 ===")
rows = list(cur.execute("SELECT ID, Name, Type, OperatorService, Length, Width FROM DataFacility WHERE OperatorCountry=2018 AND Category=2003"))
print(" count:", len(rows))
for r in rows[:30]:
    print(f"  DBID={r[0]} Type={r[2]} Svc={r[3]} L={r[4]}m W={r[5]}m  {r[1]}")

con.close()
