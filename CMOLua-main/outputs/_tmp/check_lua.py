"""极简 Lua 平衡检查 + 关键字高风险提示"""
src = open(r"C:\Users\user\.codex\skills\CMOLua-main\outputs\lua\20260708_10_true_time_delay\all.lua", encoding="utf-8").read()
def balance(s):
    pairs = {"(":")","[":"]","{":"}"}
    stack = []
    in_str = None
    i = 0
    line = 1
    while i < len(s):
        c = s[i]
        if c == "\n": line += 1
        # 字符串
        if in_str:
            if c == "\\" and i+1 < len(s):
                i += 2; continue
            if c == in_str:
                in_str = None
            i += 1; continue
        if c in ("'", '"'):
            in_str = c; i += 1; continue
        if c == "-" and i+1 < len(s) and s[i+1] == "-":
            # 整行注释吃掉
            j = s.find("\n", i)
            i = len(s) if j == -1 else j
            continue
        if c == "{":
            stack.append(("}", line))
        elif c == "(":
            stack.append((")", line))
        elif c == "[":
            stack.append(("]", line))
        elif c in (")", "}", "]"):
            if not stack:
                return f"unbalanced {c} at line {line}"
            exp, ln = stack.pop()
            if exp != c:
                return f"mismatch at line {line}: expected {exp} got {c} (opened at {ln})"
        i += 1
    if stack:
        return f"unclosed: {stack[-5:]}"
    return "OK"
print("balance:", balance(src))
print("lines:", src.count("\n"))
print("size:", len(src))
# 关键函数检查
checks = [
    ("fireAt 全局", "function fireAt(" in src and "local function fireAt" not in src),
    ("scheduleOne 局部", "local function scheduleOne" in src),
    ("contact_settle 全局", "_CONTACT_SETTLE_DELAY = 15" in src),
    ("mode='1' 字符串", 'mode = "1"' in src),
    ("Time Trigger", 'ScenEdit_SetTrigger' in src and 'type="Time"' in src),
    ("qty=1 逐枚", src.count("qty=1") >= 2),
    ("Event 自清理", "mode='remove'" in src),
    ("tag 时间戳", "ScenEdit_CurrentTime()" in src and "_" in src),
    ("autodetectable", "autodetectable=true" in src),
    ("蓝方 wcs=0", 'weapon_control_status_surface="0"' in src),
    ("side 红蓝", '"红方"' in src and '"蓝方"' in src),
    ("不硬编瞎写 DBID", "2496" in src and "9682" in src and "2862" in src and "3883" in src and "2007" in src and "2137" in src),
]
for name, ok in checks:
    print(("[OK]   " if ok else "[FAIL] ") + name)