"""强化 v4 红线检查"""
src = open(r"C:\Users\user\.codex\skills\CMOLua-main\outputs\lua\20260708_10_true_time_delay\all.lua", encoding="utf-8").read()
def balance(s):
    pairs = {"(":")","[":"]","{":"}"}
    stack = []; in_str = None; i = 0; line = 1
    while i < len(s):
        c = s[i]
        if c == "\n": line += 1
        if in_str:
            if c == "\\" and i+1 < len(s):
                i += 2; continue
            if c == in_str: in_str = None
            i += 1; continue
        if c in ("'", '"'): in_str = c; i += 1; continue
        if c == "-" and i+1 < len(s) and s[i+1] == "-":
            j = s.find("\n", i); i = len(s) if j == -1 else j; continue
        if c == "{": stack.append(("}", line))
        elif c == "(": stack.append((")", line))
        elif c == "[": stack.append(("]", line))
        elif c in (")", "}", "]"):
            if not stack: return f"unbalanced {c} at line {line}"
            exp, ln = stack.pop()
            if exp != c: return f"mismatch at line {line}: expected {exp} got {c} (opened at {ln})"
        i += 1
    if stack: return f"unclosed: {stack[-5:]}"
    return "OK"
print("balance:", balance(src))

checks = [
    ("AddSide 用 table",  'ScenEdit_AddSide, {name=_SIDE_RED' in src and 'pcall(ScenEdit_AddSide, _SIDE_RED' not in src),
    ("阵营颜色",          'color="255,0,0"' in src and 'color="0,0,255"' in src),
    ("scheduleOne 拆 qty", '("fireAt(%q,%q,%d,1)\\n")' in src),
    ("scheduleRtb 全局",  'local function scheduleRtb' in src),
    ("RTB Time 触发器",   'scheduleRtb(rtbDelay, tag)' in src),
    ("RTB 强设 course",   "_CARRIER_LAT" in src and "_CARRIER_LON" in src and "course={" in src),
    ("RTB 设 homebase",   "homebase=" in src),
    ("RTB 设 base",       "base=" in src),
    ("fireAt 全局",       "function fireAt(" in src and "local function fireAt" not in src),
    ("contact_settle 全局", "_CONTACT_SETTLE_DELAY = 15" in src),
    ("Time Trigger",      'ScenEdit_SetTrigger' in src and 'type="Time"' in src),
    ("Event 自清理",      "mode='remove'" in src),
    ("tag 时间戳",        "ScenEdit_CurrentTime()" in src),
    ("autodetectable",    "autodetectable=true" in src),
    ("蓝方 wcs=0",        'weapon_control_status_surface="0"' in src),
    ("side 中文",         '"红方"' in src and '"蓝方"' in src),
    ("DBID 实测集合",     all(str(d) in src for d in [2007, 3883, 2496, 9682, 2137, 2862])),
    ("mode='1' 字符串",   'mode = "1"' in src),
    ("OMNI awareness",    'awareness="OMNI"' in src),
    ("H 敌对",            '"H"' in src),
    ("RTB 时间线打印",    "导弹命中" in src),
]
ok_n = 0
for name, ok in checks:
    if ok: ok_n += 1
    print(("[OK]   " if ok else "[FAIL] ") + name)
print(f"\n通过 {ok_n}/{len(checks)} 项")