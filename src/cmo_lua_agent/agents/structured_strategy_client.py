"""受限 JSON LLM 边界，不向模型暴露执行或评分能力。
协议+封装类，统一约束大模型输出为标准JSON；
强制限制LLM不可修改场景事实、CMO执行逻辑、计分插桩、运行时工具、Lua代码，
只允许输出完整策略结构 / 受限替换补丁，隔离底层确定性管线，防止模型篡改核心系统逻辑。
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


# 底层统一结构化输出客户端协议（接口规范）
class StructuredJsonClient(Protocol):
    def complete_json(self, *, system: str, prompt: str) -> object:
        """
        协议规范：所有LLM底层客户端必须实现该方法
        :param system: 系统提示词（约束模型行为、输出格式）
        :param prompt: 用户/业务上下文输入
        :return: 纯JSON可序列化对象（dict/list）
        """
        ...


# 上层策略专用结构化客户端，封装统一系统约束提示
class StructuredStrategyClient:
    """把底层 JSON 客户端适配为策略 Agent 使用的受限结构化调用接口。"""
    def __init__(self, client: StructuredJsonClient) -> None:
        # 注入实现了结构化输出协议的底层LLM客户端
        self._client = client

    def complete(self, *, mode: str, prompt: str) -> dict[str, Any]:
        """
        对外统一调用入口
        :param mode: 模式标识：create / revise / strategy_patch（区分新建/修订/修复补丁）
        :param prompt: 业务上下文、错误信息、策略原文等输入内容
        :return: LLM返回的标准字典结果
        """
        # 调用底层结构化LLM接口，传入强约束系统提示词
        response = self._client.complete_json(
            system=(
                "仅返回一个严格JSON对象。你只允许输出标准StrategySpec完整结构 或 受限替换补丁。"
                "场景事实、CMO执行逻辑、受保护计分插桩、运行时工具、Lua代码均不可编辑、不可修改。"
            ),
            prompt=f"mode={mode}\n{prompt}",
        )
        # 强制校验：模型返回必须是字典，禁止数组/自由文本/纯字符串
        if not isinstance(response, Mapping):
            raise ValueError("结构化代理返回结果必须是JSON对象")
        return dict(response)
