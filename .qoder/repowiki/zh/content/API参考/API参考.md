# API参考

<cite>
**本文档中引用的文件**
- [__init__.py](file://qlib/__init__.py)
- [config.py](file://qlib/config.py)
- [typehint.py](file://qlib/typehint.py)
- [mod.py](file://qlib/utils/mod.py)
- [data/__init__.py](file://qlib/data/__init__.py)
- [model/__init__.py](file://qlib/model/__init__.py)
- [workflow/__init__.py](file://qlib/workflow/__init__.py)
- [backtest/__init__.py](file://qlib/backtest/__init__.py)
</cite>

## 目录
1. [初始化接口](#初始化接口)
2. [数据模块](#数据模块)
3. [模型模块](#模型模块)
4. [工作流模块](#工作流模块)
5. [回测模块](#回测模块)
6. [配置系统](#配置系统)
7. [模块注册机制](#模块注册机制)

## 初始化接口

提供Qlib框架的初始化功能，包括自动配置加载和环境设置。

### init
初始化Qlib运行环境。

**函数签名**
```python
def init(default_conf="client", **kwargs)
```

**参数说明**
- `default_conf`: 配置模式，可选"client"或"server"
- `clear_mem_cache`: 是否清除内存缓存，默认True
- `skip_if_reg`: 是否跳过已注册的初始化，默认True

**返回值类型**
无返回值

**异常情况**
无显式异常抛出，但会在日志中记录错误信息

### init_from_yaml_conf
从YAML配置文件初始化Qlib。

**函数签名**
```python
def init_from_yaml_conf(conf_path, **kwargs)
```

**参数说明**
- `conf_path`: YAML配置文件路径
- `**kwargs`: 其他覆盖配置参数

**返回值类型**
无返回值

### auto_init
自动初始化Qlib，按优先级查找配置并初始化。

**函数签名**
```python
def auto_init(**kwargs)
```

**参数说明**
- `cur_path`: 查找项目配置的起始路径
- `skip_if_reg`: 是否跳过已注册的初始化

**返回值类型**
无返回值

**Section sources**
- [__init__.py](file://qlib/__init__.py#L30-L314)

## 数据模块

提供数据访问和管理的核心接口。

### 核心类
- `D`: 数据访问入口点
- `CalendarProvider`: 交易日历提供者
- `InstrumentProvider`: 标的物提供者
- `FeatureProvider`: 特征提供者
- `ExpressionProvider`: 表达式提供者
- `DatasetProvider`: 数据集提供者

### 本地实现类
- `LocalCalendarProvider`: 本地交易日历提供者
- `LocalInstrumentProvider`: 本地标的物提供者
- `LocalFeatureProvider`: 本地特征提供者
- `LocalPITProvider`: 本地PIT提供者
- `LocalExpressionProvider`: 本地表达式提供者
- `LocalDatasetProvider`: 本地数据集提供者

### 客户端实现类
- `ClientCalendarProvider`: 客户端交易日历提供者
- `ClientInstrumentProvider`: 客户端标的物提供者
- `ClientDatasetProvider`: 客户端数据集提供者

### 缓存类
- `ExpressionCache`: 表达式缓存基类
- `DatasetCache`: 数据集缓存基类
- `DiskExpressionCache`: 磁盘表达式缓存
- `DiskDatasetCache`: 磁盘数据集缓存
- `SimpleDatasetCache`: 简单数据集缓存
- `DatasetURICache`: 数据集URI缓存
- `MemoryCalendarCache`: 内存日历缓存

**Section sources**
- [data/__init__.py](file://qlib/data/__init__.py#L1-L66)

## 模型模块

提供机器学习模型的基础接口。

### Model
所有模型的基类，定义了模型的标准接口。

**函数签名**
```python
class Model:
    pass
```

该类作为所有具体模型实现的抽象基类，为模型开发提供了统一的接口规范。

**Section sources**
- [model/__init__.py](file://qlib/model/__init__.py#L1-L9)

## 工作流模块

提供实验管理和结果记录的核心功能。

### QlibRecorder
全局记录器，管理实验和记录器的生命周期。

#### start
启动实验的上下文管理器。

**函数签名**
```python
@contextmanager
def start(self, *, experiment_id=None, experiment_name=None, recorder_id=None, recorder_name=None, uri=None, resume=False)
```

**参数说明**
- `experiment_id`: 实验ID
- `experiment_name`: 实验名称
- `recorder_id`: 记录器ID
- `recorder_name`: 记录器名称
- `uri`: 跟踪URI
- `resume`: 是否恢复之前的记录器

#### get_exp
获取指定实验实例。

**函数签名**
```python
def get_exp(self, *, experiment_id=None, experiment_name=None, create=True, start=False) -> Experiment
```

**参数说明**
- `experiment_id`: 实验ID
- `experiment_name`: 实验名称
- `create`: 是否自动创建不存在的实验
- `start`: 是否启动实验

#### log_params
记录实验参数。

**函数签名**
```python
def log_params(self, **kwargs)
```

**参数说明**
- `**kwargs`: 要记录的参数键值对

#### log_metrics
记录实验指标。

**函数签名**
```python
def log_metrics(self, step=None, **kwargs)
```

**参数说明**
- `step`: 步骤编号
- `**kwargs`: 要记录的指标键值对

#### save_objects
保存对象为实验产物。

**函数签名**
```python
def save_objects(self, local_path=None, artifact_path=None, **kwargs: Dict[Text, Any])
```

**参数说明**
- `local_path`: 本地路径
- `artifact_path`: 产物路径
- `**kwargs`: 要保存的对象

### R
全局工作流记录器实例，作为工作流模块的主要入口点。

**Section sources**
- [workflow/__init__.py](file://qlib/workflow/__init__.py#L1-L681)

## 回测模块

提供回测功能的核心接口。

该模块包含回测相关的所有核心类和函数，包括账户管理、决策生成、交易所模拟、执行器、高绩效数据结构、持仓管理、收益归因、信号处理和工具函数等。

**Section sources**
- [backtest/__init__.py](file://qlib/backtest/__init__.py)

## 配置系统

### 配置结构
Qlib的配置系统基于`QlibConfig`类，提供灵活的配置管理能力。

#### 主要配置项
- `provider_uri`: 数据提供者URI，支持字符串或字典格式
- `expression_cache`: 表达式缓存类型
- `dataset_cache`: 数据集缓存类型
- `local_cache_path`: 本地缓存路径
- `kernels`: 并行计算核数
- `logging_level`: 日志级别
- `exp_manager`: 实验管理器配置
- `region`: 区域配置（REG_CN, REG_US, REG_TW）

#### 模式配置
支持两种主要模式：
- `server`: 服务端模式配置
- `client`: 客户端模式配置

#### 区域配置
不同市场的特定配置：
- `REG_CN`: 中国市场配置
- `REG_US`: 美国市场配置
- `REG_TW`: 台湾市场配置

### 配置使用
通过`C`全局变量访问当前配置，支持动态更新和重置。

**Section sources**
- [config.py](file://qlib/config.py#L1-L526)

## 模块注册机制

### 核心功能
通过`mod.py`提供的工具函数实现插件式扩展机制。

### 主要函数
#### init_instance_by_config
根据配置初始化实例，支持多种输入格式。

**函数签名**
```python
def init_instance_by_config(config: InstConf, default_module=None, accept_types=(), try_kwargs={}, **kwargs) -> Any
```

**参数说明**
- `config`: 实例配置，支持字典、字符串、对象或路径
- `default_module`: 默认模块
- `accept_types`: 接受的类型
- `try_kwargs`: 尝试传递的关键字参数

#### get_callable_kwargs
从配置中提取可调用对象和参数。

**函数签名**
```python
def get_callable_kwargs(config: InstConf, default_module: Union[str, ModuleType] = None) -> (type, dict)
```

**返回值类型**
返回元组(可调用对象, 参数字典)

#### find_all_classes
在指定模块中查找所有继承自指定基类的子类。

**函数签名**
```python
def find_all_classes(module_path: Union[str, ModuleType], cls: type) -> List[type]
```

**参数说明**
- `module_path`: 模块路径
- `cls`: 基类类型

该机制允许用户通过配置文件动态加载和实例化各类组件，实现高度可扩展的插件架构。

**Section sources**
- [mod.py](file://qlib/utils/mod.py#L1-L240)