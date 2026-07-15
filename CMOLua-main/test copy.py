import sqlite3
con = sqlite3.connect(r"C:\Users\user\.codex\skills\CMOLua-main\mcp\db\DB3K_504.db3")   # 换成真实路径
cur = con.cursor()

for t in ("DataAircraftLoadouts", "DataLoadout", "DataLoadoutWeapons"):
    print("==== " + t + " ====")
    for row in cur.execute("PRAGMA table_info(" + t + ")"):
        print(row[1], row[2])   # 列名, 类型
    print()