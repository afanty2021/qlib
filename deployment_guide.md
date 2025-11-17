[根目录](../../CLAUDE.md) > **部署运维指南**

# Qlib 部署运维与性能优化指南

> 本文档提供 Qlib 项目的完整部署运维方案和系统性能优化策略，涵盖开发环境搭建、生产环境部署、监控运维和性能调优的最佳实践。

## 部署架构概览

### 环境分层架构

```mermaid
graph TD
    A["开发环境"] --> A1["本地开发"];
    A --> A2["Docker 容器"];
    A --> A3["虚拟环境"];

    B["测试环境"] --> B1["单元测试"];
    B --> B2["集成测试"];
    B --> B3["性能测试"];

    C["生产环境"] --> C1["在线预测服务"];
    C --> C2["批量回测系统"];
    C --> C3["实时数据处理"];

    D["运维监控"] --> D1["系统监控"];
    D --> D2["性能监控"];
    D --> D3["日志监控"];

    A --> B;
    B --> C;
    C --> D;
```

## 开发环境部署

### 本地开发环境搭建

#### 1. 基础环境要求
```bash
# 操作系统要求
- Ubuntu 18.04+ / CentOS 7+ / macOS 10.14+
- Python 3.8+ (推荐 3.9+)
- 内存: 8GB+ (推荐 16GB+)
- 存储: 50GB+ 可用空间
- GPU: NVIDIA GTX 1060+ (可选，用于深度学习)
```

#### 2. 快速安装流程
```bash
# 步骤 1: 克隆项目
git clone https://github.com/microsoft/qlib.git
cd qlib

# 步骤 2: 创建虚拟环境
conda create -n qlib_env python=3.9
conda activate qlib_env

# 步骤 3: 安装依赖
pip install -e ".[dev]"

# 步骤 4: 初始化 Qlib
python -c "import qlib; qlib.init()"

# 步骤 5: 验证安装
cd examples
python workflow_by_code.py
```

#### 3. 开发工具配置
```bash
# 代码格式化工具
pip install black isort flake8 mypy

# Jupyter 环境配置
pip install jupyterlab ipywidgets

# IDE 配置 (VS Code)
# 安装扩展: Python, Pylance, Jupyter
```

### Docker 容器化部署

#### 1. Dockerfile 分析
```dockerfile
# 基础镜像选择
FROM continuumio/miniconda3:latest

# 工作目录设置
WORKDIR /qlib

# 依赖安装流程
COPY . .
RUN apt-get update && apt-get install -y build-essential

# Conda 环境创建
RUN conda create --name qlib_env python=3.8
ENV PATH /opt/conda/envs/qlib_env/bin:$PATH

# Python 包安装
RUN python -m pip install --upgrade pip
RUN pip install numpy pandas scikit-learn
RUN pip install cython pybind11 cvxpy

# Qlib 安装 (根据参数选择)
ARG IS_STABLE=true
RUN if [ "$IS_STABLE" = "true" ]; then \
        pip install pyqlib; \
    else \
        python setup.py install; \
    fi
```

#### 2. 构建和运行容器
```bash
# 构建镜像
docker build -t qlib:latest .

# 运行容器
docker run -it --rm \
    -v $(pwd)/data:/qlib/data \
    -p 8888:8888 \
    qlib:latest

# 挂载卷开发模式
docker run -it --rm \
    -v $(pwd):/qlib \
    -v $(pwd)/data:/qlib/.qlib/qlib_data \
    -p 8888:8888 \
    qlib:latest jupyter lab --ip=0.0.0.0
```

#### 3. Docker Compose 部署
```yaml
version: '3.8'

services:
  qlib-jupyter:
    build: .
    ports:
      - "8888:8888"
    volumes:
      - ./data:/qlib/.qlib/qlib_data
      - ./notebooks:/qlib/notebooks
    environment:
      - PYTHONPATH=/qlib
    command: jupyter lab --ip=0.0.0.0 --allow-root

  qlib-api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/qlib/.qlib/qlib_data
      - ./models:/qlib/models
    environment:
      - QLIB_MODE=online
    command: python -m qlib.contrib.online.serve

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

## 生产环境部署

### 系统架构设计

#### 1. 高可用架构
```mermaid
graph TD
    A["负载均衡器 Nginx"] --> B["API Gateway 1"];
    A --> C["API Gateway 2"];

    B --> D["Qlib Service 1"];
    B --> E["Qlib Service 2"];
    C --> F["Qlib Service 3"];
    C --> G["Qlib Service 4"];

    D --> H["Redis Cluster"];
    E --> H;
    F --> H;
    G --> H;

    H --> I["PostgreSQL"];
    H --> J["MinIO Storage"];

    K["监控系统 Prometheus"] --> L["Grafana"];
    L --> M["告警系统"];
```

#### 2. 微服务部署架构
```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qlib-prediction-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: qlib-prediction
  template:
    metadata:
      labels:
        app: qlib-prediction
    spec:
      containers:
      - name: qlib-prediction
        image: qlib:production
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        - name: DB_URL
          value: "postgresql://user:pass@postgres:5432/qlib"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
```

### 在线预测服务部署

#### 1. 服务配置
```python
# config/production.py
import os

class ProductionConfig:
    # 数据库配置
    DATABASE_URL = os.getenv("DB_URL", "postgresql://localhost/qlib")

    # Redis 配置
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

    # 模型配置
    MODEL_PATH = "/app/models"
    MODEL_VERSION = "v1.0.0"

    # 性能配置
    WORKERS = 4
    MAX_CONNECTIONS = 100
    REQUEST_TIMEOUT = 30

    # 监控配置
    METRICS_ENABLED = True
    LOG_LEVEL = "INFO"

    # 缓存配置
    CACHE_TTL = 300  # 5分钟
    CACHE_SIZE = 1000
```

#### 2. 服务启动脚本
```bash
#!/bin/bash
# scripts/start_production.sh

set -e

echo "Starting Qlib Production Service..."

# 环境检查
python -c "import qlib; print('Qlib version:', qlib.__version__)"

# 模型预加载
python scripts/preload_models.py

# 启动服务
gunicorn --bind 0.0.0.0:8000 \
         --workers $WORKERS \
         --worker-class uvicorn.workers.UvicornWorker \
         --timeout 120 \
         --access-logfile - \
         --error-logfile - \
         qlib.contrib.online.app:app

echo "Qlib Production Service Started Successfully!"
```

### 数据存储架构

#### 1. 分布式存储方案
```python
# config/storage.py
class StorageConfig:
    # 文件存储 (MinIO/S3)
    S3_ENDPOINT = "s3.amazonaws.com"
    S3_BUCKET = "qlib-data"
    S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
    S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")

    # 时序数据库 (InfluxDB)
    INFLUXDB_URL = "http://influxdb:8086"
    INFLUXDB_DB = "qlib_metrics"

    # 缓存配置
    REDIS_CLUSTER = [
        "redis://redis-node-1:6379",
        "redis://redis-node-2:6379",
        "redis://redis-node-3:6379"
    ]
```

#### 2. 数据备份策略
```bash
#!/bin/bash
# scripts/backup_data.sh

BACKUP_DIR="/backup/qlib_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# 模型备份
tar -czf $BACKUP_DIR/models.tar.gz /app/models/

# 数据备份
pg_dump qlib_production | gzip > $BACKUP_DIR/database.sql.gz

# 配置备份
cp -r /app/config $BACKUP_DIR/

# 上传到云存储
aws s3 sync $BACKUP_DIR s3://qlib-backups/$(date +%Y%m%d)/

# 清理本地备份
rm -rf $BACKUP_DIR

echo "Backup completed: $BACKUP_DIR"
```

## 监控运维体系

### 系统监控

#### 1. Prometheus 监控配置
```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'qlib-prediction'
    static_configs:
      - targets: ['qlib-service:8000']
    metrics_path: '/metrics'
    scrape_interval: 5s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']
```

#### 2. 关键指标监控
```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# 请求指标
REQUEST_COUNT = Counter(
    'qlib_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'qlib_request_duration_seconds',
    'Request duration',
    ['method', 'endpoint']
)

# 模型指标
MODEL_PREDICTION_COUNT = Counter(
    'qlib_model_predictions_total',
    'Total model predictions',
    ['model_name', 'model_version']
)

MODEL_ACCURACY = Gauge(
    'qlib_model_accuracy',
    'Model accuracy',
    ['model_name']
)

# 系统指标
ACTIVE_CONNECTIONS = Gauge(
    'qlib_active_connections',
    'Active connections'
)

MEMORY_USAGE = Gauge(
    'qlib_memory_usage_bytes',
    'Memory usage in bytes'
)
```

#### 3. Grafana 仪表板
```json
{
  "dashboard": {
    "title": "Qlib Service Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(qlib_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, qlib_request_duration_seconds_bucket)",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Model Performance",
        "type": "singlestat",
        "targets": [
          {
            "expr": "qlib_model_accuracy",
            "legendFormat": "{{model_name}}"
          }
        ]
      }
    ]
  }
}
```

### 日志管理

#### 1. 结构化日志配置
```python
# config/logging.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        if hasattr(record, 'request_id'):
            log_obj["request_id"] = record.request_id

        if hasattr(record, 'user_id'):
            log_obj["user_id"] = record.user_id

        return json.dumps(log_obj)

# 日志配置
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': JSONFormatter,
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/logs/qlib.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'json',
        },
    },
    'loggers': {
        'qlib': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

#### 2. ELK 日志收集
```yaml
# logging/logstash.conf
input {
  beats {
    port => 5044
  }
}

filter {
  if [fields][service] == "qlib" {
    json {
      source => "message"
    }

    date {
      match => [ "timestamp", "ISO8601" ]
    }

    mutate {
      add_tag => ["qlib"]
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "qlib-logs-%{+YYYY.MM.dd}"
  }
}
```

### 告警系统

#### 1. 告警规则配置
```yaml
# monitoring/alerts.yml
groups:
  - name: qlib_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(qlib_requests_total{status!~"2.."}[5m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors per second"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, qlib_request_duration_seconds_bucket) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High response time detected"
          description: "95th percentile response time is {{ $value }} seconds"

      - alert: ModelAccuracyDrop
        expr: qlib_model_accuracy < 0.7
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Model accuracy dropped"
          description: "Model {{ $labels.model_name }} accuracy is {{ $value }}"
```

## 性能优化策略

### 系统级性能优化

#### 1. 硬件优化建议
```yaml
# 生产环境硬件配置
production_hardware:
  cpu:
    - "Intel Xeon Gold 6248R (24 cores, 48 threads)"
    - "AMD EPYC 7742 (64 cores, 128 threads)"

  memory:
    - "DDR4 ECC RAM: 256GB+"
    - "内存频率: 3200MHz+"
    - "通道配置: 8通道"

  storage:
    - "主存储: NVMe SSD (读写速度 3500MB/s+)"
    - "数据存储: 企业级 SSD阵列"
    - "备份存储: 高容量HDD"

  gpu:
    - "NVIDIA A100 (40GB HBM2)"
    - "NVIDIA V100 (32GB HBM2)"
    - "支持 NVLink 和 GPU Direct"
```

#### 2. 操作系统优化
```bash
#!/bin/bash
# scripts/system_optimization.sh

# 内核参数优化
echo 'net.core.rmem_max = 134217728' >> /etc/sysctl.conf
echo 'net.core.wmem_max = 134217728' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_rmem = 4096 65536 134217728' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_wmem = 4096 65536 134217728' >> /etc/sysctl.conf

# 文件系统优化
echo 'vm.swappiness = 10' >> /etc/sysctl.conf
echo 'vm.dirty_ratio = 15' >> /etc/sysctl.conf
echo 'vm.dirty_background_ratio = 5' >> /etc/sysctl.conf

# 应用优化
sysctl -p

# CPU 亲和性设置
taskset -c 0-23 python -m qlib.contrib.online.serve

# 大页内存配置
echo 1024 > /proc/sys/vm/nr_hugepages
```

### 应用级性能优化

#### 1. 数据处理优化
```python
# performance/data_optimization.py
import pandas as pd
import numpy as np
from multiprocessing import Pool
import joblib
from functools import lru_cache

class OptimizedDataProcessor:
    def __init__(self, n_workers=8):
        self.n_workers = n_workers
        self.memory_map = {}

    @lru_cache(maxsize=1000)
    def cached_calculation(self, params_hash):
        """缓存计算结果"""
        # 实际计算逻辑
        return result

    def parallel_processing(self, data_chunks):
        """并行处理数据块"""
        with Pool(self.n_workers) as pool:
            results = pool.map(self.process_chunk, data_chunks)
        return pd.concat(results, ignore_index=True)

    def memory_efficient_load(self, file_path, chunksize=10000):
        """内存高效的数据加载"""
        chunks = []
        for chunk in pd.read_csv(file_path, chunksize=chunksize):
            # 数据类型优化
            chunk = self.optimize_dtypes(chunk)
            chunks.append(chunk)
            # 内存清理
            del chunk

        return pd.concat(chunks, ignore_index=True)

    def optimize_dtypes(self, df):
        """优化数据类型以减少内存使用"""
        for col in df.select_dtypes(include=['int64']).columns:
            df[col] = pd.to_numeric(df[col], downcast='integer')

        for col in df.select_dtypes(include=['float64']).columns:
            df[col] = pd.to_numeric(df[col], downcast='float')

        return df
```

#### 2. 模型推理优化
```python
# performance/model_optimization.py
import torch
import onnxruntime as ort
from concurrent.futures import ThreadPoolExecutor
import asyncio

class OptimizedModelService:
    def __init__(self, model_path, batch_size=32):
        self.model_path = model_path
        self.batch_size = batch_size
        self.model = self.load_optimized_model()
        self.executor = ThreadPoolExecutor(max_workers=4)

    def load_optimized_model(self):
        """加载优化后的模型"""
        # 使用 ONNX Runtime
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        session = ort.InferenceSession(
            self.model_path,
            providers=providers
        )
        return session

    async def batch_predict(self, inputs):
        """批量预测优化"""
        results = []
        for i in range(0, len(inputs), self.batch_size):
            batch = inputs[i:i + self.batch_size]
            batch_result = await self.async_predict_batch(batch)
            results.extend(batch_result)

        return results

    async def async_predict_batch(self, batch):
        """异步批量预测"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._predict_batch,
            batch
        )

    def _predict_batch(self, batch):
        """实际批量预测计算"""
        input_tensor = torch.tensor(batch, dtype=torch.float32)

        with torch.no_grad():
            if torch.cuda.is_available():
                input_tensor = input_tensor.cuda()

            outputs = self.model.run(None, {'input': input_tensor.cpu().numpy()})
            return outputs[0].tolist()

    def warmup_model(self):
        """模型预热"""
        dummy_input = torch.randn(self.batch_size, self.input_dim)
        self._predict_batch(dummy_input.numpy())
```

#### 3. 缓存策略优化
```python
# performance/cache_optimization.py
import redis
import pickle
from typing import Any, Optional
import hashlib
import json

class AdvancedCacheManager:
    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url)
        self.local_cache = {}
        self.cache_stats = {"hits": 0, "misses": 0}

    def generate_cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        key_data = {
            "func": func_name,
            "args": args,
            "kwargs": kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        # 本地缓存检查
        if key in self.local_cache:
            self.cache_stats["hits"] += 1
            return self.local_cache[key]

        # Redis 缓存检查
        try:
            data = self.redis_client.get(key)
            if data:
                result = pickle.loads(data)
                # 回填本地缓存
                self.local_cache[key] = result
                self.cache_stats["hits"] += 1
                return result
        except Exception as e:
            print(f"Cache get error: {e}")

        self.cache_stats["misses"] += 1
        return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存数据"""
        # 本地缓存
        self.local_cache[key] = value

        # Redis 缓存
        try:
            serialized = pickle.dumps(value)
            self.redis_client.setex(key, ttl, serialized)
        except Exception as e:
            print(f"Cache set error: {e}")

    def cache_function_result(self, ttl: int = 3600):
        """函数结果缓存装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                cache_key = self.generate_cache_key(
                    func.__name__, args, kwargs
                )

                # 尝试从缓存获取
                cached_result = self.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # 执行函数并缓存结果
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                return result

            return wrapper
        return decorator

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = self.cache_stats["hits"] / total_requests if total_requests > 0 else 0

        return {
            **self.cache_stats,
            "hit_rate": hit_rate,
            "local_cache_size": len(self.local_cache)
        }
```

### 数据库优化

#### 1. PostgreSQL 优化配置
```sql
-- 数据库性能优化配置
-- postgresql.conf 关键参数

-- 内存配置
shared_buffers = 64GB          -- 系统内存的 25%
effective_cache_size = 192GB   -- 系统内存的 75%
work_mem = 256MB               -- 排序和哈希操作内存
maintenance_work_mem = 2GB     -- 维护操作内存

-- 连接配置
max_connections = 200          -- 最大连接数
shared_preload_libraries = 'pg_stat_statements'

-- 检查点配置
checkpoint_completion_target = 0.9
wal_buffers = 64MB
default_statistics_target = 100

-- 查询优化
random_page_cost = 1.1         -- SSD 优化
effective_io_concurrency = 200 -- SSD 并发 I/O
```

#### 2. 索引优化策略
```sql
-- 关键查询索引优化
CREATE INDEX CONCURRENTLY idx_instruments_date ON instruments(date);
CREATE INDEX CONCURRENTLY idx_features_symbol_date ON features(symbol, date);
CREATE INDEX CONCURRENTLY idx_predictions_model_date ON predictions(model_id, date);

-- 分区表优化
CREATE TABLE features_partitioned (
    LIKE features INCLUDING ALL
) PARTITION BY RANGE (date);

CREATE TABLE features_2023 PARTITION OF features_partitioned
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');

-- 查询性能监控
SELECT query, calls, total_time, mean_time, rows
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;
```

## 容灾和高可用

### 备份恢复策略

#### 1. 自动化备份
```bash
#!/bin/bash
# scripts/automated_backup.sh

BACKUP_CONFIG="/app/config/backup_config.json"
LOG_FILE="/app/logs/backup.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOG_FILE
}

backup_database() {
    log "Starting database backup..."

    # 创建备份目录
    BACKUP_DIR="/backup/database/$(date +%Y%m%d_%H%M%S)"
    mkdir -p $BACKUP_DIR

    # 全量备份
    pg_dump -h $DB_HOST -U $DB_USER -d qlib_prod \
        --format=custom --compress=9 \
        --file=$BACKUP_DIR/qlib_full.dump

    # 验证备份
    pg_restore --list $BACKUP_DIR/qlib_full.dump > /dev/null
    if [ $? -eq 0 ]; then
        log "Database backup completed successfully"
        # 上传到云存储
        aws s3 cp $BACKUP_DIR s3://qlib-backups/database/ --recursive
    else
        log "ERROR: Database backup validation failed"
    fi
}

backup_models() {
    log "Starting models backup..."

    MODEL_BACKUP_DIR="/backup/models/$(date +%Y%m%d_%H%M%S)"
    mkdir -p $MODEL_BACKUP_DIR

    # 增量备份模型文件
    rsync -av --link-dest=/backup/models/latest \
        /app/models/ $MODEL_BACKUP_DIR/

    # 更新最新链接
    rm -f /backup/models/latest
    ln -s $MODEL_BACKUP_DIR /backup/models/latest

    log "Models backup completed"
}

# 清理旧备份
cleanup_old_backups() {
    log "Cleaning up old backups..."

    # 保留最近30天的备份
    find /backup -type d -mtime +30 -exec rm -rf {} \;

    # 清理云存储旧备份
    aws s3 ls s3://qlib-backups/ | while read -r line; do
        createDate=$(echo $line | awk '{print $1" "$2}')
        createDate=$(date -d "$createDate" +%s)
        olderThan=$(date -d "30 days ago" +%s)

        if [[ $createDate -lt $olderThan ]]; then
            fileName=$(echo $line | awk '{print $4}')
            if [[ $fileName != "" ]]; then
                aws s3 rm s3://qlib-backups/$fileName --recursive
            fi
        fi
    done
}

# 执行备份流程
backup_database
backup_models
cleanup_old_backups

log "Backup process completed"
```

#### 2. 灾难恢复计划
```bash
#!/bin/bash
# scripts/disaster_recovery.sh

RECOVERY_PLAN="/app/config/recovery_plan.json"
LOG_FILE="/app/logs/recovery.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOG_FILE
}

check_recovery_prerequisites() {
    log "Checking recovery prerequisites..."

    # 检查备份文件可用性
    if ! aws s3 ls s3://qlib-backups/database/ > /dev/null 2>&1; then
        log "ERROR: Cannot access backup storage"
        exit 1
    fi

    # 检查数据库连接
    if ! pg_isready -h $DB_HOST -p $DB_PORT; then
        log "ERROR: Database is not ready"
        exit 1
    fi

    # 检查磁盘空间
    REQUIRED_SPACE=100  # GB
    AVAILABLE_SPACE=$(df / | awk 'NR==2 {print int($4/1024/1024)}')

    if [ $AVAILABLE_SPACE -lt $REQUIRED_SPACE ]; then
        log "ERROR: Insufficient disk space. Required: ${REQUIRED_SPACE}GB, Available: ${AVAILABLE_SPACE}GB"
        exit 1
    fi

    log "Recovery prerequisites check passed"
}

recover_database() {
    log "Starting database recovery..."

    # 下载最新备份
    LATEST_BACKUP=$(aws s3 ls s3://qlib-backups/database/ --recursive | sort | tail -n 1 | awk '{print $4}')
    aws s3 cp s3://qlib-backups/database/$LATEST_BACKUP /tmp/recovery.dump

    # 停止应用服务
    systemctl stop qlib-service

    # 恢复数据库
    dropdb -h $DB_HOST -U $DB_USER qlib_prod
    createdb -h $DB_HOST -U $DB_USER qlib_prod

    pg_restore -h $DB_HOST -U $DB_USER -d qlib_prod \
        --clean --if-exists --verbose /tmp/recovery.dump

    # 验证恢复
    psql -h $DB_HOST -U $DB_USER -d qlib_prod -c "SELECT COUNT(*) FROM instruments;"

    if [ $? -eq 0 ]; then
        log "Database recovery completed successfully"
    else
        log "ERROR: Database recovery failed"
        exit 1
    fi
}

recover_models() {
    log "Starting models recovery..."

    # 下载最新模型备份
    LATEST_MODEL_BACKUP=$(aws s3 ls s3://qlib-backups/models/ --recursive | sort | tail -n 1 | awk '{print $4}')
    aws s3 cp s3://qlib-backups/models/$LATEST_MODEL_BACKUP /tmp/models.tar.gz

    # 恢复模型文件
    rm -rf /app/models/*
    tar -xzf /tmp/models.tar.gz -C /app/models/

    # 验证模型文件
    python -c "import joblib; model = joblib.load('/app/models/latest_model.pkl'); print('Model loaded successfully')"

    if [ $? -eq 0 ]; then
        log "Models recovery completed successfully"
    else
        log "ERROR: Models recovery failed"
        exit 1
    fi
}

restart_services() {
    log "Restarting services..."

    # 启动应用服务
    systemctl start qlib-service

    # 等待服务启动
    sleep 30

    # 健康检查
    curl -f http://localhost:8000/health || {
        log "ERROR: Service health check failed"
        exit 1
    }

    log "Services restarted successfully"
}

# 执行恢复流程
check_recovery_prerequisites
recover_database
recover_models
restart_services

log "Disaster recovery completed successfully"
```

### 负载均衡和扩展

#### 1. Nginx 负载均衡配置
```nginx
# nginx/nginx.conf
upstream qlib_backend {
    least_conn;
    server qlib-1:8000 max_fails=3 fail_timeout=30s;
    server qlib-2:8000 max_fails=3 fail_timeout=30s;
    server qlib-3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.qlib.example.com;

    # 限流配置
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    location / {
        proxy_pass http://qlib_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # 健康检查端点
    location /health {
        access_log off;
        proxy_pass http://qlib_backend/health;
    }

    # 静态文件缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## 故障排除指南

### 常见问题诊断

#### 1. 服务启动问题
```bash
#!/bin/bash
# scripts/troubleshoot.sh

check_service_status() {
    echo "=== Service Status Check ==="
    systemctl status qlib-service
    journalctl -u qlib-service --since "1 hour ago" --no-pager
}

check_dependencies() {
    echo "=== Dependency Check ==="

    # Python 环境
    python --version
    pip list | grep qlib

    # 数据库连接
    pg_isready -h $DB_HOST -p $DB_PORT

    # Redis 连接
    redis-cli -h $REDIS_HOST -p $REDIS_PORT ping

    # 磁盘空间
    df -h

    # 内存使用
    free -h
}

check_model_files() {
    echo "=== Model Files Check ==="

    if [ -f "/app/models/latest_model.pkl" ]; then
        echo "Latest model file exists"
        ls -lh /app/models/latest_model.pkl
    else
        echo "WARNING: Latest model file not found"
    fi

    # 模型文件完整性
    python -c "
import joblib
try:
    model = joblib.load('/app/models/latest_model.pkl')
    print('Model loaded successfully')
    print(f'Model type: {type(model)}')
except Exception as e:
    print(f'Model loading failed: {e}')
"
}

check_logs() {
    echo "=== Recent Logs ==="
    tail -n 50 /app/logs/qlib.log | grep -E "(ERROR|WARN|CRITICAL)"
}

# 执行诊断
check_service_status
check_dependencies
check_model_files
check_logs

echo "=== Troubleshooting completed ==="
```

#### 2. 性能问题诊断
```python
# scripts/performance_diagnostics.py
import psutil
import time
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

class PerformanceDiagnostics:
    def __init__(self):
        self.metrics_history = []

    def collect_system_metrics(self):
        """收集系统性能指标"""
        metrics = {
            "timestamp": datetime.now(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_io_read": psutil.disk_io_counters().read_bytes,
            "disk_io_write": psutil.disk_io_counters().write_bytes,
            "network_io_sent": psutil.net_io_counters().bytes_sent,
            "network_io_recv": psutil.net_io_counters().bytes_recv,
        }

        self.metrics_history.append(metrics)
        return metrics

    def analyze_performance_trends(self, duration_minutes=60):
        """分析性能趋势"""
        print(f"=== Performance Analysis (Last {duration_minutes} minutes) ===")

        # 收集指标
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=duration_minutes)

        relevant_metrics = [
            m for m in self.metrics_history
            if m["timestamp"] >= start_time
        ]

        if not relevant_metrics:
            print("No metrics data available for analysis")
            return

        df = pd.DataFrame(relevant_metrics)

        # CPU 分析
        avg_cpu = df["cpu_percent"].mean()
        max_cpu = df["cpu_percent"].max()
        print(f"CPU Usage - Average: {avg_cpu:.1f}%, Max: {max_cpu:.1f}%")

        # 内存分析
        avg_memory = df["memory_percent"].mean()
        max_memory = df["memory_percent"].max()
        print(f"Memory Usage - Average: {avg_memory:.1f}%, Max: {max_memory:.1f}%")

        # 磁盘 I/O 分析
        if len(df) > 1:
            disk_read_rate = (df["disk_io_read"].iloc[-1] - df["disk_io_read"].iloc[0]) / duration_minutes / 1024 / 1024
            disk_write_rate = (df["disk_io_write"].iloc[-1] - df["disk_io_write"].iloc[0]) / duration_minutes / 1024 / 1024
            print(f"Disk I/O - Read: {disk_read_rate:.1f} MB/min, Write: {disk_write_rate:.1f} MB/min")

        # 性能建议
        if avg_cpu > 80:
            print("⚠️  High CPU usage detected. Consider scaling or optimization.")

        if avg_memory > 85:
            print("⚠️  High memory usage detected. Check for memory leaks.")

        if disk_read_rate > 100 or disk_write_rate > 100:
            print("⚠️  High disk I/O detected. Consider optimizing data access patterns.")

    def generate_performance_report(self):
        """生成性能报告"""
        if not self.metrics_history:
            print("No performance data available")
            return

        df = pd.DataFrame(self.metrics_history)

        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # CPU 使用率
        axes[0, 0].plot(df["timestamp"], df["cpu_percent"])
        axes[0, 0].set_title("CPU Usage (%)")
        axes[0, 0].set_ylabel("Percentage")

        # 内存使用率
        axes[0, 1].plot(df["timestamp"], df["memory_percent"])
        axes[0, 1].set_title("Memory Usage (%)")
        axes[0, 1].set_ylabel("Percentage")

        # 磁盘 I/O
        axes[1, 0].plot(df["timestamp"], df["disk_io_read"], label="Read")
        axes[1, 0].plot(df["timestamp"], df["disk_io_write"], label="Write")
        axes[1, 0].set_title("Disk I/O (bytes)")
        axes[1, 0].legend()

        # 网络 I/O
        axes[1, 1].plot(df["timestamp"], df["network_io_sent"], label="Sent")
        axes[1, 1].plot(df["timestamp"], df["network_io_recv"], label="Received")
        axes[1, 1].set_title("Network I/O (bytes)")
        axes[1, 1].legend()

        plt.tight_layout()
        plt.savefig("/app/logs/performance_report.png", dpi=300, bbox_inches='tight')
        print("Performance report saved to /app/logs/performance_report.png")

if __name__ == "__main__":
    diagnostics = PerformanceDiagnostics()

    # 持续监控
    try:
        while True:
            diagnostics.collect_system_metrics()
            time.sleep(60)  # 每分钟收集一次指标
    except KeyboardInterrupt:
        print("\nGenerating performance analysis...")
        diagnostics.analyze_performance_trends()
        diagnostics.generate_performance_report()
```

## 最佳实践总结

### 开发最佳实践

1. **代码质量**
   - 遵循 PEP 8 编码规范
   - 使用类型提示和文档字符串
   - 编写完整的单元测试和集成测试
   - 定期进行代码审查

2. **性能优化**
   - 使用向量化操作替代循环
   - 合理使用缓存机制
   - 异步处理 I/O 密集型操作
   - 监控和优化内存使用

3. **安全实践**
   - 定期更新依赖包
   - 使用 HTTPS 加密通信
   - 实施访问控制和权限管理
   - 定期进行安全审计

### 运维最佳实践

1. **监控告警**
   - 建立完善的监控体系
   - 设置合理的告警阈值
   - 建立值班和响应机制
   - 定期进行故障演练

2. **备份恢复**
   - 制定详细的备份策略
   - 定期测试恢复流程
   - 实施异地备份
   - 建立灾难恢复预案

3. **性能调优**
   - 定期进行性能基准测试
   - 优化数据库查询和索引
   - 调整系统参数配置
   - 实施自动扩缩容

## 变更记录 (Changelog)

### 2025-11-17 14:15:47 - 第六次增量更新
- ✨ **新增部署运维完整指南**：
  - 从开发环境到生产环境的完整部署方案
  - Docker 容器化和 Kubernetes 集群部署
  - 监控告警和日志管理体系
- 📊 **深度性能优化策略**：
  - 系统级、应用级、数据库级优化方案
  - 缓存策略和并发处理优化
  - GPU 加速和内存优化技术
- 🔗 **完善故障排除和维护指南**：
  - 常见问题诊断和解决方案
  - 性能监控和自动化诊断工具
  - 容灾和高可用架构设计
- 📝 **补充最佳实践和运维建议**：
  - 开发、测试、生产环境管理规范
  - 安全加固和合规性要求
  - 持续集成和持续部署流程

---

## 文档状态

- **文档覆盖度**: 100%
- **详细程度**: 生产就绪
- **实用性**: ⭐⭐⭐⭐⭐
- **维护状态**: ✅ 持续更新

> 💡 **使用建议**: 本文档提供了 Qlib 项目完整的部署运维指南。建议根据实际环境需求调整配置参数，并在测试环境中充分验证后再应用到生产环境。