"""
加载并生成校验指纹：限定范围的6v4作战推演任务输入资源包
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

# 项目内部契约、基线策略、想定定义加载接口
from cmo_lua_agent.contract import load_baseline_strategy, load_scenario_definition
# Lua运行时配置模型
from cmo_lua_agent.generation.runtime_models import LuaRuntimeProfile
# 计分渲染器版本常量
from cmo_lua_agent.generation.scored_lua_assembly import SCORED_RENDERER_VERSION
# 基线评分编译工具
from cmo_lua_agent.scoring.baseline import compile_score_baseline


@dataclass(frozen=True, slots=True)
class CampaignInputBundle:
    """
    6v4推演任务输入资源包
    frozen=True：实例不可变；slots=True：优化内存、禁止动态新增属性
    承载一次完整推演任务所需全部原始输入、配置、基线资源与完整性哈希指纹
    """
    project_root: Path               # 项目根目录绝对路径
    baseline_root: Path              # 6v4基线资源根目录
    scenario_path: Path              # 作战想定定义文件路径
    baseline_strategy_path: Path     # 基线参照策略文件路径
    job_config_path: Path            # 当前推演任务运行配置文件路径
    bootstrap_skill_path: Path       # 策略生成引导Prompt/技能文档路径
    scenario: object                 # 解析完成的作战想定对象（ScenarioDefinition）
    baseline: object                 # 解析完成的基线策略对象（BaselineStrategy）
    runtime: LuaRuntimeProfile       # Lua脚本运行时环境描述信息
    score_compilation: object        # 编译后的评分规则包（包含评分片段、评分规约）
    checksums: dict[str, str]        # 全资源SHA256校验指纹清单，用于防篡改、复现校验


class CampaignInputLoader:
    """
    6v4任务专属资源加载器
    仅加载项目内预先声明的6v4配套资源，同时完成文件存在性、路径合法性、哈希校验
    强约束：不允许随意加载外部文件，保障推演实验可复现性
    """

    def load_6v4(self, *, project_root: Path, job_config_path: Path) -> CampaignInputBundle:
        """
        加载标准6v4作战推演全套输入资源，组装成资源包Bundle并生成完整性指纹
        :param project_root: 项目根目录路径
        :param job_config_path: 当前推演任务配置文件路径
        :return: 封装完成的CampaignInputBundle资源包
        :raises ValueError: 文件不存在 / 文件路径超出项目根目录（防止路径穿越）
        """
        # 转为绝对路径，消除相对路径歧义
        root = Path(project_root).resolve()
        baseline_root = root / "baseline" / "6v4"

        # 固定绑定6v4基线配套文件
        scenario_path = baseline_root / "scenario_definition.json"
        strategy_path = baseline_root / "baseline_strategy.json"
        bootstrap_path = root / "src" / "cmo_lua_agent" / "skills" / "bootstrap" / "cmo_naval_air_strategy_proposal_v1.md"
        job_config_path = Path(job_config_path).resolve()

        # 合法性校验：文件必须存在，且不能脱离项目根目录（防御路径穿越）
        for path in (scenario_path, strategy_path, bootstrap_path, job_config_path):
            if not path.is_file() or not path.is_relative_to(root):
                raise ValueError("campaign_input_path_invalid")

        # 反序列化：加载作战想定、基线参照策略
        scenario = load_scenario_definition(scenario_path)
        baseline = load_baseline_strategy(strategy_path)

        # 编译基线评分规则，得到评分规约与评分片段
        compilation = compile_score_baseline(baseline_root).compilation

        # 初始化本次推演使用的Lua运行时标识（推演模板ID + 版本号）
        runtime = LuaRuntimeProfile("cmo_naval_air_anti_surface_scored", "2.0.0")

        # 构建全套资源指纹清单
        checksums = {
            "scenario": self._sha(scenario_path),          # 想定文件哈希
            "baseline": self._sha(strategy_path),           # 基线策略哈希
            "bootstrap": self._sha(bootstrap_path),         # 引导技能文档哈希
            "job_config": self._sha(job_config_path),       # 任务配置哈希
            "score_fragment": compilation.fragment_checksum, # 评分片段哈希
            "score_spec": compilation.score_spec_checksum,   # 评分规约哈希
            "runtime": f"{runtime.runtime_id}:{runtime.runtime_version}", # 运行时标识串
            "renderer": SCORED_RENDERER_VERSION,            # 计分渲染器版本
        }

        # 组装并返回不可变资源包
        return CampaignInputBundle(
            root, baseline_root, scenario_path, strategy_path, job_config_path, bootstrap_path,
            scenario, baseline, runtime, compilation, checksums
        )

    @staticmethod
    def _sha(path: Path) -> str:
        """
        静态工具：计算单个文件SHA256摘要十六进制字符串
        :param path: 目标文件路径
        :return: sha256 hexdigest
        """
        return sha256(path.read_bytes()).hexdigest()