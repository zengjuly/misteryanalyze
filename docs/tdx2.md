数据层设计方案（Hermes 开发指南）

目标：本地优先 + 过期回退。最小改动，贴合现有 tdx_local → akshare → baostock 框架。

1. 数据优先级（硬规则）

| 类型 | 优先本地路径 | 环境变量 / 配置 | 过期/缺失时 |
|------|-------------|-----------------|-------------|
| 日K | {TDX_HOME}/vipdoc/{sh\|sz\|bj}/lday/*.day | TDX_HOME 默认 /mnt/bigdata/tdx/files/new_tdx | akshare → baostock |
| 板块 | {TDX_HOME}/T0002/blocknew、hq_cache | 同上 | 原策略或空 |
| 财务 | {TDX_VIPDOC_DIR}/cw/gpcw* | TDX_VIPDOC_DIR 默认 /home/ai/ai_runner/stock/data/tdx_vipdoc | akshare → baostock |

禁止：财务从 TDX_HOME 读；日K/板块不强制依赖 TDX_VIPDOC_DIR（可推导）。

2. config.yaml 增量

tdx:
  home_dir: "/mnt/bigdata/tdx/files/new_tdx"      # TDX_HOME 覆盖
  vipdoc_dir: "/home/ai/ai_runner/stock/data/tdx_vipdoc"  # TDX_VIPDOC_DIR 覆盖；财务专用
日K：优先 {home_dir}/vipdoc；若 vipdoc_dir 下存在 lday 也可作日K源（可选）
  freshness:
    kline_max_age_days: 1
    block_max_age_days: 3
    financial_max_age_days: 30
  enable: true

路径解析优先级：
日K vipdoc：{home_dir}/vipdoc > 显式 vipdoc_dir（若含 lday）
财务：仅 vipdoc_dir（及子目录 cw/）
板块：仅 home_dir

3. 新鲜度判定

日K: 文件不存在 → 过期
     读末根K线日期  block_max_age_days → 过期

财务: 最新 gpcw 报告期落后 / mtime > financial_max_age_days → 过期

交易日历：用项目已有日历或简单「工作日」近似即可。

4. 模块改动清单

4.1 新建 data/tdx_path_resolver.py（小文件）

resolve_home() -> str
resolve_vipdoc_for_kline() -> str
resolve_vipdoc_for_fin() -> str  # = TDX_VIPDOC_DIR
is_kline_fresh(day_file, max_age_days) -> bool
is_file_fresh(path, max_age_days) -> bool

4.2 改 data/tdx_local_client.py

get_daily_data(code):
  path = day_file under resolve_vipdoc_for_kline()
  if not exists or not is_kline_fresh: return None
  return 现有 TdxIncremental 读盘逻辑

get_block_data():  # 新增
  从 {home}/T0002/blocknew 等读；不新鲜 return {}

get_financial_data(code):  # 财务
  仅扫 resolve_vipdoc_for_fin()/cw/
  不新鲜或无文件 return None
解析 gpcw：沿用项目现有尝试或简单返回状态，解析失败也 return None

财务不要从 home_dir 找。

4.3 改 multi_source_client.py / market_data_client.py

get_daily_data:
  df = tdx_local.get_daily_data(...)
  if df not empty: return df
  else: 原 fallback 链

get_financial_data:
  df = tdx_local.get_financial_data(...)  # 只走 VIPDOC
  if df not empty: return df
  else: 原 akshare/baostock 财务逻辑

板块同理

日志必打：[TDX本地-新鲜] / [TDX本地-过期→fallback:akshare]

5. 财务包说明（给下载脚本用）

来源：https://data.tdx.com.cn/vipdoc/tdxfin.zip 或增量  
  http://down.tdx.com.cn:8001/tdxfin/gpcw.txt + gpcwYYYYMMDD.zip
落地目录：仅 {TDX_VIPDOC_DIR}/cw/
不写入 TDX_HOME

日K包 hsjday.zip、股票包 tdxgp.zip 可解到 {home}/vipdoc 或现有流程，与财务分离。

6. 验收用例

本地日K新鲜 → 无网络请求，返回本地 df  
人为改旧 .day 末日期 → 走 akshare/baostock  
财务仅 VIPDOC 有包且新鲜 → 用本地；VIPDOC 无包 → 原策略  
TDX_HOME / TDX_VIPDOC_DIR 环境变量覆盖生效  
板块从 home 读；财务绝不读 home

7. 实现顺序（省 token）

tdx_path_resolver.py + config 两行  
tdx_local_client：日K 新鲜度 + 财务只读 VIPDOC + 板块可选  
multi_source：None/空则 fallback，加日志  
单测 3 条路径（新鲜/过期/财务隔离）

不改分析层、不改前端。保持现有 TdxIncremental、重采样、2000 条 trim 不动。



