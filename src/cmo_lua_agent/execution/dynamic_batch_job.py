"""单次尝试：CMO BatchRunner 任务构建器
“每次真正要跑一次 CMO 时，给这次仿真单独准备一个完整、独立的运行目录和 BatchRunner 任务文件。”
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil

from cmo_lua_agent.evolution.production_assets import file_sha256
from cmo_lua_agent.evolution.production_models import ControlledScenarioAsset


@dataclass(frozen=True, slots=True)
class DynamicBatchJob:
    """
    单次CMO批量推演任务不可变描述对象
    承载一次候选策略推演所需全部路径、标识与校验信息
    """
    campaign_id: str               # 演化任务唯一标识
    generation_index: int          # 当前演化代数
    candidate_id: str              # 候选策略ID
    operation_id: str              # 本次推演操作唯一ID
    attempt_index: int             # 当前重试序号
    scenario_path: Path            # 本地副本想定文件路径
    scenario_checksum: str         # 原始想定SHA256
    lua_path: Path                 # 候选Lua脚本本地副本路径
    lua_checksum: str              # Lua脚本SHA256
    results_dir: Path              # 推演结果输出目录
    job_path: Path                 # BatchRunner任务配置文件路径


class DynamicBatchJobBuilder:
    """
    负责构建单次推演运行环境、复制资源、生成BatchRunner标准任务清单与审计清单
    执行流程：目录初始化→冲突检查→复制想定&Lua脚本→组装任务payload→原子写入配置文件→返回任务实例
    """

    def build(
        self,
        *,
        attempt_dir: Path,
        source_scenario: ControlledScenarioAsset,
        lua_path: Path,
        campaign_id: str,
        generation_index: int,
        candidate_id: str,
        operation_id: str,
        attempt_index: int,
        audit_profile: dict[str, object] | None,
        cmo_executable: Path | None = None,
        wall_timeout_seconds: int = 300,
    ) -> DynamicBatchJob:
        """
        生成单次推演运行环境与Batch任务配置
        :param attempt_dir: 本次尝试独立工作目录
        :param source_scenario: 受控校验过的原始CMO想定资产
        :param lua_path: 候选策略Lua脚本源路径
        :param campaign_id: 演化任务ID
        :param generation_index: 演化代数
        :param candidate_id: 候选ID
        :param operation_id: 推演操作唯一标识
        :param attempt_index: 重试次数索引
        :param audit_profile: 审计指标配置（包含计分单元、作战方信息）
        :param cmo_executable: CMO程序路径
        :param wall_timeout_seconds: 推演最大墙钟超时时间
        :return: 完整推演任务对象 DynamicBatchJob
        :raises ValueError: 工作目录已存在运行时文件，防止覆盖旧任务
        """
        attempt = Path(attempt_dir).resolve()
        attempt.mkdir(parents=True, exist_ok=True)
        # 受保护关键路径清单，存在即判定任务已初始化，禁止重复构建
        protected = (
            attempt / "scenario.scen",
            attempt / "batch-job.json",
            attempt / "attempt-manifest.json",
            attempt / "batch-results",
        )
        if any(path.exists() for path in protected):
            raise ValueError("attempt_runtime_assets_already_exist")

        # 复制原始想定文件到本次推演隔离目录
        source = Path(source_scenario.absolute_path).resolve()
        scenario_copy = attempt / "scenario.scen"
        lua_copy = attempt / "candidate.lua"
        shutil.copy2(source, scenario_copy)

        # 复制候选Lua脚本，源与目标路径不同时才拷贝
        source_lua = Path(lua_path).resolve()
        if source_lua != lua_copy:
            shutil.copy2(source_lua, lua_copy)

        # 创建推演结果输出文件夹
        results = attempt / "batch-results"
        results.mkdir()
        job_path = attempt / "batch-job.json"

        # 组装审计载荷，填充基础溯源字段
        audit_payload = (
            dict(audit_profile)
            if isinstance(audit_profile, dict)
            else {"profile": str(audit_profile or "phase9c")}
        )
        audit_payload.update(
            {
                "profile": str(audit_payload.get("profile", "phase9c")),
                "campaign_id": campaign_id,
                "generation_index": generation_index,
                "candidate_id": candidate_id,
                "operation_id": operation_id,
                "attempt_index": attempt_index,
                "script_checksum": file_sha256(lua_copy),
            }
        )

        # 自动补全Side名称：仅有SideId缺少CmoSideName时进行回填
        sides = audit_payload.get("Sides")
        if isinstance(sides, list):
            for side in sides:
                if not isinstance(side, dict):
                    continue
                if not side.get("CmoSideName") and side.get("SideId"):
                    side["CmoSideName"] = str(side["SideId"])

        # 构造BatchRunner标准执行配置
        payload = {
            "cmoExecutable": (
                str(Path(cmo_executable).resolve())
                if cmo_executable is not None
                else ""
            ),
            "scenario": str(scenario_copy),
            "scenarioChecksum": source_scenario.sha256,
            "outputDirectory": str(results),
            "simulation": {
                "enabled": True,
                "pulseSeconds": 1,
                "stopWhenScenarioEnds": True,
                "wallTimeoutSeconds": int(wall_timeout_seconds),
            },
            "jobs": [
                {
                    "name": operation_id,
                    "script": str(lua_copy),
                    # BatchRunner依靠该列表采集敌方计分目标最终损毁状态；
                    # 数据来源于审计单元映射，不在推演结束后反向重建
                    "metrics": {
                        "expectedDestructionTargets": [
                            str(unit["Name"])
                            for unit in audit_payload.get("Units", [])
                            if isinstance(unit, dict)
                            and unit.get("Name")
                            and str(unit.get("SideId", "")).casefold()
                            != str(audit_payload.get("ScoringSideId", "")).casefold()
                        ]
                    },
                    "auditProfile": audit_payload,
                }
            ],
        }

        # 先写入临时文件，再原子替换，避免配置文件损坏
        temporary = job_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, job_path)

        # 生成任务总清单manifest，附加job路径便于外部检索
        manifest_path = attempt / "attempt-manifest.json"
        manifest = {**payload, "jobPath": str(job_path)}
        temporary = manifest_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, manifest_path)

        return DynamicBatchJob(
            campaign_id=campaign_id,
            generation_index=generation_index,
            candidate_id=candidate_id,
            operation_id=operation_id,
            attempt_index=attempt_index,
            scenario_path=scenario_copy,
            scenario_checksum=source_scenario.sha256,
            lua_path=lua_copy,
            lua_checksum=file_sha256(lua_copy),
            results_dir=results,
            job_path=job_path,
        )

    @staticmethod
    def verify_source_unchanged(asset: ControlledScenarioAsset) -> None:
        """
        兼容占位空方法：原始资产校验仅作为审计元数据，此处暂不执行额外校验逻辑
        """
        return None