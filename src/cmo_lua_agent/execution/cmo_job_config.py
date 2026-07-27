"""
CMO 批量任务 JSON 配置管理。

该模块负责在执行单个 Lua 脚本前：

1. 读取 CmoBatchRunner 的 JSON 配置；
2. 保存 jobs[job_index].script 的原始值；
3. 将 script 临时切换为当前待执行 Lua；
4. 对写入结果进行回读校验；
5. 无论外层执行成功或异常，都恢复运行前的 script；
6. 使用同目录临时文件和原子替换，降低 JSON 损坏风险。

当前 MVP 约束：

- 单进程；
- 单实例；
- 单 Lua；
- 串行执行；
- 暂不支持多个 Python 进程并发修改同一配置文件。

本模块不启动 CMO，不清理进程，也不解析控制台错误。

流程：
    读配置里原本写死的 Lua 路径（比如base.lua）
    临时改成第 1 个待测试 Lua：test1.lua
    启动 CMO 运行脚本
    跑完强制改回原来的base.lua，再循环下一个脚本
"""

from __future__ import annotations

import json
from copy import deepcopy
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


class CmoJobConfigError(RuntimeError):
    """
    CMO 任务配置读取、校验或写入失败。
    """


class CmoJobConfigRestoreError(
    CmoJobConfigError
):
    """
    CMO 执行结束后恢复原始 script 失败。

    该错误意味着配置文件可能处于脏状态，
    后续任务不应继续自动执行。
    """


@dataclass
class CmoJobConfigSession:
    """
    一次临时配置切换会话。

    Attributes:
        job_index:
            当前修改的 jobs 数组下标。

        original_script:
            进入上下文前的 script 原始字符串。

        active_script:
            当前执行 Lua 的绝对路径字符串。

        restore_succeeded:
            离开上下文后是否成功恢复。

        restore_error:
            恢复失败时的错误摘要。
    """

    job_index: int
    original_script: str
    active_script: str

    restore_succeeded: bool = False
    restore_error: str | None = None


class CmoJobConfig:
    """
    CmoBatchRunner JSON 任务配置管理器。

    推荐使用 use_script() 上下文管理器：

        config = CmoJobConfig(config_path)

        with config.use_script(
            lua_path=lua_path,
            job_index=0,
        ):
            run_cmo()

    离开 with 块时，无论 run_cmo() 是否抛出异常，
    都会尝试恢复执行前的 script 原值。
    """

    def __init__(
        self,
        config_path: Path,
    ) -> None:
        """
        初始化配置管理器。

        Args:
            config_path:
                CmoBatchRunner 任务 JSON 文件路径。
        """
        self._config_path = Path(
            config_path
        )

    @property
    def config_path(self) -> Path:
        """
        返回任务 JSON 文件路径。
        """
        return self._config_path

    def get_script(
        self,
        job_index: int = 0,
    ) -> str:
        """
        读取指定任务当前配置的 script。

        Args:
            job_index:
                jobs 数组下标。

        Returns:
            script 字段的原始字符串。
        """
        config = self._load_config()

        job = self._get_job(
            config=config,
            job_index=job_index,
        )

        script = job.get("script")

        if (
            not isinstance(script, str)
            or not script.strip()
        ):
            raise CmoJobConfigError(
                f"jobs[{job_index}].script "
                "必须是非空字符串"
            )

        return script

    @contextmanager
    def use_script(
        self,
        *,
        lua_path: Path,
        job_index: int = 0,
        audit_profile: dict[str, Any] | None = None,
    ) -> Iterator[CmoJobConfigSession]:
        """
        临时切换指定任务的 Lua 脚本。

        执行过程：

            校验 Lua
            → 读取原 script
            → 写入当前 Lua
            → yield 给外层执行 CMO
            → finally 恢复原 script

        Args:
            lua_path:
                本轮待执行的 Lua 文件。

            job_index:
                需要修改的 jobs 数组下标。

        Yields:
            CmoJobConfigSession。

        Raises:
            FileNotFoundError:
                Lua 或配置文件不存在。

            CmoJobConfigError:
                JSON 格式、jobs 结构或 script 字段非法。

            IndexError:
                job_index 越界。

            CmoJobConfigRestoreError:
                离开上下文时恢复配置失败。
        """
        normalized_lua_path = Path(
            lua_path
        )

        if not normalized_lua_path.is_file():
            raise FileNotFoundError(
                "Lua 文件不存在："
                f"{normalized_lua_path}"
            )

        active_script = str(
            normalized_lua_path.resolve()
        )

        original_script = self.get_script(
            job_index=job_index
        )
        original_job = self._get_job(config=self._load_config(), job_index=job_index)
        original_audit_profile = deepcopy(original_job.get("auditProfile"))

        # 只有前置校验全部通过后才开始修改配置。
        self._set_script(
            job_index=job_index,
            script_value=active_script,
        )
        if audit_profile is not None:
            self._set_audit_profile(job_index=job_index, value=audit_profile)

        session = CmoJobConfigSession(
            job_index=job_index,
            original_script=original_script,
            active_script=active_script,
        )

        try:
            yield session

        finally:
            try:
                # 恢复时重新读取当前配置，只恢复 script，
                # 不覆盖 CMO 运行期间可能写入的其他字段。
                self._set_script(
                    job_index=job_index,
                    script_value=(
                        original_script
                    ),
                )
                self._set_audit_profile(job_index=job_index, value=original_audit_profile)

            except Exception as exc:
                session.restore_error = (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                raise CmoJobConfigRestoreError(
                    "无法恢复 CMO 任务配置："
                    f"jobs[{job_index}].script "
                    f"应恢复为 {original_script!r}"
                ) from exc

            else:
                session.restore_succeeded = True
                session.restore_error = None

    def _load_config(
        self,
    ) -> dict[str, Any]:
        """
        读取并解析任务 JSON。
        """
        if not self._config_path.is_file():
            raise FileNotFoundError(
                "CMO 任务配置文件不存在："
                f"{self._config_path}"
            )

        try:
            raw_text = (
                self._config_path.read_text(
                    encoding="utf-8-sig",
                    errors="strict",
                )
            )

            config = json.loads(
                raw_text
            )

        except json.JSONDecodeError as exc:
            raise CmoJobConfigError(
                "CMO 任务配置 JSON 格式错误："
                f"{self._config_path}，"
                f"第 {exc.lineno} 行，"
                f"第 {exc.colno} 列"
            ) from exc

        except UnicodeError as exc:
            raise CmoJobConfigError(
                "CMO 任务配置文件编码错误："
                f"{self._config_path}"
            ) from exc

        if not isinstance(config, dict):
            raise CmoJobConfigError(
                "CMO 任务配置根节点必须是对象"
            )

        return config

    @staticmethod
    def _get_job(
        *,
        config: dict[str, Any],
        job_index: int,
    ) -> dict[str, Any]:
        """
        校验并返回 jobs[job_index]。
        """
        if (
            isinstance(job_index, bool)
            or not isinstance(
                job_index,
                int,
            )
        ):
            raise TypeError(
                "job_index 必须是整数"
            )

        if job_index < 0:
            raise IndexError(
                f"job_index={job_index} "
                "不能小于 0"
            )

        jobs = config.get("jobs")

        if not isinstance(jobs, list):
            raise CmoJobConfigError(
                "CMO 任务配置中的 jobs "
                "必须是数组"
            )

        if job_index >= len(jobs):
            raise IndexError(
                f"job_index={job_index} "
                "超出范围，"
                f"当前共有 {len(jobs)} 个 job"
            )

        job = jobs[job_index]

        if not isinstance(job, dict):
            raise CmoJobConfigError(
                f"jobs[{job_index}] "
                "必须是对象"
            )

        return job

    def _set_script(
        self,
        *,
        job_index: int,
        script_value: str,
    ) -> None:
        """
        修改指定 job 的 script 并回读校验。

        每次调用都会重新读取当前配置，
        因而恢复操作不会覆盖其他字段的最新值。
        """
        if (
            not isinstance(
                script_value,
                str,
            )
            or not script_value.strip()
        ):
            raise CmoJobConfigError(
                "script_value 必须是非空字符串"
            )

        config = self._load_config()

        job = self._get_job(
            config=config,
            job_index=job_index,
        )

        job["script"] = script_value

        self._atomic_write(
            config
        )

        # 写入后回读验证。
        saved_config = self._load_config()

        saved_job = self._get_job(
            config=saved_config,
            job_index=job_index,
        )

        saved_script = saved_job.get(
            "script"
        )

        if saved_script != script_value:
            raise CmoJobConfigError(
                "CMO 任务配置写入验证失败："
                f"期望 {script_value!r}，"
                f"实际 {saved_script!r}"
            )

    def _set_audit_profile(self, *, job_index: int, value: dict[str, Any] | None) -> None:
        config = self._load_config()
        job = self._get_job(config=config, job_index=job_index)
        if value is None:
            job.pop("auditProfile", None)
        else:
            job["auditProfile"] = deepcopy(value)
        self._atomic_write(config)

    def _atomic_write(
        self,
        config: dict[str, Any],
    ) -> None:
        """
        通过同目录临时文件原子替换 JSON。

        临时文件与目标文件位于同一目录，
        以提高 Windows 下 replace 的可靠性。
        """
        parent = (
            self._config_path.parent
        )

        parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = parent / (
            f".{self._config_path.name}."
            f"{uuid4().hex}.tmp"
        )

        try:
            serialized = json.dumps(
                config,
                ensure_ascii=False,
                indent=2,
            ) + "\n"

            temporary_path.write_text(
                serialized,
                encoding="utf-8",
                errors="strict",
            )

            temporary_path.replace(
                self._config_path
            )

        except OSError as exc:
            raise CmoJobConfigError(
                "无法原子写入 CMO 任务配置："
                f"{self._config_path}"
            ) from exc

        finally:
            # replace 成功后临时文件已经不存在；
            # 写入或替换失败时执行兜底清理。
            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except OSError:
                # 临时文件清理失败不覆盖原始异常。
                pass
