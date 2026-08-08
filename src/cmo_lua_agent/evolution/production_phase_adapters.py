"""
Phase7、Phase8 工作流的生产环境薄适配层
作用：把底层的学习、技能演化工作流包装成对外可用的生产接口，
外部业务代码不需要关心内部一堆类如何组装，只需要传入路径 + LLM客户端即可运行。
"""
from __future__ import annotations

from pathlib import Path

# Phase7：对比学习Agent（内部会调用大模型做仿真结果对比分析）
from cmo_lua_agent.agents.comparative_learning_agent import ComparativeLearningAgent
# Phase8：技能编写Agent（内部调用大模型生成/修订战术技能草稿）
from cmo_lua_agent.agents.skill_author_agent import SkillAuthorAgent
# 技能文件存储：负责技能包读写、目录管理
from cmo_lua_agent.learning.skill_evolution.assets import SkillAssetStore
# 技能存储路径配置
from cmo_lua_agent.learning.skill_evolution.config import SkillStorageConfig
# 技能回归校验服务：检查新生成的技能有没有违规、退化
from cmo_lua_agent.learning.skill_evolution.regression import SkillRegressionService
# Phase8完整离线技能演化主工作流
from cmo_lua_agent.learning.skill_evolution.workflow import SkillEvolutionWorkflow
# 经验持久化存储：读写经验记录jsonl文件
from cmo_lua_agent.learning.store import ExperienceStore
# Phase7完整学习主工作流：从仿真结果产出经验候选
from cmo_lua_agent.learning.workflow import GenerationLearningWorkflow


class ProductionPhase7Adapter:
    """
    Phase7 生产适配器
    通俗说：启动Phase7整套对比学习流水线。
    输入：项目根目录 + 大模型json客户端实例
    干的活：
        1.初始化经验存储目录
        2.组装【对比学习Agent(LLM) + 经验存储】，构造Phase7工作流
        3.接收上一层传过来的仿真输出目录，执行学习流程
        4.返回简洁可读的结果给上层调用方，屏蔽内部复杂对象
    """
    def __init__(self, *, project_root: Path, json_client: object) -> None:
        # 初始化经验存储，所有经验数据存在项目根目录下 data/experiences
        self._store = ExperienceStore(Path(project_root) / "data" / "experiences")
        # 实例化Phase7学习工作流：注入大模型客户端、经验存储器
        self._workflow = GenerationLearningWorkflow(
            agent=ComparativeLearningAgent(json_client),
            store=self._store,
        )

    @property
    def experience_store(self) -> ExperienceStore:
        """对外暴露经验存储对象，给后面Phase8复用，不用重复初始化"""
        return self._store

    def run(
        self,
        *,
        generation_index: int,          # 当前是第几轮优化迭代
        optimization_dir: Path,         # Phase6仿真输出目录，里面是各个candidate结果
        outcomes: tuple[dict[str, object], ...],
    ) -> dict[str, object]:
        """
        执行Phase7主逻辑
        输入：仿真轮次、仿真结果目录
        输出：普通字典（方便序列化打印、存日志，不返回内部复杂dataclass对象）
        """
        # 运行Phase7：读取仿真产物，清洗事实，调用LLM对比分析，生成经验候选记录
        bundle, experiences = self._workflow.run(Path(optimization_dir))
        # 把内部对象提取关键字段，包装成简单字典对外返回
        return {
            "status": "completed",
            "generation_index": generation_index,
            "optimization_id": bundle.optimization_id,
            "experience_candidate_count": len(experiences), # 本轮产出多少条经验
            "experience_ids": [item.experience_id for item in experiences], #经验id列表
            "learning_dir": str(Path(optimization_dir) / "learning"), #产出文件存放路径
        }


class ProductionPhase8Adapter:
    """
    Phase8生产适配器
    通俗说：执行技能演化流水线，基于Phase7产出的经验，生成战术技能草稿
    依赖Phase7运行完成，复用Phase7的经验存储，避免重复加载数据
    """
    def __init__(
        self,
        *,
        project_root: Path,
        json_client: object,                # 同一个大模型客户端实例
        experience_store: ExperienceStore, # 直接复用Phase7已经建好的经验存储
    ) -> None:
        self._root = Path(project_root).resolve()
        # 复用Phase7的经验存储器，读取Phase7生成的经验记录
        self._experience_store = experience_store
        # 组装Phase8完整工作流
        self._workflow = SkillEvolutionWorkflow(
            # 注入技能编写Agent，内部会调用LLM，基于经验写战术Skill草稿
            author_agent=SkillAuthorAgent(json_client),
            # 技能包的存储实例，读取/写入技能文件到生产目录
            asset_store=SkillAssetStore(
                SkillStorageConfig.production(self._root)
            ),
            # 技能回归校验服务；这里lambda是临时占位实现，生产要替换真实校验逻辑
            regression_service=SkillRegressionService(
                proposal_validator=lambda _package: True
            ),
        )

    def run(
        self,
        *,
        generation_index: int,
        phase7_result: dict[str, object], # 直接接收Phase7Adapter.run返回的字典结果
    ) -> dict[str, object]:
        """执行Phase8技能演化"""
        # 从phase7输出结果拿到本次优化任务id
        optimization_id = str(phase7_result["optimization_id"])
        # 跑Phase8工作流：读取经验、聚合证据、阈值判断、调用LLM生成技能草稿
        result = self._workflow.run(
            phase8_run_id=f"{optimization_id}_phase8",
            runs_root=self._root / "runs" / "evolution",
            experience_store=self._experience_store,
        )
        # 将内部dataclass转为字典返回，供上层保存日志
        return result.to_dict()

    def run_for_training(
        self,
        *,
        workflow_id: str,
        experience_ids: tuple[str, ...],
    ) -> dict[str, object]:
        """Aggregate only the experiences produced by one completed workflow."""
        result = self._workflow.run(
            phase8_run_id=f"{workflow_id}_phase8",
            runs_root=self._root / "runs" / "evolution",
            experience_store=self._experience_store,
            experience_ids=experience_ids,
        )
        return result.to_dict()
