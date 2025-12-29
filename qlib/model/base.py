# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Qlib 模型基类模块

本模块定义了 Qlib 中所有机器学习模型的基础抽象类，提供：
1. 统一的模型接口规范
2. 标准化的训练和预测流程
3. 模型序列化和反序列化支持
4. 灵活的权重调整机制

主要组件：
- BaseModel: 所有模型的抽象基类
- Model: 可学习模型的基础类
- 支持从配置文件初始化模型

设计原则：
- 统一接口：所有模型都实现相同的接口
- 可扩展性：支持自定义模型和算法
- 配置驱动：通过配置文件管理模型参数
- 序列化支持：模型的保存和加载
"""

import abc
from typing import Text, Union
from ..utils.serial import Serializable
from ..data.dataset import Dataset
from ..data.dataset.weight import Reweighter


class BaseModel(Serializable, metaclass=abc.ABCMeta):
    """
    模型基础抽象类

    这是 Qlib 中所有模型的抽象基类，定义了模型的基本接口和行为。
    提供统一的预测接口和函数式调用支持。

    主要功能：
    1. 定义统一的预测接口
    2. 支持函数式调用模式
    3. 提供模型序列化基础
    4. 确保模型接口的一致性

    子类需要实现的方法：
    - predict(): 执行预测的抽象方法

    设计模式：
    - 抽象工厂模式：定义模型创建的接口
    - 函数式接口：支持直接调用模型对象

    Example:
        >>> class MyModel(BaseModel):
        ...     def predict(self, data):
        ...         return data * 2
        >>>
        >>> model = MyModel()
        >>> # 两种调用方式等价
        >>> result1 = model.predict(data)
        >>> result2 = model(data)
    """

    @abc.abstractmethod
    def predict(self, *args, **kwargs) -> object:
        """
        执行预测的抽象方法

        子类必须实现此方法来定义具体的预测逻辑。
        这是模型的核心功能接口。

        Args:
            *args: 可变位置参数
            **kwargs: 可变关键字参数

        Returns:
            object: 预测结果

        Raises:
            NotImplementedError: 子类必须实现此方法

        Note:
            - 参数的具体含义由子类定义
            - 返回值类型根据具体模型而定
            - 应该支持批量预测以提高效率
        """
        pass  # 子类必须实现

    def __call__(self, *args, **kwargs) -> object:
        """
        函数式调用接口

        利用 Python 语法糖，使模型对象可以像函数一样直接调用。
        提供更自然的编程接口。

        Args:
            *args: 传递给 predict 方法的位置参数
            **kwargs: 传递给 predict 方法的关键字参数

        Returns:
            object: predict 方法的返回值

        Example:
            >>> model = MyModel()
            >>> result = model(input_data)  # 直接调用
            >>> # 等价于
            >>> result = model.predict(input_data)
        """
        return self.predict(*args, **kwargs)


class Model(BaseModel):
    """
    可学习模型基类

    这是所有需要从数据中学习参数的模型的基础类。
    提供标准的训练接口和数据处理流程。

    主要功能：
    1. 提供统一的模型训练接口
    2. 支持数据集和权重调整
    3. 标准化的数据处理流程
    4. 模型保存和加载支持

    训练流程：
    1. 数据准备：从数据集中提取特征、标签和权重
    2. 模型训练：使用训练数据拟合模型参数
    3. 验证评估：使用验证数据评估模型性能
    4. 参数保存：保存训练好的模型参数

    属性命名规则：
    - 学习到的参数属性名不能以'_'开头
    - 这样可以确保模型能够正确地序列化到磁盘

    Example:
        >>> class MyModel(Model):
        ...     def fit(self, dataset, reweighter):
        ...         # 准备数据
        ...         df_train, df_valid = dataset.prepare(...)
        ...         x_train, y_train = df_train["feature"], df_train["label"]
        ...
        ...         # 训练模型
        ...         self.model.fit(x_train, y_train)
        ...
        ...     def predict(self, data):
        ...         return self.model.predict(data)
    """

    def fit(self, dataset: Dataset, reweighter: Reweighter):
        """
        从数据中学习模型参数

        这是模型训练的核心方法，负责从数据集中学习模型参数。
        子类应该重写此方法来实现具体的训练逻辑。

        Args:
            dataset (Dataset): 训练数据集，包含特征、标签和可选的权重
            reweighter (Reweighter): 权重调整器，用于样本权重调整

        Note:
            === 数据准备方式 ===
            以下代码展示了如何从数据集中提取训练数据：

            .. code-block:: Python

                # 准备训练和验证数据
                df_train, df_valid = dataset.prepare(
                    ["train", "valid"],                    # 数据集类型
                    col_set=["feature", "label"],         # 需要的列
                    data_key=DataHandlerLP.DK_L           # 数据键
                )

                # 提取特征和标签
                x_train, y_train = df_train["feature"], df_train["label"]
                x_valid, y_valid = df_valid["feature"], df_valid["label"]

                # 提取权重（可选）
                try:
                    wdf_train, wdf_valid = dataset.prepare(
                        ["train", "valid"],
                        col_set=["weight"],
                        data_key=DataHandlerLP.DK_L
                    )
                    w_train, w_valid = wdf_train["weight"], wdf_valid["weight"]
                except KeyError:
                    # 如果没有权重数据，使用默认权重
                    w_train, w_valid = None, None

            === 训练流程建议 ===
            1. 数据预处理和验证
            2. 模型参数初始化
            3. 迭代训练过程
            4. 验证集性能监控
            5. 早停和模型选择
            6. 最终模型保存

            === 注意事项 ===
            - 确保学习到的参数属性名不以'_'开头
            - 处理数据缺失和异常值
            - 实现适当的正则化防止过拟合
            - 考虑内存使用和计算效率
        """
        pass  # 子类应该重写此方法

    @abc.abstractmethod
    def predict(self, dataset: Dataset, segment: Union[Text, slice] = "test") -> object:
        """give prediction given Dataset

        Parameters
        ----------
        dataset : Dataset
            dataset will generate the processed dataset from model training.

        segment : Text or slice
            dataset will use this segment to prepare data. (default=test)

        Returns
        -------
        Prediction results with certain type such as `pandas.Series`.
        """
        raise NotImplementedError()


class ModelFT(Model):
    """Model (F)ine(t)unable"""

    @abc.abstractmethod
    def finetune(self, dataset: Dataset):
        """finetune model based given dataset

        A typical use case of finetuning model with qlib.workflow.R

        .. code-block:: python

            # start exp to train init model
            with R.start(experiment_name="init models"):
                model.fit(dataset)
                R.save_objects(init_model=model)
                rid = R.get_recorder().id

            # Finetune model based on previous trained model
            with R.start(experiment_name="finetune model"):
                recorder = R.get_recorder(recorder_id=rid, experiment_name="init models")
                model = recorder.load_object("init_model")
                model.finetune(dataset, num_boost_round=10)


        Parameters
        ----------
        dataset : Dataset
            dataset will generate the processed dataset from model training.
        """
        raise NotImplementedError()
