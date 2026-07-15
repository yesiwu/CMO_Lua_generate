# """
# 第一层是 JSON Intake，也就是通用 JSON 读取层。
# 它不假设所有 JSON 都长得一样，而是先做 schema profile：
# 统计顶层字段、字段路径、字段类型、数组规模、空值、异常键、坐标字段、单位字段、装备字段、任务字段。
# 你的样例里已经有这类脏数据风险，比如字段命名不统一，
# UnitLocation 里有 alt/lat/lon，也有 Altitude/Latitude/Longitude；部分值可能为空；
# 还有类似 TacticalGra phic 这种字段名异常。
# 这一层要做“容错读取”，不能一上来写死 Pydantic 强 schema，否则真实军方数据稍微变一下就崩。



# 输入：A1场景_new.json
# 执行：python json_profiler.py A1场景_new.json --out outputs/a1
# 输出：
#   outputs/a1/schema_profile.json
#   outputs/a1/scenario_ir.json
#   outputs/a1/scene_contract.md
# """


# """
# 这个文件作为入口。它负责：

# 读取 JSON；
# 扫描整个 JSON 的字段结构；
# 输出 schema_profile.json；
# 调用 scenario_ir.py 生成 IR 和文本合同。
# """
from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List

from scenario_ir import build_ir, render_scene_contract, save_json


def load_json(path: str) -> Any:
    """
    utf-8-sig 可以兼容带 BOM 的 JSON。
    """
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def normalize_schema_path(path: str) -> str:
    """
    把数组下标归一化，避免 Unit[0]、Unit[1] 被当成两个 schema 字段。
    例如：
      WarPower.ForceSides[0].Unit[1].UnitName
    变成：
      WarPower.ForceSides[].Unit[].UnitName
    """
    result = []
    i = 0
    while i < len(path):
        if path[i] == "[":
            j = path.find("]", i)
            if j != -1:
                result.append("[]")
                i = j + 1
                continue
        result.append(path[i])
        i += 1
    return "".join(result)


def preview_value(value: Any, max_len: int = 120) -> Any:
    if isinstance(value, (dict, list)):
        return f"<{type_name(value)}>"
    text = repr(value)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return value


def walk_json(
    value: Any,
    path: str,
    stats: Dict[str, Dict[str, Any]],
    anomalies: List[Dict[str, Any]],
) -> None:
    schema_path = normalize_schema_path(path)

    item = stats.setdefault(schema_path, {
        "path": schema_path,
        "types": Counter(),
        "count": 0,
        "null_count": 0,
        "empty_string_count": 0,
        "examples": [],
        "array_lengths": [],
    })

    t = type_name(value)
    item["types"][t] += 1
    item["count"] += 1

    if value is None:
        item["null_count"] += 1

    if isinstance(value, str) and value.strip() == "":
        item["empty_string_count"] += 1

    if len(item["examples"]) < 5 and not isinstance(value, (dict, list)):
        item["examples"].append(preview_value(value))

    if isinstance(value, list):
        item["array_lengths"].append(len(value))
        for idx, child in enumerate(value):
            walk_json(child, f"{path}[{idx}]", stats, anomalies)

    elif isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                anomalies.append({
                    "type": "non_string_key",
                    "path": path,
                    "message": f"发现非字符串 key：{key!r}",
                    "severity": "medium",
                })

            if isinstance(key, str):
                if key != key.strip():
                    anomalies.append({
                        "type": "key_has_outer_whitespace",
                        "path": f"{path}.{key}",
                        "message": f"字段名前后存在空白：{key!r}",
                        "severity": "medium",
                    })

                # 例如样例中可能出现 TacticalGra phic 这种内部空格字段。
                if any(ch.isspace() for ch in key):
                    anomalies.append({
                        "type": "key_has_inner_whitespace",
                        "path": f"{path}.{key}",
                        "message": f"字段名内部存在空白字符：{key!r}",
                        "severity": "medium",
                    })

            child_path = f"{path}.{key}" if path != "$" else str(key)
            walk_json(child, child_path, stats, anomalies)


def detect_coordinate_anomalies(stats: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    anomalies: List[Dict[str, Any]] = []

    coord_names = {
        "Latitude": (-90, 90),
        "latitude": (-90, 90),
        "lat": (-90, 90),
        "Longitude": (-180, 180),
        "longitude": (-180, 180),
        "lon": (-180, 180),
    }

    for path, item in stats.items():
        last = path.split(".")[-1]
        if last not in coord_names:
            continue

        low, high = coord_names[last]
        examples = item.get("examples", [])

        if item.get("null_count", 0) > 0 or item.get("empty_string_count", 0) > 0:
            anomalies.append({
                "type": "coordinate_missing_value",
                "path": path,
                "message": f"坐标字段存在 null 或空字符串：null={item.get('null_count')}, empty={item.get('empty_string_count')}",
                "severity": "high",
            })

        for ex in examples:
            try:
                v = float(ex)
            except (TypeError, ValueError):
                anomalies.append({
                    "type": "coordinate_non_numeric",
                    "path": path,
                    "message": f"坐标示例不是数字：{ex!r}",
                    "severity": "high",
                })
                continue

            if not (low <= v <= high):
                anomalies.append({
                    "type": "coordinate_out_of_range",
                    "path": path,
                    "message": f"坐标示例超出范围：{ex!r}, expected=[{low},{high}]",
                    "severity": "high",
                })

    return anomalies


def finalize_stats(stats: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []

    for path, item in sorted(stats.items()):
        types_counter: Counter = item["types"]
        array_lengths = item.get("array_lengths", [])

        result.append({
            "path": path,
            "types": dict(types_counter),
            "count": item["count"],
            "null_count": item["null_count"],
            "empty_string_count": item["empty_string_count"],
            "examples": item["examples"],
            "array_length_min": min(array_lengths) if array_lengths else None,
            "array_length_max": max(array_lengths) if array_lengths else None,
        })

    return result


def build_schema_profile(raw: Any) -> Dict[str, Any]:
    stats: Dict[str, Dict[str, Any]] = {}
    anomalies: List[Dict[str, Any]] = []

    walk_json(raw, "$", stats, anomalies)
    anomalies.extend(detect_coordinate_anomalies(stats))

    top_level_keys = list(raw.keys()) if isinstance(raw, dict) else []

    type_histogram = Counter()
    for item in stats.values():
        for t, cnt in item["types"].items():
            type_histogram[t] += cnt

    profile = {
        "profile_version": "0.1",
        "top_level_keys": top_level_keys,
        "path_count": len(stats),
        "type_histogram": dict(type_histogram),
        "field_stats": finalize_stats(stats),
        "anomalies": anomalies,
        "anomaly_summary": dict(Counter(a["type"] for a in anomalies)),
    }

    return profile


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile CMO scenario JSON and build ScenarioIR + Scene Contract."
    )
    parser.add_argument("input", help="输入 JSON 文件路径，例如 data/A1场景_new.json")
    parser.add_argument("--out", default="outputs/a1", help="输出目录")
    args = parser.parse_args()

    raw = load_json(args.input)

    os.makedirs(args.out, exist_ok=True)

    profile = build_schema_profile(raw)
    ir = build_ir(raw, profile)
    contract = render_scene_contract(ir)

    schema_profile_path = os.path.join(args.out, "schema_profile.json")
    scenario_ir_path = os.path.join(args.out, "scenario_ir.json")
    scene_contract_path = os.path.join(args.out, "scene_contract.md")

    save_json(schema_profile_path, profile)
    save_json(scenario_ir_path, ir)

    with open(scene_contract_path, "w", encoding="utf-8") as f:
        f.write(contract)

    print("[ok] schema_profile:", schema_profile_path)
    print("[ok] scenario_ir:", scenario_ir_path)
    print("[ok] scene_contract:", scene_contract_path)
    print()
    print("[summary]")
    print("top_level_keys:", profile["top_level_keys"])
    print("path_count:", profile["path_count"])
    print("anomaly_summary:", profile["anomaly_summary"])
    print("unit_count:", ir["summary"]["unit_count"])
    print("equipment_count:", ir["summary"]["equipment_count"])
    print("warning_count:", len(ir["warnings"]))


if __name__ == "__main__":
    main()