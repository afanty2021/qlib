# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
测试重构后的NFS挂载功能

这个测试文件专门测试重构后的NFS挂载功能，
包括参数验证、系统兼容性和错误处理。
"""

import platform
import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock

from qlib.nfs_mount import (
    _validate_mount_parameters,
    _mount_windows_nfs,
    _check_if_already_mounted,
    _ensure_nfs_common_installed,
    _mount_linux_nfs,
    mount_nfs_uri_improved
)


class TestValidateMountParameters:
    """测试挂载参数验证"""

    def test_valid_parameters(self):
        """测试有效参数"""
        # 应该不抛出异常
        _validate_mount_parameters("192.168.1.100/data", "/mnt/test")

    def test_invalid_mount_path(self):
        """测试无效挂载路径"""
        with pytest.raises(ValueError, match="Invalid mount path"):
            _validate_mount_parameters("192.168.1.100/data", None)

    def test_invalid_provider_uri_format(self):
        """测试无效的provider_uri格式"""
        with pytest.raises(ValueError, match="Invalid provider_uri format"):
            _validate_mount_parameters("invalid uri with spaces", "/mnt/test")

    def test_provider_uri_with_special_chars(self):
        """测试包含特殊字符的有效URI"""
        # 有效字符应该通过
        _validate_mount_parameters("192.168.1.100/data-test", "/mnt/test")
        _validate_mount_parameters("server.local/path", "/mnt/test")


class TestMountWindowsNFS:
    """测试Windows NFS挂载"""

    @patch('subprocess.run')
    def test_successful_mount(self, mock_run):
        """测试成功挂载"""
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

        logger = Mock()
        _mount_windows_nfs("server/data", "/mnt/test", logger)

        mock_run.assert_called_once_with(
            ["mount", "-o", "anon", "server/data", "/mnt/test"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info.assert_called_with("Mount finished.")

    @patch('subprocess.run')
    def test_already_mounted(self, mock_run):
        """测试已经挂载的情况"""
        mock_run.side_effect = subprocess.CalledProcessError(85, "", "already mounted")

        logger = Mock()
        _mount_windows_nfs("server/data", "/mnt/test", logger)

        logger.warning.assert_called_once()

    @patch('subprocess.run')
    def test_network_path_not_found(self, mock_run):
        """测试网络路径不存在"""
        mock_run.side_effect = subprocess.CalledProcessError(53, "", "network error")

        logger = Mock()
        with pytest.raises(OSError, match="Network path not found"):
            _mount_windows_nfs("server/data", "/mnt/test", logger)


class TestCheckIfAlreadyMounted:
    """测试挂载状态检查"""

    @patch('subprocess.Popen')
    def test_already_mounted(self, mock_popen):
        """测试已经挂载的情况"""
        mock_process = Mock()
        mock_process.stdout.readlines.return_value = [
            "server/data on /mnt/test type nfs",
            "other mount entries"
        ]
        mock_popen.return_value.__enter__.return_value = mock_process

        result = _check_if_already_mounted("server/data", "/mnt/test")
        assert result is True

    @patch('subprocess.Popen')
    def test_not_mounted(self, mock_popen):
        """测试未挂载的情况"""
        mock_process = Mock()
        mock_process.stdout.readlines.return_value = [
            "other mount entries",
            "no matching mount"
        ]
        mock_popen.return_value.__enter__.return_value = mock_process

        result = _check_if_already_mounted("server/data", "/mnt/test")
        assert result is False

    @patch('subprocess.Popen')
    def test_subprocess_error(self, mock_popen):
        """测试subprocess错误"""
        mock_popen.side_effect = subprocess.SubprocessError("Permission denied")

        result = _check_if_already_mounted("server/data", "/mnt/test")
        assert result is False


class TestEnsureNFSCommonInstalled:
    """测试nfs-common包检查"""

    @patch('subprocess.run')
    def test_package_installed(self, mock_run):
        """测试包已安装"""
        mock_run.return_value = Mock(
            stdout="nfs-common 1:1.3.4-2.1ubuntu5",
            returncode=0
        )

        # 应该不抛出异常
        _ensure_nfs_common_installed()

    @patch('subprocess.run')
    def test_package_not_installed(self, mock_run):
        """测试包未安装"""
        mock_run.return_value = Mock(
            stdout="other packages",
            returncode=0
        )

        with pytest.raises(OSError, match="nfs-common is not found"):
            _ensure_nfs_common_installed()

    @patch('subprocess.run')
    def test_command_not_found(self, mock_run):
        """测试dpkg命令不存在"""
        mock_run.side_effect = FileNotFoundError("No such file")

        with pytest.raises(OSError, match="Failed to check nfs-common"):
            _ensure_nfs_common_installed()


class TestMountLinuxNFS:
    """测试Linux NFS挂载"""

    @patch('qlib.nfs_mount._ensure_nfs_common_installed')
    @patch('qlib.nfs_mount._check_if_already_mounted')
    @patch('subprocess.run')
    @patch('pathlib.Path.mkdir')
    def test_successful_mount(self, mock_mkdir, mock_run, mock_check, mock_ensure):
        """测试成功挂载"""
        mock_check.return_value = False

        logger = Mock()
        _mount_linux_nfs("server/data", "/mnt/test", logger)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_ensure.assert_called_once()
        mock_run.assert_called_once()

    @patch('qlib.nfs_mount._check_if_already_mounted')
    def test_already_mounted(self, mock_check):
        """测试已经挂载的情况"""
        mock_check.return_value = True

        logger = Mock()
        _mount_linux_nfs("server/data", "/mnt/test", logger)

        logger.info.assert_called_with("server/data already mounted at /mnt/test")


class TestMountNFSUriImproved:
    """测试改进的NFS挂载函数"""

    @patch('qlib.nfs_mount._mount_windows_nfs')
    @patch('platform.system')
    def test_windows_system(self, mock_system, mock_mount):
        """测试Windows系统"""
        mock_system.return_value = "Windows"

        mount_nfs_uri_improved("server/data", "/mnt/test", auto_mount=True)

        mock_mount.assert_called_once_with("server/data", "/mnt/test", ANY)

    @patch('qlib.nfs_mount._mount_linux_nfs')
    @patch('platform.system')
    def test_linux_system(self, mock_system, mock_mount):
        """测试Linux系统"""
        mock_system.return_value = "Linux"

        mount_nfs_uri_improved("server/data", "/mnt/test", auto_mount=True)

        mock_mount.assert_called_once_with("server/data", "/mnt/test", ANY)

    def test_auto_mount_false_and_path_not_exists(self):
        """测试auto_mount=False且路径不存在"""
        with pytest.raises(FileNotFoundError):
            mount_nfs_uri_improved("server/data", "/nonexistent/path", auto_mount=False)

    def test_invalid_parameters(self):
        """测试无效参数"""
        with pytest.raises(ValueError, match="Invalid mount path"):
            mount_nfs_uri_improved("server/data", None, auto_mount=True)

        with pytest.raises(ValueError, match="Invalid provider_uri format"):
            mount_nfs_uri_improved("invalid uri", "/mnt/test", auto_mount=True)


if __name__ == "__main__":
    pytest.main([__file__])