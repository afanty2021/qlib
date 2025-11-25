# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import logging
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Union

from setuptools_scm import get_version
from ruamel.yaml import YAML

from .log import get_module_logger

try:
    from ._version import version as __version__
except ImportError:
    __version__ = get_version(root="..", relative_to=__file__)
__version__bak = __version__  # This version is backup for QlibConfig.reset_qlib_version


# init qlib
def init(default_conf="client", **kwargs):
    """

    Parameters
    ----------
    default_conf: str
        the default value is client. Accepted values: client/server.
    **kwargs :
        clear_mem_cache: str
            the default value is True;
            Will the memory cache be clear.
            It is often used to improve performance when init will be called for multiple times
        skip_if_reg: bool: str
            the default value is True;
            When using the recorder, skip_if_reg can set to True to avoid loss of recorder.

    """
    from .config import C  # pylint: disable=C0415
    from .data.cache import H  # pylint: disable=C0415

    logger = get_module_logger("Initialization")

    skip_if_reg = kwargs.pop("skip_if_reg", False)
    if skip_if_reg and C.registered:
        # if we reinitialize Qlib during running an experiment `R.start`.
        # it will result in loss of the recorder
        logger.warning("Skip initialization because `skip_if_reg is True`")
        return

    clear_mem_cache = kwargs.pop("clear_mem_cache", True)
    if clear_mem_cache:
        H.clear()
    C.set(default_conf, **kwargs)
    get_module_logger.setLevel(C.logging_level)

    # mount nfs
    for _freq, provider_uri in C.provider_uri.items():
        mount_path = C["mount_path"][_freq]
        # check path if server/local
        uri_type = C.dpm.get_uri_type(provider_uri)
        if uri_type == C.LOCAL_URI:
            if not Path(provider_uri).exists():
                if C["auto_mount"]:
                    logger.error(
                        f"Invalid provider uri: {provider_uri}, please check if a valid provider uri has been set. This path does not exist."
                    )
                else:
                    logger.warning(
                        f"auto_path is False, please make sure {mount_path} is mounted"
                    )
        elif uri_type == C.NFS_URI:
            _mount_nfs_uri(provider_uri, C.dpm.get_data_uri(_freq), C["auto_mount"])
        else:
            raise NotImplementedError("This type of URI is not supported")

    C.register()

    if "flask_server" in C:
        logger.info(f"flask_server={C['flask_server']}, flask_port={C['flask_port']}")
    logger.info("qlib successfully initialized based on %s settings." % default_conf)
    data_path = {
        _freq: C.dpm.get_data_uri(_freq) for _freq in C.dpm.provider_uri.keys()
    }
    logger.info(f"data_path={data_path}")


# 导入重构后的NFS挂载函数
from .nfs_mount import mount_nfs_uri_improved

def _mount_nfs_uri(provider_uri, mount_path, auto_mount: bool = False):
    """
    向后兼容的NFS挂载函数包装器

    为了保持向后兼容性，这个函数作为包装器调用重构后的改进版本。
    新代码建议直接使用 mount_nfs_uri_improved 函数。

    Parameters
    ----------
    provider_uri : str
        NFS路径URI
    mount_path : str
        本地挂载路径
    auto_mount : bool
        是否自动挂载

    Examples
    --------
    >>> _mount_nfs_uri("172.23.233.89/data/csdesign", "/mnt/nfs", auto_mount=True)
    Mount finished.
    """
    return mount_nfs_uri_improved(provider_uri, mount_path, auto_mount)
