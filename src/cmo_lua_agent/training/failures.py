"""在决定是否适合自动修复代码前，对 Workflow 失败进行分类。

分类结果驱动 Training Runner 的重试、停止或源码修复分流；证据不足时保守地交由
人工处理，避免把场景、模型或基础设施故障误改为 Python 源码问题。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json


class FailureKind(str, Enum):
    TRANSIENT = "TRANSIENT"
    BUSINESS = "BUSINESS"
    INPUT = "INPUT"
    CODE = "CODE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class FailureRecord:
    kind: FailureKind
    error_type: str
    message: str


class FailureClassifier:
    """使用确定性的异常与消息证据；无法确认的错误保持不可自动修复。"""

    def classify(self, error: BaseException) -> FailureRecord:
        message = str(error)
        lowered = message.lower()
        if isinstance(error, (TimeoutError, ConnectionError)) or type(error).__name__ in {
            "APIConnectionError",
            "APITimeoutError",
        } or any(
            marker in lowered for marker in ("timeout", "connection error", "connection reset", "temporarily unavailable")
        ):
            kind = FailureKind.TRANSIENT
        elif isinstance(error, PermissionError) and ("\\workers\\" in lowered or "/workers/" in lowered):
            # Worker 状态由独立进程原子替换。Windows 上读取方可能短暂输掉文件
            # 替换竞争；重试已持久化的操作，避免把已完成结果误判为无效输入。
            kind = FailureKind.TRANSIENT
        elif isinstance(error, (FileNotFoundError, json.JSONDecodeError)) or any(
            marker in lowered for marker in ("scenario", "json", "input path", "not found")
        ):
            kind = FailureKind.INPUT
        elif isinstance(error, (ImportError, ModuleNotFoundError, SyntaxError, AssertionError)) or any(
            marker in lowered for marker in ("traceback", "state-machine", "attributeerror", "typeerror")
        ):
            kind = FailureKind.CODE
        elif any(marker in lowered for marker in ("candidate", "semantic", "score", "validation")):
            kind = FailureKind.BUSINESS
        else:
            kind = FailureKind.UNKNOWN
        return FailureRecord(kind=kind, error_type=type(error).__name__, message=message)
