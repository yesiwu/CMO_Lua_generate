"""
生产环境CMO实例独占文件锁
保证同一推演任务同时只能运行一个CMO仿真进程，防止并发冲突
"""
from __future__ import annotations

import json
import os
from pathlib import Path


class CmoLockError(RuntimeError):
    """CMO实例锁获取失败异常，代表已有CMO实例正在运行"""
    pass


class CmoInstanceLock:
    """
    文件互斥锁，用于管控单campaign下CMO兵棋实例的独占访问
    基于操作系统原子文件创建原语 O_EXCL，规避「先检查后创建」的竞态漏洞；
    实现上下文管理器协议，支持 with 语法自动上锁、自动释放。
    """
    def __init__(self, path: Path, *, campaign_id: str) -> None:
        """
        :param path: 锁文件路径
        :param campaign_id: 当前推演任务ID，写入锁文件便于故障排查
        """
        self._path = Path(path).resolve()
        self._campaign_id = campaign_id
        self._held = False  # 标记当前对象是否持有锁

    def acquire(self) -> None:
        """尝试抢占独占锁；锁文件已存在则抛出 CmoLockError"""
        # 确保锁目录存在
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # O_CREAT | O_EXCL：原子创建文件，文件已存在直接报错，无TOCTOU竞争窗口
            descriptor = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise CmoLockError("cmo_instance_locked") from exc

        # 写入锁元数据：任务ID + 当前进程PID，用于排查僵死锁
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump({"campaign_id": self._campaign_id, "pid": os.getpid()}, stream, sort_keys=True)
        self._held = True

    def release(self) -> None:
        """释放锁，仅持有锁的实例允许删除锁文件"""
        if self._held and self._path.is_file():
            self._path.unlink()
        self._held = False

    def __enter__(self) -> "CmoInstanceLock":
        """进入with上下文时自动获取锁"""
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        """正常退出/异常退出都会执行，自动释放锁"""
        self.release()