"""
Phase 9C 生产环境契约定义，提供确定性序列化与完整性校验
核心目的：Campaign（大迭代任务）层面做防篡改、不可变数据契约；
所有结构体均为 frozen 不可变dataclass，配合标准化sha256哈希校验，
用于管控候选集提交、人工执行授权、想定文件校验、执行配额消耗、基准失败档案。
一旦JSON磁盘加载回来，会重新计算哈希，如果和存储的checksum对不上，直接抛异常，防止数据被篡改。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping


def canonical_json(value: object) -> str:
    """
    生成标准化JSON字符串（确定性序列化）
    sort_keys=True保证字典key顺序固定；separators取消多余空格；ensure_ascii=False保留中文
    同一个对象永远输出完全一样的字符串，用来算checksum，避免格式差异导致哈希不一致
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def canonical_checksum(value: object) -> str:
    """基于标准化JSON，计算sha256校验和，用于防篡改、数据指纹"""
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class FrozenCandidateSet:
    """
    冻结候选策略集合【Phase9C核心契约】
    把一轮Campaign的基准策略baseline + 4份候选candidate完整打包并上锁冻结。
    一旦创建完成，对象不可修改；保存到磁盘再读回会强制校验全部checksum。
    只有本对象标记 production_execution_eligible=True，才允许交给CMO批量执行器跑仿真。
    """
    campaign_id: str                          # 所属大任务（Campaign）唯一ID
    generation_index: int                     # 当前是第几轮生成迭代
    preview_revision: int                     # 预览修订版本号，用于多轮预览修改
    baseline: Mapping[str, Any]                # 基准策略原始数据
    baseline_checksum: str                    # 基准策略指纹哈希
    candidates: tuple[Mapping[str, Any], ...]  # 4份候选策略完整数据
    candidate_checksums: tuple[str, ...]       # 每一个候选策略对应的指纹哈希
    candidate_set_checksum: str               # 整套候选集整体指纹（身份哈希）
    source_proposal_operation_id: str         # 生成这组候选的上游操作ID，链路溯源
    scenario_ir_checksum: str | None = None           # 想定中间表示IR哈希
    derived_baseline_checksum: str | None = None       # 派生基准的哈希
    proposal_context_checksum: str | None = None       # 提案上下文快照哈希
    knowledge_snapshot_checksum: str | None = None    # 当时使用的Skill知识快照哈希
    candidate_quality_report_checksum: str | None = None # 候选质量检测报告哈希
    candidate_quality_index_checksum: str | None = None
    proposal_provider: str = "unknown"                # 候选是谁生成的（LLM/人工）
    production_execution_eligible: bool = False        # 是否允许正式环境执行CMO仿真

    @classmethod
    def create(
        cls,
        *,
        campaign_id: str,
        generation_index: int,
        preview_revision: int,
        baseline: Mapping[str, Any],
        candidates: tuple[Mapping[str, Any], ...],
        source_proposal_operation_id: str,
        scenario_ir_checksum: str | None = None,
        derived_baseline_checksum: str | None = None,
        proposal_context_checksum: str | None = None,
        knowledge_snapshot_checksum: str | None = None,
        candidate_quality_report_checksum: str | None = None,
        candidate_quality_index_checksum: str | None = None,
        proposal_provider: str = "unknown",
        production_execution_eligible: bool = False,
    ) -> "FrozenCandidateSet":
        """
        工厂方法：构造冻结候选集对象
        1.做标准化归一，消除字典顺序差异
        2.强制校验候选ID必须为 candidate_00、candidate_01、candidate_02、candidate_03
        3.分别计算基准、每个候选、整套集合的checksum
        """
        baseline_value = json.loads(canonical_json(dict(baseline)))
        candidate_values = tuple(json.loads(canonical_json(dict(item))) for item in candidates)
        # 强制校验候选ID命名规则，必须连续00~03
        ids = [item.get("candidate_id") for item in candidate_values]
        if ids != [f"candidate_{index:02d}" for index in range(4)]:
            raise ValueError("frozen_candidate_ids_invalid")
        # 计算基准策略哈希
        baseline_checksum = canonical_checksum(baseline_value)
        # 逐个计算每个候选策略的哈希，取strategy字段做指纹
        candidate_checksums = tuple(
            canonical_checksum(item["strategy"]) for item in candidate_values
        )
        # 组装身份结构体，计算整套候选集总checksum
        identity = {
            "campaign_id": campaign_id,
            "generation_index": generation_index,
            "preview_revision": preview_revision,
            "baseline_checksum": baseline_checksum,
            "candidate_ids": ids,
            "candidate_checksums": list(candidate_checksums),
            "source_proposal_operation_id": source_proposal_operation_id,
            "scenario_ir_checksum": scenario_ir_checksum,
            "derived_baseline_checksum": derived_baseline_checksum,
            "proposal_context_checksum": proposal_context_checksum,
            "knowledge_snapshot_checksum": knowledge_snapshot_checksum,
            "candidate_quality_report_checksum": candidate_quality_report_checksum,
            "proposal_provider": proposal_provider,
            "production_execution_eligible": production_execution_eligible,
        }
        if candidate_quality_index_checksum is not None:
            identity["candidate_quality_index_checksum"] = candidate_quality_index_checksum
        return cls(
            campaign_id=campaign_id,
            generation_index=generation_index,
            preview_revision=preview_revision,
            baseline=baseline_value,
            baseline_checksum=baseline_checksum,
            candidates=candidate_values,
            candidate_checksums=candidate_checksums,
            candidate_set_checksum=canonical_checksum(identity),
            source_proposal_operation_id=source_proposal_operation_id,
            scenario_ir_checksum=scenario_ir_checksum,
            derived_baseline_checksum=derived_baseline_checksum,
            proposal_context_checksum=proposal_context_checksum,
            knowledge_snapshot_checksum=knowledge_snapshot_checksum,
            candidate_quality_report_checksum=candidate_quality_report_checksum,
            candidate_quality_index_checksum=candidate_quality_index_checksum,
            proposal_provider=proposal_provider,
            production_execution_eligible=production_execution_eligible,
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为普通字典，用于保存JSON文件"""
        return {
            "campaign_id": self.campaign_id,
            "generation_index": self.generation_index,
            "preview_revision": self.preview_revision,
            "baseline": dict(self.baseline),
            "baseline_checksum": self.baseline_checksum,
            "candidates": [dict(item) for item in self.candidates],
            "candidate_checksums": list(self.candidate_checksums),
            "candidate_set_checksum": self.candidate_set_checksum,
            "source_proposal_operation_id": self.source_proposal_operation_id,
            "scenario_ir_checksum": self.scenario_ir_checksum,
            "derived_baseline_checksum": self.derived_baseline_checksum,
            "proposal_context_checksum": self.proposal_context_checksum,
            "knowledge_snapshot_checksum": self.knowledge_snapshot_checksum,
            "candidate_quality_report_checksum": self.candidate_quality_report_checksum,
            "candidate_quality_index_checksum": self.candidate_quality_index_checksum,
            "proposal_provider": self.proposal_provider,
            "production_execution_eligible": self.production_execution_eligible,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        *,
        verify_checksums: bool = True,
    ) -> "FrozenCandidateSet":
        """
        从磁盘JSON反序列化加载
        重建对象之后，**重新计算全部哈希，和文件内存储的哈希比对**
        一旦任何checksum不一致，直接抛异常，检测文件被篡改
        """
        candidate = cls.create(
            campaign_id=str(value["campaign_id"]),
            generation_index=int(value["generation_index"]),
            preview_revision=int(value["preview_revision"]),
            baseline=dict(value["baseline"]),
            candidates=tuple(dict(item) for item in value["candidates"]),
            source_proposal_operation_id=str(value["source_proposal_operation_id"]),
            scenario_ir_checksum=value.get("scenario_ir_checksum"),
            derived_baseline_checksum=value.get("derived_baseline_checksum"),
            proposal_context_checksum=value.get("proposal_context_checksum"),
            knowledge_snapshot_checksum=value.get("knowledge_snapshot_checksum"),
            candidate_quality_report_checksum=value.get("candidate_quality_report_checksum"),
            candidate_quality_index_checksum=value.get("candidate_quality_index_checksum"),
            proposal_provider=str(value.get("proposal_provider", "unknown")),
            production_execution_eligible=bool(value.get("production_execution_eligible", False)),
        )
        # 三重校验：基准哈希、候选数组哈希、整套集合哈希全部核对
        if verify_checksums:
            if candidate.baseline_checksum != value.get("baseline_checksum"):
                raise ValueError("frozen_baseline_checksum_mismatch")
            if tuple(value.get("candidate_checksums", ())) != candidate.candidate_checksums:
                raise ValueError("frozen_candidate_checksum_mismatch")
            if candidate.candidate_set_checksum != value.get("candidate_set_checksum"):
                raise ValueError("frozen_candidate_set_checksum_mismatch")
        return candidate


@dataclass(frozen=True, slots=True)
class GenerationApprovalGrant:
    """
    执行授权凭证（权限契约）
    人工/系统签发一张“许可票据”：允许执行本轮Campaign的CMO仿真，
    包含最大尝试次数、允许哪些operation_id运行、签发人、过期时间；
    票据自带checksum防篡改；没有这个Grant，BatchRunner拒绝启动仿真。
    """
    approval_id: str                     # 授权票据ID，由checksum截断生成
    campaign_id: str                     # 所属大任务ID
    generation_index: int                # 对应迭代轮次
    preview_revision: int                # 预览修订号
    snapshot_checksum: str               # 关联快照哈希
    candidate_set_checksum: str          # 绑定被授权的那一套冻结候选集指纹
    baseline_checksum: str               # 绑定基准策略哈希
    contract_checksum: str              # 契约本身哈希
    budget_revision: int                # 资源预算版本
    approved_operation_ids: tuple[str, ...] # 允许运行的操作ID列表
    maximum_cmo_attempts: int            # 本轮最多允许跑多少次CMO仿真尝试
    actor: str                           # 签发人账号
    actor_source: str                    # 身份来源：本地操作系统用户
    identity_strength: str              # 身份可信度标记
    hostname: str                        # 签发时机器主机名
    process_id: int                     # 签发进程PID
    approved_at: str                    # 签发时间ISO字符串
    expires_at: str                     # 授权过期时间
    receipt_checksum: str               # 回执哈希
    checksum: str                       # 本授权凭证整体指纹
    valid: bool = True                  # 凭证是否有效

    @classmethod
    def issue(cls, **values: Any) -> "GenerationApprovalGrant":
        """工厂：签发一张新的执行授权，自动计算checksum，生成approval_id"""
        body = {
            **values,
            "approved_operation_ids": list(values["approved_operation_ids"]),
            "actor_source": "local_os_user",
            "identity_strength": "local_os_attribution",
        }
        checksum = canonical_checksum(body)
        approval_id = f"approval_{checksum[:24]}"
        return cls(
            approval_id=approval_id,
            checksum=checksum,
            actor_source="local_os_user",
            identity_strength="local_os_attribution",
            **values,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GenerationApprovalGrant":
        """加载磁盘上的授权凭证，重新校验checksum，防止被篡改"""
        data = dict(value)
        data["approved_operation_ids"] = tuple(data["approved_operation_ids"])
        grant = cls(**data)
        body = grant.to_dict()
        expected_id = body.pop("approval_id")
        expected_checksum = body.pop("checksum")
        body.pop("valid", None)
        # 重新计算哈希和ID，与存储内容比对
        if canonical_checksum(body) != expected_checksum or expected_id != f"approval_{expected_checksum[:24]}":
            raise ValueError("generation_approval_checksum_mismatch")
        return grant


@dataclass(frozen=True, slots=True)
class ControlledScenarioAsset:
    """受管控的CMO想定资源元信息
    记录想定文件路径、大小、sha256；标记初始环境是否干净无修改。
    仿真前必须核对，防止想定文件被人为改动。
    """
    asset_id: str
    scenario_id: str
    absolute_path: str               # 文件绝对路径
    sha256: str                      # 文件哈希
    size_bytes: int                  # 文件字节大小
    verification_record_path: str    # 对应的校验记录文件路径
    verified_clean_initial_state: bool # 是否确认是干净原始初始状态

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScenarioAssetVerificationRecord:
    """
    想定文件校验审计记录
    每次仿真启动前，对CMO想定文件做完整性扫描，生成这条审计日志；
    记录：文件哈希、修改时间、校验人、主机进程；自带record_checksum防篡改。
    """
    schema_version: str
    asset_id: str
    scenario_id: str
    absolute_path: str
    sha256: str
    size_bytes: int
    modified_time_ns: int          # 文件修改时间（纳秒时间戳）
    verified_clean_initial_state: bool # 是否干净初始状态
    actor: str                     # 执行校验的用户
    actor_source: str
    identity_strength: str
    hostname: str
    process_id: int
    verified_at: str               # 校验完成时间
    record_checksum: str           # 本审计记录自身哈希

    @classmethod
    def create(cls,** values: Any) -> "ScenarioAssetVerificationRecord":
        body = {
            "schema_version": "1.0",
            **values,
            "actor_source": "local_os_user",
            "identity_strength": "local_os_attribution",
        }
        return cls(**body, record_checksum=canonical_checksum(body))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any]
    ) -> "ScenarioAssetVerificationRecord":
        """加载校验记录，校验记录本身是否被篡改"""
        record = cls(**dict(value))
        body = record.to_dict()
        checksum = body.pop("record_checksum")
        if canonical_checksum(body) != checksum:
            raise ValueError("scenario_asset_verification_record_invalid")
        return record


@dataclass(frozen=True, slots=True)
class AttemptSlot:
    """执行槽位：跟踪单次CMO仿真尝试的状态
    operation_id + candidate_id + attempt_index定位一次运行；remaining属性快速判断是否还可以执行
    """
    operation_id: str
    candidate_id: str
    attempt_index: int
    status: str   # "available"/占用/失败等状态

    @property
    def remaining(self) -> bool:
        """True = 该槽位还空闲，可以发起仿真尝试"""
        return self.status == "available"


@dataclass(frozen=True, slots=True)
class GenerationApprovalUsage:
    """授权票据的消耗统计
    跟踪一张授权已经跑了多少个CMO任务，计算剩余还能跑多少次仿真配额，用于限流。
    """
    approval_id: str
    maximum_cmo_attempts: int                     # 总允许最大次数
    consumed_operation_ids: tuple[str, ...] = ()   # 已经消耗掉的operation_id

    @property
    def remaining_cmo_attempts(self) -> int:
        """剩余可执行CMO尝试次数，最小为0"""
        return max(
            0,
            self.maximum_cmo_attempts - len(self.consumed_operation_ids),
        )


@dataclass(frozen=True, slots=True)
class BaselineFailureProfile:
    """
    基准策略失败档案
    当baseline基准策略跑崩（执行失败、语义漂移、分数异常），生成这份档案归档。
    记录分数、语义是否合法、执行保真度、异常指标、偏差详情、全部源文件哈希；带checksum锁。
    """
    schema_version: str
    run_id: str                                 # 本次运行ID
    official_score: int | float                 # CMO官方得分
    semantic_valid: bool                        # 是否通过Phase3语义校验
    execution_fidelity: str                     # 执行保真等级
    failure_indicators: tuple[str, ...]         # 失败标签集合（例如semantic_drift）
    deviations: tuple[Mapping[str, Any], ...]   # 执行与预期发生偏差的详情列表
    source_checksums: Mapping[str, str]         # 相关输入文件哈希快照
    checksum: str                               # 档案整体指纹

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        official_score: int | float,
        semantic_valid: bool,
        execution_fidelity: str,
        failure_indicators: tuple[str, ...],
        deviations: tuple[Mapping[str, Any], ...],
        source_checksums: Mapping[str, str],
    ) -> "BaselineFailureProfile":
        """工厂构建失败档案，做数据归一并计算checksum"""
        body = {
            "schema_version": "1.0",
            "run_id": run_id,
            "official_score": official_score,
            "semantic_valid": semantic_valid,
            "execution_fidelity": execution_fidelity,
            "failure_indicators": list(failure_indicators),
            "deviations": [dict(item) for item in deviations],
            "source_checksums": dict(source_checksums),
        }
        return cls(
            schema_version="1.0",
            run_id=run_id,
            official_score=official_score,
            semantic_valid=semantic_valid,
            execution_fidelity=execution_fidelity,
            failure_indicators=failure_indicators,
            deviations=tuple(
                json.loads(canonical_json(dict(item))) for item in deviations
            ),
            source_checksums=json.loads(canonical_json(dict(source_checksums))),
            checksum=canonical_checksum(body),
        )
