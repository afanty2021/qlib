[根目录](../../CLAUDE.md) > **examples** > **benchmarks**

# 基准测试系统 (benchmarks)

> Qlib 的完整模型性能基准测试平台，提供全面的量化模型评估和对比分析。

## 模块职责

benchmarks 模块提供：
- 全面的机器学习模型性能基准测试
- 标准化的评估指标和测试流程
- 详细的性能对比和分析报告
- 可复现的实验配置和结果

## 基准测试概览

### 测试数据集
- **Alpha158**：基于特征工程的表格数据集
  - 158个精心设计的技术指标特征
  - 适用于传统机器学习模型
  - 特征间空间关系较弱

- **Alpha360**：原始价格和成交量时序数据集
  - 360个时间步的原始 OHLCV 数据
  - 适用于深度学习和时序模型
  - 强时间维度空间关系

### 评估指标体系

#### 信号类指标（Signal-based Evaluation）
- **IC (Information Coefficient)**：预测值与实际收益的相关系数
- **ICIR**：IC的信息比率（均值/标准差）
- **Rank IC**：预测值排名与收益排名的相关系数
- **Rank ICIR**：Rank IC的信息比率

#### 组合类指标（Portfolio-based Evaluation）
- **年化收益 (Annualized Return)**：投资组合年化收益率
- **信息比率 (Information Ratio)**：超额收益的风险调整后收益
- **最大回撤 (Max Drawdown)**：最大损失幅度

## 基准测试结果

### CSI300 Alpha158 数据集性能排名

| 排名 | 模型名称 | IC | ICIR | 年化收益 | 信息比率 | 最大回撤 | 模型类型 |
|------|----------|----|----- |----------|----------|----------|----------|
| 🥇 | **DoubleEnsemble** | 0.0521 | 0.4223 | 0.1158 | 1.3432 | -0.0920 | 集成学习 |
| 🥈 | **XGBoost** | 0.0498 | 0.3779 | 0.0780 | 0.9070 | -0.1168 | 梯度提升 |
| 🥉 | **CatBoost** | 0.0481 | 0.3366 | 0.0765 | 0.8032 | -0.1092 | 梯度提升 |
| 4 | **LightGBM** | 0.0448 | 0.3660 | 0.0901 | 1.0164 | -0.1038 | 梯度提升 |
| 5 | **TRA (20 features)** | 0.0440 | 0.3535 | 0.0718 | 1.0835 | -0.0760 | 深度学习 |
| 6 | **Linear** | 0.0397 | 0.3000 | 0.0692 | 0.9209 | -0.1509 | 线性模型 |
| 7 | **TRA** | 0.0404 | 0.3197 | 0.0649 | 1.0091 | -0.0860 | 深度学习 |

### CSI300 Alpha360 数据集性能排名

| 排名 | 模型名称 | IC | ICIR | 年化收益 | 信息比率 | 最大回撤 | 模型类型 |
|------|----------|----|----- |----------|----------|----------|----------|
| 🥇 | **HIST** | 0.0522 | 0.3530 | 0.0987 | 1.3726 | -0.0681 | 深度学习 |
| 🥈 | **IGMTF** | 0.0480 | 0.3589 | 0.0946 | 1.3509 | -0.0716 | 深度学习 |
| 🥉 | **TRA** | 0.0485 | 0.3787 | 0.0920 | 1.2789 | -0.0834 | 深度学习 |
| 4 | **TCTS** | 0.0508 | 0.3931 | 0.0893 | 1.2256 | -0.0857 | 深度学习 |
| 5 | **GATs** | 0.0476 | 0.3508 | 0.0824 | 1.1079 | -0.0894 | 图神经网络 |
| 6 | **AdaRNN** | 0.0464 | 0.3619 | 0.0753 | 1.0200 | -0.0936 | 循环神经网络 |
| 7 | **GRU** | 0.0493 | 0.3772 | 0.0720 | 0.9730 | -0.0821 | 循环神经网络 |
| 8 | **LightGBM** | 0.0400 | 0.3037 | 0.0558 | 0.7632 | -0.0659 | 梯度提升 |

## 模型分类详解

### 传统机器学习模型

#### LightGBM
- **论文**：LightGBM: A Highly Efficient Gradient Boosting Decision Tree
- **特点**：高效梯度提升，内存占用低
- **适用场景**：Alpha158 特征工程数据
- **性能**：在 Alpha158 上表现稳定，综合性能优秀

#### XGBoost
- **特点**：极端梯度提升，正则化强
- **适用场景**：表格数据，特征重要性分析
- **性能**：在 Alpha158 上排名第二，表现突出

#### CatBoost
- **特点**：类别特征处理能力强，无需特征工程
- **适用场景**：混合数据类型，自动特征处理
- **性能**：在 Alpha158 上排名第三，稳定性好

#### Linear
- **特点**：简单线性模型，解释性强
- **适用场景**：基准对比，特征分析
- **性能**：简单的线性关系就能获得不错效果

### 深度学习模型

#### LSTM 系列
- **LSTM**：长短期记忆网络
- **ALSTM**：增强型 LSTM，引入注意力机制
- **特点**：时序建模能力强，适合 Alpha360 数据

#### Transformer 系列
- **Transformer**：自注意力机制
- **Localformer**：局部注意力 Transformer
- **特点**：并行计算能力强，长程依赖建模

#### 时序专用模型
- **TCN**：时间卷积网络
- **TRA**：时序关系感知网络
- **HIST**：历史信息感知网络
- **IGMTF**：交互式多尺度时序融合
- **TCTS**：时序交叉转换器

#### 图神经网络
- **GATs**：图注意力网络
- **特点**：建模股票间关系，捕捉市场结构

### 集成学习方法

#### DoubleEnsemble
- **论文**：DoubleEnsemble: A New Ensemble Method Based on Sample Reweighting and Feature Selection
- **特点**：
  - 基于学习轨迹的样本重加权
  - 基于洗牌的特征选择
  - 解决低信噪比和特征冗余问题
- **性能**：在 Alpha158 上排名第一，表现突出

## 配置文件系统

### 配置文件结构
每个模型都有对应的 YAML 配置文件，格式统一：

```yaml
# workflow_config_lightgbm_Alpha158.yaml
qlib_init:
    provider_uri: "~/.qlib/qlib_data/cn_data"
    region: "cn"

market: "csi300"
benchmark: "SH000300"

data_handler_config:
    start_time: "2008-01-01"
    end_time: "2020-08-01"
    fit_start_time: "2008-01-01"
    fit_end_time: "2014-12-31"
    instruments: "csi300"

model:
    class: "LGBModel"
    module_path: "qlib.contrib.model.gbdt"
    kwargs:
        loss: "mse"
        learning_rate: 0.1
        num_leaves: 31
        num_threads: 20

task:
    model:
        class: "LGBModel"
        module_path: "qlib.contrib.model.gbdt"
    dataset:
        class: "DatasetH"
        module_path: "qlib.data.dataset"
        kwargs:
            handler:
                class: "Alpha158"
                module_path: "qlib.contrib.data.handler"
                kwargs: ...
            segments:
                train: ("2008-01-01", "2014-12-31")
                valid: ("2015-01-01", "2016-12-31")
                test: ("2017-01-01", "2020-08-01")
```

### 特殊配置文件

#### 多频率配置
- `workflow_config_lightgbm_multi_freq.yaml`：多频率数据融合
- `workflow_config_lightgbm_Alpha158_multi_freq.yaml`：Alpha158 多频率

#### CSI500 配置
- `workflow_config_lightgbm_Alpha158_csi500.yaml`：CSI500 市场测试
- 支持快速扩展到其他市场

## 运行和使用指南

### 基本运行命令
```bash
# 进入模型目录
cd examples/benchmarks/LightGBM

# 安装依赖
pip install -r requirements.txt

# 运行基准测试
python workflow.py config_path.yaml
```

### 批量运行脚本
```bash
# 运行所有模型
bash run_all_benchmarks.sh

# 运行特定数据集的所有模型
bash run_alpha158_benchmarks.sh
bash run_alpha360_benchmarks.sh
```

### 结果收集和分析
```bash
# 收集所有结果
python collect_results.py --output benchmark_results.csv

# 生成性能报告
python generate_report.py --results benchmark_results.csv
```

## 性能分析和洞察

### 数据集特点分析

#### Alpha158 vs Alpha360
- **Alpha158**：传统机器学习表现更好
  - 特征工程已经提取了有用信息
  - 模型主要学习特征组合模式

- **Alpha360**：深度学习模型优势明显
  - 原始数据需要模型自动提取特征
  - 时序建模能力更关键

#### 模型类型分析

**传统 ML 优势**：
- 训练速度快
- 超参数较少
- 可解释性强
- 适合结构化数据

**深度学习优势**：
- 自动特征提取
- 时序建模能力强
- 端到端学习
- 适合原始数据

### 性能排名洞察

1. **数据适配性**：不同模型在不同数据集上表现差异很大
2. **集成方法**：DoubleEnsemble 在 Alpha158 上表现突出
3. **时序建模**：专门设计的时序模型在 Alpha360 上优势明显
4. **复杂度权衡**：模型复杂度与性能不成正比，需要权衡

## 扩展和自定义

### 添加新模型
1. **创建模型目录**：`examples/benchmarks/NewModel/`
2. **实现模型代码**：按照 Qlib 模型接口实现
3. **创建配置文件**：`workflow_config_newmodel_Alpha158.yaml`
4. **编写 README**：说明模型原理和使用方法
5. **运行测试**：验证性能和可复现性

### 添加新数据集
1. **数据处理器**：实现新的数据处理器类
2. **配置文件**：创建新数据集配置
3. **基准测试**：在新数据集上测试所有模型
4. **结果分析**：对比不同数据集上的性能

### 自定义评估指标
```python
# 添加自定义指标
def custom_metric(y_true, y_pred):
    # 计算自定义指标
    return metric_value

# 在配置中使用
task:
    record:
        - metric: "custom_metric"
          func: "path.to.custom_metric"
```

## 最佳实践建议

### 实验设计
1. **固定随机种子**：确保结果可复现
2. **多次运行**：至少运行 20 次取平均
3. **数据划分**：严格按照时间顺序划分
4. **超参数调优**：使用验证集进行参数选择

### 性能优化
1. **并行计算**：充分利用多核 CPU
2. **内存管理**：合理设置批次大小
3. **缓存策略**：缓存中间结果加速实验
4. **GPU 加速**：深度学习模型使用 GPU

### 结果分析
1. **统计显著性**：进行 t-test 等统计检验
2. **错误分析**：分析模型预测错误的样本
3. **特征分析**：分析特征重要性和贡献
4. **稳定性分析**：分析模型在不同时期的表现

## 常见问题 (FAQ)

### Q1: 如何复现论文结果？
```bash
# 使用 v1 版本数据
python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn --version v1

# 运行对应配置
python workflow.py workflow_config_modelname.yaml
```

### Q2: 如何在 CSI500 上测试？
```bash
# 复制并修改配置
cp workflow_config_lightgbm_Alpha158.yaml workflow_config_lightgbm_Alpha158_csi500.yaml
sed -i "s/csi300/csi500/g" workflow_config_lightgbm_Alpha158_csi500.yaml

# 运行测试
python workflow.py workflow_config_lightgbm_Alpha158_csi500.yaml
```

### Q3: 如何添加自定义指标？
```python
# 在 workflow.py 中添加
def custom_evaluation(dataset, model):
    predictions = model.predict(dataset)
    # 计算自定义指标
    return custom_score

# 在配置文件中启用
task:
    record:
        - custom_evaluation
```

### Q4: 如何调试模型性能？
```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 分析预测结果
predictions = model.predict(test_dataset)
analysis_df = pd.DataFrame({
    'pred': predictions,
    'label': test_dataset.labels,
    'feature_importance': model.feature_importances_
})
```

## 相关文件清单

### 核心模型目录
- `LightGBM/` - LightGBM 梯度提升模型
- `XGBoost/` - XGBoost 极端梯度提升
- `CatBoost/` - CatBoost 类别增强提升
- `Linear/` - 线性模型基准
- `DoubleEnsemble/` - 双重集成方法
- `MLP/` - 多层感知机
- `LSTM/` - 长短期记忆网络
- `ALSTM/` - 增强型 LSTM
- `GRU/` - 门控循环单元
- `Transformer/` - Transformer 模型
- `Localformer/` - 局部 Transformer
- `TCN/` - 时间卷积网络
- `TabNet/` - 表格神经网络
- `SFM/` - 稀疏特征混合
- `Sandwich/` - 三明治模型
- `TRA/` - 时序关系感知网络
- `GATs/` - 图注意力网络
- `HIST/` - 历史信息感知网络
- `IGMTF/` - 交互式多尺度时序融合
- `TCTS/` - 时序交叉转换器
- `TFT/` - 时间融合 Transformer
- `ADARNN/` - 自适应 RNN
- `ADD/` - 注意力密集分解
- `KRNN/` - 核循环神经网络

### 配置文件
- 各模型目录下的 `workflow_config_*.yaml` 文件
- 支持不同数据集和市场配置

### 工具和脚本
- `workflow.py` - 通用工作流执行脚本
- `requirements.txt` - 模型依赖文件
- `README.md` - 模型说明文档

## 变更记录 (Changelog)

### 2025-11-17 14:10:03 - 第五次增量更新创建
- ✨ **创建基准测试系统文档**：
  - 完整的性能基准测试分析
  - 详细的模型性能排名表格
  - 全面的配置文件系统说明
- 📊 **补充性能分析洞察**：
  - 数据集特点对比分析
  - 模型类型优势分析
  - 性能排名背后原因解析
- 🔗 **建立实用使用指南**：
  - 详细的运行和使用方法
  - 扩展和自定义指导
  - 最佳实践建议
- 📝 **补充问题解决方案**：
  - 常见问题详细解答
  - 调试和优化方法
  - 实验设计建议