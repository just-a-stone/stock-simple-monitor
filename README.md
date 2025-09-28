# stock

使用 uv/uvx 初始化的 Python 工程骨架，固定 Python 版本为 3.8。

## 运行方式

- 一次性运行（不创建本地虚拟环境）：
  ```bash
  uv run -p 3.8 python -m stock -- hello
  ```

- 本地虚拟环境（推荐，位于 `.venv/`）：
  ```bash
  uv python install 3.8
  uv venv --python 3.8
  source .venv/bin/activate  # Windows 使用: .venv\\Scripts\\activate
  uv pip install -e .
  python -m stock -- hello
  ```

## IPO 数据抓取与分析（TuShare）

功能：定时拉取近 5 年新股 IPO 数据（TuShare `new_share` 接口），并按月统计发行数量与募集金额的变化趋势，结果输出为 CSV。

1) 配置 TuShare Token（任选其一）

```bash
export TUSHARE_TOKEN=你的token
# 或在命令中显式传入 --token
```

2) 运行一次（默认近 5 年）

```bash
uv run -p 3.8 python -m stock ipo once --token "$TUSHARE_TOKEN"
# 自定义时间范围（YYYYMMDD）
uv run -p 3.8 python -m stock ipo once --start 20200101 --end 20251231 --token "$TUSHARE_TOKEN"
```

输出文件：
- `data/ipo_raw.csv` 原始数据
- `data/ipo_monthly.csv` 月度聚合（列：`month`,`ipo_count`,`issue_amount_sum`,`funds_sum`）

3) 定时运行

```bash
# 每 24 小时运行一次（默认）
uv run -p 3.8 python -m stock ipo schedule --token "$TUSHARE_TOKEN"

# 或者每天固定时间（本地时区）
uv run -p 3.8 python -m stock ipo schedule --at 18:30 --token "$TUSHARE_TOKEN"

# 或自定义间隔（小时）
uv run -p 3.8 python -m stock ipo schedule --interval-hours 6 --token "$TUSHARE_TOKEN"
```

> 说明：TuShare `new_share` 字段中，`funds`（募集资金，单位通常为“亿元”）与 `amount`（发行数量，单位通常为“万股”）若存在会被聚合求和；聚合时按每个月统计：`ipo_count`（数量）、`issue_amount_sum`（发行数量总和）、`funds_sum`（募集资金总和）。

## 消息推送（Server酱 Turbo）

`ipo once` 执行后，会在“当前月份”的统计满足任一条件时推送微信订阅号通知：

- `ipo_count > 10`，或
- `funds_sum > 100`

配置 SendKey（任选其一）：

```bash
export SCT_SENDKEY=你的Server酱SendKey
# 或
export SERVERCHAN_SENDKEY=你的Server酱SendKey
```

推送内容：

- 标题：`YYYY-MM IPO提示`（标题最大 32 字符）
- 内容：月份、上市家数、募集资金合计、触发条件（支持 Markdown，最大 32KB）

> 接口：`https://sctapi.ftqq.com/<SendKey>.send?title=...&desp=...`

## 使用 uvx 运行开发工具

无需在本地环境安装工具，直接通过 uvx 执行：

```bash
uvx ruff check
uvx black src --check
uvx pytest -q
```

> 说明：`uvx` 主要用于“临时”运行工具；固定 Python 版本与创建虚拟环境通常由 `uv` 完成。项目中通过 `pyproject.toml` 的 `requires-python = "==3.8.*"` 明确约束 Python 版本。

## 项目结构

```
.
├── pyproject.toml      # 项目信息与 Python 版本要求
├── README.md
└── src/
    └── stock/
        ├── __init__.py
        └── __main__.py  # 入口：python -m stock
```

## 常用命令速查

```bash
# 锁定/更新依赖（当前无依赖，演示命令）
uv lock

# 安装依赖（含可编辑安装当前包）
uv pip install -e .

# 运行入口
uv run -p 3.8 python -m stock -- demo
```
