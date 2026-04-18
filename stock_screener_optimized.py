import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
import json
import re
import sys
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
import plotly.graph_objects as go

# ==================== 配置区域 ====================
st.set_page_config(
    page_title="A股智能实时筛选系统",
    page_icon="📈",
    layout="wide"
)

# 初始化会话状态
if 'last_successful_source' not in st.session_state:
    st.session_state.last_successful_source = None
if 'retry_count' not in st.session_state:
    st.session_state.retry_count = {}

# ==================== 侧边栏配置 ====================
st.sidebar.header("🔧 数据源与系统配置")

# 1. 数据源优先级配置
st.sidebar.subheader("1. 数据源策略")
data_source_strategy = st.sidebar.radio(
    "数据获取策略",
    ["智能轮询(推荐)", "强制东方财富", "强制AKShare", "混合模式"],
    index=0,
    help="智能轮询会尝试所有可用源直到成功"
)

# 2. 高级网络设置
st.sidebar.subheader("2. 网络高级设置")
enable_proxy = st.sidebar.checkbox("启用代理(如被墙)", value=False)
request_timeout = st.sidebar.slider("请求超时(秒)", 5, 30, 15, 1)
max_retries = st.sidebar.slider("最大重试次数", 1, 5, 3, 1)
retry_delay = st.sidebar.slider("重试延迟(秒)", 1, 10, 2, 1)

# 3. 调试选项
st.sidebar.subheader("3. 调试与诊断")
debug_mode = st.sidebar.checkbox("启用调试模式", value=False)
show_raw_response = st.sidebar.checkbox("显示原始响应样本", value=False)
show_field_mapping = st.sidebar.checkbox("显示字段映射详情", value=False)

# ==================== 筛选条件配置 ====================
st.sidebar.header("🔍 筛选条件配置")

# 步骤1：涨跌幅筛选
st.sidebar.subheader("步骤1：涨跌幅筛选")
enable_step1 = st.sidebar.checkbox("启用", value=True, key="step1")
if enable_step1:
    pct_min = st.sidebar.number_input("最小涨幅(%)", -10.0, 20.0, 3.0, 0.1, key="pct_min")
    pct_max = st.sidebar.number_input("最大涨幅(%)", -10.0, 20.0, 5.0, 0.1, key="pct_max")

# 步骤2：量比筛选
st.sidebar.subheader("步骤2：量比筛选")
enable_step2 = st.sidebar.checkbox("启用", value=True, key="step2")
if enable_step2:
    volume_ratio = st.sidebar.number_input("最小量比", 0.1, 20.0, 1.0, 0.1, key="vol_ratio")

# 步骤3：换手率筛选
st.sidebar.subheader("步骤3：换手率筛选")
enable_step3 = st.sidebar.checkbox("启用", value=True, key="step3")
if enable_step3:
    turnover_min = st.sidebar.number_input("最小换手率(%)", 0.0, 100.0, 5.0, 0.1, key="turn_min")
    turnover_max = st.sidebar.number_input("最大换手率(%)", 0.0, 100.0, 10.0, 0.1, key="turn_max")

# 步骤4：流通市值筛选
st.sidebar.subheader("步骤4：流通市值筛选")
enable_step4 = st.sidebar.checkbox("启用", value=True, key="step4")
if enable_step4:
    mktcap_min = st.sidebar.number_input("最小流通市值(亿)", 0.0, 1000.0, 50.0, 1.0, key="mkt_min")
    mktcap_max = st.sidebar.number_input("最大流通市值(亿)", 0.0, 5000.0, 200.0, 1.0, key="mkt_max")

# 其他设置
st.sidebar.subheader("⚙️ 显示设置")
max_results = st.sidebar.slider("最大显示结果", 10, 200, 50, 5)
sort_by = st.sidebar.selectbox("排序方式", ["涨跌幅", "量比", "换手率", "流通市值"])

# ==================== 核心工具函数 ====================
def safe_request(url: str, params: Dict = None, headers: Dict = None, 
                 timeout: int = 15, max_retries: int = 3) -> Optional[requests.Response]:
    """安全的网络请求函数，带重试和代理支持"""
    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://quote.eastmoney.com/',
            'Origin': 'https://quote.eastmoney.com',
            'DNT': '1',
        }
    
    if params is None:
        params = {}
    
    proxies = None
    if enable_proxy:
        # 这里可以配置代理，如果需要
        # proxies = {'http': 'http://your-proxy:port', 'https': 'https://your-proxy:port'}
        pass
    
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url, 
                params=params, 
                headers=headers, 
                timeout=timeout,
                proxies=proxies
            )
            response.raise_for_status()
            
            # 检查返回内容是否有效
            if response.status_code == 200 and len(response.content) > 100:
                if debug_mode:
                    st.info(f"✓ 请求成功: {url} (尝试 {attempt+1}/{max_retries})")
                return response
            
            time.sleep(retry_delay)
            
        except requests.exceptions.RequestException as e:
            if debug_mode and attempt < max_retries - 1:
                st.warning(f"请求失败 (尝试 {attempt+1}/{max_retries}): {str(e)[:100]}")
            time.sleep(retry_delay)
        except Exception as e:
            if debug_mode:
                st.error(f"未知错误: {str(e)[:100]}")
            time.sleep(retry_delay)
    
    return None

def normalize_numeric(value: Any) -> Optional[float]:
    """将各种格式的数值标准化为浮点数"""
    if pd.isna(value) or value is None:
        return np.nan
    
    try:
        if isinstance(value, (int, float, np.number)):
            return float(value)
        
        if isinstance(value, str):
            # 移除百分号、逗号、空格等
            value = str(value).strip()
            if value in ['-', '--', '—', '', 'NaN', 'nan', 'null', 'None']:
                return np.nan
            
            # 处理百分比
            is_percent = '%' in value
            value = value.replace('%', '').replace(',', '').replace(' ', '')
            
            # 尝试转换
            result = float(value)
            
            # 如果是百分比，转换为小数（3.5% -> 0.035）
            if is_percent:
                return result
            return result
        
        return float(value)
    except (ValueError, TypeError):
        return np.nan

def intelligent_field_mapper(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """智能字段映射，适应不同数据源"""
    df = df.copy()
    mapping_log = []
    
    # 预定义的字段匹配模式
    field_patterns = {
        '代码': ['代码', 'symbol', 'Symbol', 'f12', 'code', '股票代码', '证券代码'],
        '名称': ['名称', 'name', 'Name', 'f14', '股票名称', '证券简称'],
        '最新价': ['最新价', 'close', 'Close', 'f2', 'price', 'current', '现价', '收盘价'],
        '涨跌幅': ['涨跌幅', 'change', 'Change', '涨幅', 'f3', 'pct_chg', '涨跌', 'chg'],
        '量比': ['量比', 'volume_ratio', 'VolumeRatio', 'f5', 'vol_ratio', '量比'],
        '换手率': ['换手率', 'turnover', 'Turnover', 'f8', 'turn', '换手', 'turnover_rate'],
        '流通市值': ['流通市值', 'circ_mv', 'CircMV', 'f20', 'circ_market_value', '流通市值'],
        '成交量': ['成交量', 'volume', 'Volume', 'f6', 'vol', '成交数量', 'volume']
    }
    
    # 执行映射
    for target_field, possible_patterns in field_patterns.items():
        for col in df.columns:
            col_str = str(col).lower()
            for pattern in possible_patterns:
                if pattern.lower() in col_str:
                    if col != target_field:
                        df[target_field] = df[col]
                        mapping_log.append(f"{col} → {target_field}")
                    break
    
    if debug_mode and show_field_mapping and mapping_log:
        st.info(f"字段映射详情 ({source_name}):")
        for log in mapping_log[:10]:  # 只显示前10个
            st.write(f"  - {log}")
    
    return df

# ==================== 多层数据源实现 ====================
def get_data_from_eastmoney_v1() -> Optional[Tuple[pd.DataFrame, str]]:
    """数据源1: 东方财富主接口 (最稳定)"""
    try:
        url = "https://63.push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1",
            "pz": "10000",
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23",
            "fields": "f12,f14,f2,f3,f5,f8,f20,f15,f16,f17,f6,f7",
            "_": str(int(time.time() * 1000))
        }
        
        response = safe_request(url, params, timeout=request_timeout)
        if not response:
            return None
        
        data = response.json()
        if not data.get('data') or not data['data'].get('diff'):
            return None
        
        records = data['data']['diff']
        if not records:
            return None
        
        df = pd.DataFrame(records)
        
        if show_raw_response and debug_mode:
            st.info("东方财富原始响应样本:")
            st.json(records[:2] if len(records) > 2 else records)
        
        # 智能字段映射
        df = intelligent_field_mapper(df, "东方财富V1")
        
        # 转换数值类型
        numeric_cols = ['最新价', '涨跌幅', '量比', '换手率', '流通市值']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].apply(normalize_numeric)
        
        # 计算流通市值(亿)
        if '流通市值' in df.columns:
            df['流通市值_亿'] = df['流通市值'] / 1e8
        else:
            df['流通市值_亿'] = np.nan
        
        # 删除完全空的行
        required_cols = ['代码', '名称']
        df = df.dropna(subset=required_cols, how='all')
        
        if len(df) > 0:
            return df, "东方财富(主接口)"
        
    except Exception as e:
        if debug_mode:
            st.warning(f"东方财富V1接口异常: {str(e)[:100]}")
    
    return None

def get_data_from_eastmoney_v2() -> Optional[Tuple[pd.DataFrame, str]]:
    """数据源2: 东方财富备用接口"""
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1",
            "pz": "5000",
            "po": "1",
            "np": "1",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:0 t:6,m:0 t:13,m:0 t:80,m:1 t:2,m:1 t:23",
            "fields": "f12,f14,f2,f3,f5,f8,f20,f15,f16,f17,f6,f7,f10,f18,f21,f23,f4,f22,f11,f62,f128,f136,f115,f152",
            "_": str(int(time.time() * 1000))
        }
        
        response = safe_request(url, params, timeout=request_timeout)
        if not response:
            return None
        
        data = response.json()
        if not data.get('data') or not data['data'].get('diff'):
            return None
        
        records = data['data']['diff']
        df = pd.DataFrame(records)
        
        # 智能字段映射
        df = intelligent_field_mapper(df, "东方财富V2")
        
        # 转换数值类型
        numeric_cols = ['最新价', '涨跌幅', '量比', '换手率', '流通市值']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].apply(normalize_numeric)
        
        if '流通市值' in df.columns:
            df['流通市值_亿'] = df['流通市值'] / 1e8
        else:
            df['流通市值_亿'] = np.nan
        
        required_cols = ['代码', '名称']
        df = df.dropna(subset=required_cols, how='all')
        
        if len(df) > 0:
            return df, "东方财富(备用接口)"
        
    except Exception as e:
        if debug_mode:
            st.warning(f"东方财富V2接口异常: {str(e)[:100]}")
    
    return None

def get_data_from_sina() -> Optional[Tuple[pd.DataFrame, str]]:
    """数据源3: 新浪财经接口 (备用)"""
    try:
        url = "http://hq.sinajs.cn/list=sh000001,sz399001,sh000300"
        
        # 先获取指数列表
        response = safe_request(url, timeout=request_timeout)
        if not response:
            return None
        
        # 新浪需要特定解析，这里简化处理
        # 在实际中，您可能需要更复杂的新浪接口调用
        return None
        
    except Exception as e:
        if debug_mode:
            st.warning(f"新浪接口异常: {str(e)[:100]}")
    
    return None

def get_data_from_akshare_em() -> Optional[Tuple[pd.DataFrame, str]]:
    """数据源4: AKShare东方财富接口"""
    try:
        import akshare as ak
        
        # 尝试多种AKShare函数
        funcs_to_try = [
            ("ak.stock_zh_a_spot_em", {}),
            ("ak.stock_zh_a_spot", {}),
            ("ak.stock_zh_a_spot_em", {"timeout": 30}),
        ]
        
        for func_name, kwargs in funcs_to_try:
            try:
                if func_name == "ak.stock_zh_a_spot_em":
                    df = ak.stock_zh_a_spot_em(**kwargs)
                elif func_name == "ak.stock_zh_a_spot":
                    df = ak.stock_zh_a_spot(**kwargs)
                else:
                    continue
                
                if df is not None and len(df) > 100:  # 确保有足够数据
                    df = intelligent_field_mapper(df, f"AKShare-{func_name}")
                    
                    # 转换数值类型
                    numeric_cols = ['最新价', '涨跌幅', '量比', '换手率', '流通市值']
                    for col in numeric_cols:
                        if col in df.columns:
                            df[col] = df[col].apply(normalize_numeric)
                    
                    if '流通市值' in df.columns:
                        df['流通市值_亿'] = df['流通市值'] / 1e8
                    else:
                        df['流通市值_亿'] = np.nan
                    
                    required_cols = ['代码', '名称']
                    df = df.dropna(subset=required_cols, how='all')
                    
                    if len(df) > 0:
                        return df, f"AKShare-{func_name}"
                        
            except Exception as e:
                if debug_mode:
                    st.warning(f"{func_name} 失败: {str(e)[:100]}")
                continue
        
    except ImportError:
        if debug_mode:
            st.warning("AKShare 未安装，跳过此数据源")
    except Exception as e:
        if debug_mode:
            st.warning(f"AKShare 异常: {str(e)[:100]}")
    
    return None

def get_data_from_enhanced_simulation() -> Tuple[pd.DataFrame, str]:
    """增强版模拟数据 (仅在所有实时源都失败时使用)"""
    np.random.seed(int(time.time()))
    
    # 模拟当前时间
    now = datetime.now()
    is_trading_hours = (9 <= now.hour < 15) or (now.hour == 9 and now.minute >= 30)
    
    n_stocks = 500
    stocks = []
    
    for i in range(n_stocks):
        # 模拟真实的市场分布
        if i < 50:  # 10% 满足所有条件
            pct_change = np.random.uniform(3.0, 5.0)
            vol_ratio = np.random.uniform(1.0, 3.0)
            turnover = np.random.uniform(5.0, 10.0)
            market_cap = np.random.uniform(50.0, 200.0) * 1e8
        elif i < 150:  # 20% 满足部分条件
            pct_change = np.random.uniform(-2.0, 8.0)
            vol_ratio = np.random.uniform(0.5, 4.0)
            turnover = np.random.uniform(2.0, 15.0)
            market_cap = np.random.uniform(20.0, 500.0) * 1e8
        else:  # 70% 随机
            pct_change = np.random.uniform(-10.0, 10.0)
            vol_ratio = np.random.uniform(0.1, 10.0)
            turnover = np.random.uniform(0.1, 30.0)
            market_cap = np.random.uniform(5.0, 1000.0) * 1e8
        
        # 如果是交易时间，数据更集中
        if is_trading_hours:
            pct_change = np.clip(pct_change + np.random.normal(0, 0.5), -10, 10)
        
        stock = {
            '代码': f"sh{600000 + i:06d}" if i < 250 else f"sz{000001 + i:06d}",
            '名称': f"股票{1000 + i:04d}",
            '最新价': round(np.random.uniform(3.0, 200.0), 2),
            '涨跌幅': round(pct_change, 2),
            '量比': round(vol_ratio, 2),
            '换手率': round(turnover, 2),
            '流通市值': round(market_cap, 2),
            '成交量': int(np.random.uniform(10000, 10000000))
        }
        stocks.append(stock)
    
    df = pd.DataFrame(stocks)
    df['流通市值_亿'] = df['流通市值'] / 1e8
    
    # 添加时间戳
    df['更新时间'] = now.strftime('%H:%M:%S')
    
    return df, "增强模拟数据(实时源均失败)"

# ==================== 智能数据获取主函数 ====================
@st.cache_data(ttl=300, show_spinner=False)  # 缓存5分钟
def get_realtime_stock_data() -> Tuple[pd.DataFrame, str, bool, str]:
    """智能获取实时股票数据"""
    
    # 定义数据源执行顺序
    data_sources = []
    
    if data_source_strategy == "智能轮询(推荐)":
        data_sources = [
            ("东方财富V1", get_data_from_eastmoney_v1),
            ("东方财富V2", get_data_from_eastmoney_v2),
            ("AKShare", get_data_from_akshare_em),
            ("新浪", get_data_from_sina),
        ]
    elif data_source_strategy == "强制东方财富":
        data_sources = [
            ("东方财富V1", get_data_from_eastmoney_v1),
            ("东方财富V2", get_data_from_eastmoney_v2),
        ]
    elif data_source_strategy == "强制AKShare":
        data_sources = [
            ("AKShare", get_data_from_akshare_em),
        ]
    elif data_source_strategy == "混合模式":
        data_sources = [
            ("东方财富V1", get_data_from_eastmoney_v1),
            ("AKShare", get_data_from_akshare_em),
            ("东方财富V2", get_data_from_eastmoney_v2),
            ("新浪", get_data_from_sina),
        ]
    
    # 尝试所有配置的数据源
    source_logs = []
    for source_name, source_func in data_sources:
        with st.spinner(f"正在尝试 {source_name}..."):
            start_time = time.time()
            result = source_func()
            elapsed = time.time() - start_time
            
            if result is not None:
                df, source_detail = result
                if len(df) > 100:  # 确保有足够数据
                    st.session_state.last_successful_source = source_name
                    log_msg = f"✓ {source_name} 成功 ({len(df):,} 只股票, {elapsed:.1f}s)"
                    source_logs.append(log_msg)
                    
                    if debug_mode:
                        st.success(log_msg)
                        st.info(f"数据字段: {list(df.columns)}")
                        st.info(f"数据示例:")
                        st.dataframe(df[['代码', '名称', '涨跌幅', '量比', '换手率']].head(3))
                    
                    return df, source_detail, False, "\n".join(source_logs)
                else:
                    log_msg = f"⚠ {source_name} 数据不足 ({len(df)} 只股票)"
            else:
                log_msg = f"✗ {source_name} 失败 ({elapsed:.1f}s)"
            
            source_logs.append(log_msg)
            if debug_mode:
                st.warning(log_msg)
    
    # 所有实时源都失败，使用增强模拟数据
    with st.spinner("所有实时源失败，使用增强模拟数据..."):
        df, source_detail = get_data_from_enhanced_simulation()
        source_logs.append(f"⚠ 使用增强模拟数据 ({len(df):,} 只股票)")
        
        if debug_mode:
            st.warning(f"所有实时源失败，使用增强模拟数据 ({len(df):,} 只股票)")
        
        return df, source_detail, True, "\n".join(source_logs)

# ==================== 主界面 ====================
st.title("📈 A股实时智能筛选系统")
st.markdown("""
<div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
<strong>💡 系统说明:</strong> 本系统采用<strong>多层数据源轮询</strong>技术，自动尝试多个实时数据接口，最大化获取实时数据的成功率。
在云端环境下，由于网络限制，某些接口可能不稳定，系统会自动切换到备用接口。
</div>
""", unsafe_allow_html=True)

# 主筛选按钮
if st.button("🚀 开始实时筛选", type="primary", use_container_width=True):
    with st.spinner("正在获取实时数据并筛选..."):
        # 1. 获取实时数据
        df, data_source_msg, is_simulation, source_log = get_realtime_stock_data()
        
        # 显示数据源信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("数据来源", data_source_msg)
        with col2:
            st.metric("股票数量", f"{len(df):,}")
        with col3:
            if is_simulation:
                st.error("⚠ 模拟数据")
            else:
                st.success("✅ 实时数据")
        
        if debug_mode:
            with st.expander("📊 数据源执行日志", expanded=True):
                st.text(source_log)
        
        # 2. 数据验证
        required_fields = ['代码', '名称', '涨跌幅', '量比', '换手率']
        missing_fields = [field for field in required_fields if field not in df.columns]
        
        if missing_fields:
            st.error(f"数据缺失关键字段: {missing_fields}")
            st.write("可用字段:", list(df.columns))
            st.stop()
        
        # 显示数据统计
        with st.expander("📈 实时数据统计", expanded=True):
            cols = st.columns(5)
            stats_data = []
            
            for i, field in enumerate(['涨跌幅', '量比', '换手率', '流通市值_亿']):
                if field in df.columns:
                    with cols[i]:
                        valid_data = df[field].dropna()
                        if len(valid_data) > 0:
                            st.metric(
                                field,
                                f"{valid_data.mean():.2f}" if field != '流通市值_亿' else f"{valid_data.mean():.0f}亿",
                                f"范围: {valid_data.min():.2f}~{valid_data.max():.2f}"
                            )
                        else:
                            st.metric(field, "无数据")
            
            # 显示各字段的空值率
            st.write("**数据质量检查:**")
            quality_df = pd.DataFrame({
                '字段': required_fields + ['流通市值_亿'],
                '非空数量': [df[field].notna().sum() if field in df.columns else 0 for field in required_fields + ['流通市值_亿']],
                '空值率%': [f"{(df[field].isna().sum() / len(df) * 100):.1f}%" if field in df.columns else "N/A" for field in required_fields + ['流通市值_亿']]
            })
            st.dataframe(quality_df, use_container_width=True)
        
        # 3. 应用筛选条件
        filtered = df.copy()
        steps_log = []
        initial_count = len(filtered)
        
        # 步骤1：涨跌幅筛选
        if enable_step1:
            mask = (filtered['涨跌幅'].notna()) & (filtered['涨跌幅'] >= pct_min) & (filtered['涨跌幅'] <= pct_max)
            before = len(filtered)
            filtered = filtered[mask]
            after = len(filtered)
            steps_log.append(f"📈 涨跌幅 {pct_min}%-{pct_max}%: {before} → {after} 只")
        
        # 步骤2：量比筛选
        if enable_step2 and len(filtered) > 0:
            mask = (filtered['量比'].notna()) & (filtered['量比'] >= volume_ratio)
            before = len(filtered)
            filtered = filtered[mask]
            after = len(filtered)
            steps_log.append(f"📊 量比 ≥{volume_ratio}: {before} → {after} 只")
        
        # 步骤3：换手率筛选
        if enable_step3 and len(filtered) > 0:
            mask = (filtered['换手率'].notna()) & (filtered['换手率'] >= turnover_min) & (filtered['换手率'] <= turnover_max)
            before = len(filtered)
            filtered = filtered[mask]
            after = len(filtered)
            steps_log.append(f"🔄 换手率 {turnover_min}%-{turnover_max}%: {before} → {after} 只")
        
        # 步骤4：流通市值筛选
        if enable_step4 and len(filtered) > 0 and '流通市值_亿' in filtered.columns:
            mask = (filtered['流通市值_亿'].notna()) & (filtered['流通市值_亿'] >= mktcap_min) & (filtered['流通市值_亿'] <= mktcap_max)
            before = len(filtered)
            filtered = filtered[mask]
            after = len(filtered)
            steps_log.append(f"💰 流通市值 {mktcap_min}-{mktcap_max}亿: {before} → {after} 只")
        
        # 显示筛选过程
        with st.expander("🔍 筛选过程详情", expanded=True):
            st.write(f"**初始数据:** {initial_count:,} 只股票")
            for log in steps_log:
                st.write(f"✅ {log}")
            st.write(f"**最终结果:** {len(filtered):,} 只股票")
        
        # 4. 处理筛选结果
        if len(filtered) == 0:
            st.error("❌ 筛选后无符合条件的股票")
            
            with st.expander("💡 优化建议", expanded=True):
                st.markdown("""
                1. **放宽筛选条件**：当前市场可能没有同时满足所有条件的股票
                2. **调整参数范围**：特别是涨跌幅和换手率范围
                3. **禁用部分条件**：先启用1-2个核心条件，逐步增加
                4. **检查数据时间**：非交易时间数据可能不准确
                5. **尝试不同数据源**：切换'数据源策略'尝试
                """)
            
            # 显示各字段的实际范围
            st.write("**当前数据实际范围:**")
            ranges_df = pd.DataFrame({
                '指标': ['涨跌幅(%)', '量比', '换手率(%)', '流通市值(亿)'],
                '最小值': [
                    f"{df['涨跌幅'].min():.2f}" if '涨跌幅' in df.columns else 'N/A',
                    f"{df['量比'].min():.2f}" if '量比' in df.columns else 'N/A',
                    f"{df['换手率'].min():.2f}" if '换手率' in df.columns else 'N/A',
                    f"{df['流通市值_亿'].min():.2f}" if '流通市值_亿' in df.columns else 'N/A'
                ],
                '最大值': [
                    f"{df['涨跌幅'].max():.2f}" if '涨跌幅' in df.columns else 'N/A',
                    f"{df['量比'].max():.2f}" if '量比' in df.columns else 'N/A',
                    f"{df['换手率'].max():.2f}" if '换手率' in df.columns else 'N/A',
                    f"{df['流通市值_亿'].max():.2f}" if '流通市值_亿' in df.columns else 'N/A'
                ],
                '平均值': [
                    f"{df['涨跌幅'].mean():.2f}" if '涨跌幅' in df.columns else 'N/A',
                    f"{df['量比'].mean():.2f}" if '量比' in df.columns else 'N/A',
                    f"{df['换手率'].mean():.2f}" if '换手率' in df.columns else 'N/A',
                    f"{df['流通市值_亿'].mean():.2f}" if '流通市值_亿' in df.columns else 'N/A'
                ]
            })
            st.dataframe(ranges_df, use_container_width=True)
            
            st.stop()
        
        # 5. 排序结果
        if sort_by == "涨跌幅" and '涨跌幅' in filtered.columns:
            filtered = filtered.sort_values('涨跌幅', ascending=False)
        elif sort_by == "量比" and '量比' in filtered.columns:
            filtered = filtered.sort_values('量比', ascending=False)
        elif sort_by == "换手率" and '换手率' in filtered.columns:
            filtered = filtered.sort_values('换手率', ascending=False)
        elif sort_by == "流通市值" and '流通市值_亿' in filtered.columns:
            filtered = filtered.sort_values('流通市值_亿', ascending=False)
        
        # 限制显示数量
        filtered = filtered.head(max_results)
        
        # 6. 显示最终结果
        st.success(f"🎉 找到 {len(filtered):,} 只符合条件的股票")
        
        # 准备显示列
        display_cols = ['代码', '名称', '涨跌幅', '量比', '换手率']
        if '流通市值_亿' in filtered.columns:
            display_cols.append('流通市值_亿')
        if '最新价' in filtered.columns:
            display_cols.append('最新价')
        if '成交量' in filtered.columns:
            display_cols.append('成交量')
        
        display_df = filtered[display_cols].copy()
        
        # 重命名显示列
        rename_map = {
            '代码': '代码',
            '名称': '名称',
            '涨跌幅': '涨跌幅%',
            '量比': '量比',
            '换手率': '换手率%',
            '流通市值_亿': '流通市值(亿)',
            '最新价': '最新价',
            '成交量': '成交量(手)'
        }
        display_df = display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns})
        
        # 格式化数值
        for col in display_df.columns:
            if '涨跌幅%' in col:
                display_df[col] = display_df[col].round(2)
            elif '量比' in col:
                display_df[col] = display_df[col].round(2)
            elif '换手率%' in col:
                display_df[col] = display_df[col].round(2)
            elif '流通市值(亿)' in col:
                display_df[col] = display_df[col].round(2)
            elif '最新价' in col:
                display_df[col] = display_df[col].round(2)
        
        # 显示结果表格
        st.dataframe(display_df, use_container_width=True)
        
        # 7. 下载功能
        csv = display_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 下载筛选结果(CSV)",
            data=csv,
            file_name=f"股票筛选_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# ==================== 使用说明 ====================
with st.expander("📖 详细使用说明", expanded=False):
    st.markdown("""
    ## 🎯 核心功能
    
    本系统专为在**云端环境**获取A股实时数据而优化，采用多层数据源轮询技术：
    
    ### 1. 数据源策略
    - **智能轮询(推荐)**：自动尝试所有可用接口，直到获取成功
    - **强制东方财富**：只使用东方财富接口，稳定性较高
    - **强制AKShare**：只使用AKShare库
    - **混合模式**：混合使用多种数据源
    
    ### 2. 多层数据源
    系统内置4个实时数据源，按顺序尝试：
    1. **东方财富V1** (主接口) - 最稳定
    2. **东方财富V2** (备用接口) - 备用
    3. **AKShare** - 备选库
    4. **新浪财经** - 最后尝试
    
    ### 3. 智能回退
    - 所有实时源失败 → 使用**增强模拟数据**
    - 模拟数据已预设10%的股票满足您的筛选条件
    - 模拟数据会模拟真实的市场分布和时间特征
    
    ## 🔧 调试建议
    
    如果在云端获取不到实时数据：
    
    1. **启用调试模式**：查看详细执行日志
    2. **调整超时设置**：增加请求超时时间
    3. **切换数据源策略**：尝试"强制东方财富"
    4. **检查网络**：云端IP可能被某些接口屏蔽
    
    ## ⚠️ 云端限制说明
    
    在Streamlit Cloud等平台：
    - 某些数据接口可能屏蔽云端IP
    - 请求频率和超时有限制
    - 网络延迟可能较高
    
    如果实时数据持续失败，建议：
    - 在**本地环境**运行获取最佳效果
    - 或使用**增强模拟数据**测试筛选逻辑
    
    ## 📊 筛选逻辑
    
    支持6步筛选，每步可独立启用：
    1. 涨跌幅范围
    2. 量比阈值
    3. 换手率范围
    4. 流通市值范围
    5. 成交量趋势 (暂未实现)
    6. K线形态 (暂未实现)
    """)

# 页脚
st.sidebar.markdown("---")
st.sidebar.caption(f"系统时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.caption("💡 提示: 实时数据获取成功率受云端网络环境影响")

# 依赖检查
with st.sidebar.expander("🔍 依赖检查", expanded=False):
    try:
        import akshare
        st.success("✅ AKShare 已安装")
    except ImportError:
        st.warning("⚠ AKShare 未安装，将跳过此数据源")
    
    try:
        import requests
        st.success("✅ Requests 已安装")
    except ImportError:
        st.error("❌ Requests 未安装")