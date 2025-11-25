#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Cython扩展编译脚本

编译高性能的量化操作符Cython扩展，
显著提升Qlib的数据处理性能。
"""

import numpy as np
from setuptools import setup
from setuptools.extension import Extension
from Cython.Build import cythonize
from Cython.Distutils import build_ext

# 定义Cython扩展
ext_modules = [
    Extension(
        "qlib.contrib.ops.fast_ops_cython",
        ["fast_ops.pyx"],
        include_dirs=[np.get_include()],
        language="c++",
        extra_compile_args=["-O3", "-ffast-math", "-march=native"],
        extra_link_args=["-O3"],
    ),
]

# 编译选项
compiler_directives = {
    'language_level': 3,
    'boundscheck': False,
    'wraparound': False,
    'initializedcheck': False,
    'cdivision': True,
    'optimize.use_switch': True,
    'optimize.unpack_method_calls': True,
}

setup(
    name="qlib-fast-ops",
    ext_modules=ext_modules,
    cmdclass=build_ext,
    python_requires=">=3.7",
    install_requires=["Cython>=0.29.0", "numpy>=1.19.0"],
    zip_safe=False,
    compiler_directives=compiler_directives,
)