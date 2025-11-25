# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
NFS挂载功能重构模块

将原来复杂的_mount_nfs_uri函数重构为更小、更专注的函数，
提高代码的可读性、可维护性和测试性。
"""

import logging
import platform
import re
import subprocess
from pathlib import Path
from typing import Optional

from .log import get_module_logger


def _validate_mount_parameters(provider_uri: str, mount_path: Optional[str]) -> None:
    """验证挂载参数的有效性

    Parameters
    ----------
    provider_uri : str
        NFS路径URI
    mount_path : Optional[str]
        本地挂载路径

    Raises
    ------
    ValueError
        当参数无效时
    """
    if mount_path is None:
        raise ValueError(f"Invalid mount path: {mount_path}!")
    if not re.match(r"^[a-zA-Z0-9.:/\-_]+$", provider_uri):
        raise ValueError(f"Invalid provider_uri format: {provider_uri}")


def _mount_windows_nfs(provider_uri: str, mount_path, LOG) -> None:
    """Windows系统下的NFS挂载

    Parameters
    ----------
    provider_uri : str
        NFS路径URI
    mount_path : str
        本地挂载路径
    LOG : Logger
        日志记录器

    Raises
    ------
    OSError
        当挂载失败时
    """
    try:
        subprocess.run(
            ["mount", "-o", "anon", provider_uri, mount_path],
            capture_output=True,
            text=True,
            check=True,
        )
        LOG.info("Mount finished.")
    except subprocess.CalledProcessError as e:
        error_output = (e.stdout or "") + (e.stderr or "")
        if e.returncode == 85:
            LOG.warning(f"{provider_uri} already mounted at {mount_path}")
        elif e.returncode == 53:
            raise OSError("Network path not found") from e
        elif "error" in error_output.lower() or "错误" in error_output:
            raise OSError("Invalid mount path") from e
        else:
            raise OSError(f"Unknown mount error: {error_output.strip()}") from e


def _check_if_already_mounted(provider_uri: str, mount_path: str) -> bool:
    """检查NFS路径是否已经挂载

    Parameters
    ----------
    provider_uri : str
        NFS路径URI
    mount_path : str
        本地挂载路径

    Returns
    -------
    bool
        如果已经挂载返回True，否则返回False
    """
    _remote_uri = provider_uri[:-1] if provider_uri.endswith("/") else provider_uri
    _mount_path = mount_path[:-1] if mount_path.endswith("/") else mount_path
    _check_level_num = 2
    _is_mount = False

    while _check_level_num:
        try:
            with subprocess.Popen(
                ["mount"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as shell_r:
                _command_log = shell_r.stdout.readlines()
                _command_log = [
                    line for line in _command_log if _remote_uri in line
                ]

            if len(_command_log) > 0:
                for _c in _command_log:
                    if isinstance(_c, str):
                        _temp_mount = _c.split(" ")[2]
                    else:
                        _temp_mount = _c.decode("utf-8").split(" ")[2]
                    _temp_mount = (
                        _temp_mount[:-1] if _temp_mount.endswith("/") else _temp_mount
                    )
                    if _temp_mount == _mount_path:
                        _is_mount = True
                        break
            if _is_mount:
                break

        except (subprocess.SubprocessError, OSError):
            # 忽略检查过程中的错误，继续尝试更高级别的路径
            pass

        _remote_uri = "/".join(_remote_uri.split("/")[:-1])
        _mount_path = "/".join(_mount_path.split("/")[:-1])
        _check_level_num -= 1

    return _is_mount


def _ensure_nfs_common_installed() -> None:
    """确保nfs-common包已安装

    Raises
    ------
    OSError
        当nfs-common包未安装或检查失败时
    """
    try:
        result = subprocess.run(
            ["dpkg", "-l"],
            capture_output=True,
            text=True,
            check=True
        )
        if "nfs-common" not in result.stdout:
            raise OSError(
                "nfs-common is not found, please install it by execute: sudo apt install nfs-common"
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise OSError(
            "Failed to check nfs-common package. Please ensure nfs-common is installed: sudo apt install nfs-common"
        )


def _mount_linux_nfs(provider_uri: str, mount_path, LOG) -> None:
    """Linux/Unix系统下的NFS挂载

    Parameters
    ----------
    provider_uri : str
        NFS路径URI
    mount_path : str
        本地挂载路径
    LOG : Logger
        日志记录器

    Raises
    ------
    OSError
        当挂载失败时
    """
    # 检查是否已经挂载
    if _check_if_already_mounted(provider_uri, str(mount_path)):
        LOG.info(f"{provider_uri} already mounted at {mount_path}")
        return

    # 创建挂载目录
    try:
        Path(mount_path).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise OSError(
            f"Failed to create directory {mount_path}, please create {mount_path} manually!"
        ) from e

    # 确保nfs-common已安装
    _ensure_nfs_common_installed()

    # 执行挂载命令
    mount_command = ["sudo", "mount.nfs", provider_uri, mount_path]
    try:
        subprocess.run(
            mount_command, check=True, capture_output=True, text=True
        )
        LOG.info("Mount finished.")
    except subprocess.CalledProcessError as e:
        if e.returncode == 256:
            raise OSError(
                "Mount failed: requires sudo or permission denied"
            ) from e
        elif e.returncode == 32512:
            raise OSError(
                f"mount {provider_uri} on {mount_path} error! Command error"
            ) from e
        else:
            raise OSError(
                f"mount {provider_uri} on {mount_path} error! {e.stderr.strip() if e.stderr else ''}"
            ) from e


def mount_nfs_uri_improved(provider_uri: str, mount_path, auto_mount: bool = False):
    """
    改进的NFS路径挂载函数

    将原来复杂的_mount_nfs_uri函数重构为更小、更专注的函数，
    提高代码的可读性、可维护性和测试性。

    Parameters
    ----------
    provider_uri : str
        NFS路径URI
    mount_path : str
        本地挂载路径
    auto_mount : bool, optional
        是否自动挂载，默认为False

    Raises
    ------
    ValueError
        当挂载参数无效时
    FileNotFoundError
        当挂载路径不存在且auto_mount=False时
    OSError
        当挂载失败时

    Examples
    --------
    >>> mount_nfs_uri_improved("172.23.233.89/data/csdesign", "/mnt/nfs", auto_mount=True)
    Mount finished.
    """
    LOG = get_module_logger("mount nfs", level=logging.INFO)

    # 验证参数
    _validate_mount_parameters(provider_uri, mount_path)

    # 构建手动挂载命令（用于错误信息）
    mount_command = ["sudo", "mount.nfs", provider_uri, mount_path]

    if not auto_mount:
        if not Path(mount_path).exists():
            raise FileNotFoundError(
                f"Invalid mount path: {mount_path}! Please mount manually: {' '.join(mount_command)} or Set init parameter `auto_mount=True`"
            )
        return

    # 根据系统类型选择挂载方式
    sys_type = platform.system()
    if "windows" in sys_type.lower():
        _mount_windows_nfs(provider_uri, mount_path, LOG)
    else:
        _mount_linux_nfs(provider_uri, mount_path, LOG)