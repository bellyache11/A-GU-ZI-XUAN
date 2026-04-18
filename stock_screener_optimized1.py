import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import time
import random
import sys
import requests
from typing import Optional, Tuple

# 页面配置
st.set_page_config(
    page_title="A股智能筛选系统",
    page_icon="📈",
    layout="wide"
)

# 应用标题
st.title("📊 A股智能筛选系统")
st.markdown("根据自定义条件筛选A股股票，支持六步筛选流程")

# 侧边栏 - 数据源配置
st.sidebar.header("🔧 数据源配置")
data_source = st.sidebar.radio(
    "选择数据源",
    ["自动选择(推荐)", "模拟数据(稳定)", "备用数据源1", "备用数据源2"],
    index=0,
    help="自动选择会尝试多种数据源直到成功"
)

# 侧边栏 - 调试模式
st.sidebar.header("🔍 调试选项")
enable_debug = st.sidebar.checkbox("启用调试模式", value=False, help="显示详细筛选过程和原始数据")
show_raw_data = st.sidebar.checkbox("显示原始数据", value=False, help="显示获取的原始数据")
disable_strict_filters = st.sidebar.checkbox("放宽筛选条件", value=False, 
    help="当无结果时自动放宽条件(跳过成交量趋势和K线形态筛选)")

# 侧边栏 - 筛选条件
st.sidebar.header("🔧 筛选条件配置")

# 步骤1：涨跌幅筛选
st.sidebar.subheader("步骤1：涨跌幅筛选")
enable_step1 = st.sidebar.checkbox("启用", value=True, key="step1_enable")
if enable_step1:
    pct_min = st.sidebar.slider("最小涨幅(%)", 0.0, 10.0, 3.0, 0.1, key="pct_min")
    pct_max = st.sidebar.slider("最大涨幅(%)", 0.0, 10.0, 5.0, 0.1, key="pct_max")

# 步骤2：量比筛选
st.sidebar.subheader("步骤2：量比筛选")
enable_step2 = st.sidebar.checkbox("启用", value=True, key="step2_enable")
if enable_step2:
    volume_ratio = st.sidebar.slider("最小量比", 0.5, 5.0, 1.0, 0.1, key="vol_ratio")

# 步骤3：换手率筛选
st.sidebar.subheader("步骤3：换手率筛选")
enable_step3 = st.sidebar.checkbox("启用", value=True, key="step3_enable")
if enable_step3:
    turnover_min = st.sidebar.slider("最小换手率(%)", 0.0, 20.0, 5.0, 0.1, key="turn_min")
    turnover_max = st.sidebar.slider("最大换手率(%)", 0.0, 20.0, 10.0, 0.1, key="turn_max")

# 步骤4：流通市值筛选
st.sidebar.subheader("步骤4：流通市值筛选")
enable_step4 = st.sidebar.checkbox("启用", value=True, key="step4_enable")
if enable_step4:
    mktcap_min = st.sidebar.slider("最小流通市值(亿元)", 10, 500, 50, 10, key="mkt_min")
    mktcap_max = st.sidebar.slider("最大流通市值(亿元)", 50, 1000, 200, 10, key="mkt_max")

# 步骤5：成交量趋势筛选
st.sidebar.subheader("步骤5：成交量趋势筛选")
enable_step5 = st.sidebar.checkbox("启用", value=False, key="step5_enable")
if enable_step5 and not disable_strict_filters:
    volume_window = st.sidebar.slider("趋势观察窗口(天)", 3, 10, 5, 1, key="vol_win")

# 步骤6：K线形态筛选
st.sidebar.subheader("步骤6：K线形态筛选")
enable_step6 = st.sidebar.checkbox("启用", value=False, key="step6_enable")

# 其他设置
st.sidebar.subheader("其他设置")
max_results = st.sidebar.slider("最大显示结果", 10, 100, 30, 5, key="max_res")
sort_by = st.sidebar.selectbox("排序方式", ["涨跌幅", "量比", "换手率", "流通市值"], key="sort")

# 模拟数据生成函数 - 确保有一定数量满足条件的股票
def generate_demo_data():
    """生成演示数据，确保有一定数量满足默认条件的股票"""
    np.random.seed(42)
    n_stocks = 200
    
    stocks = []
    
    # 生成20%满足默认条件的股票
    n_good_stocks = int(n_stocks * 0.2)
    
    for i in range(n_stocks):
        if i < n_good_stocks:
            # 生成满足默认条件的股票
            stock = {
                '代码': f"sh600{100+i:03d}" if i < 100 else f"sz002{100+i:03d}",
                '名称': f"优质股{i+1:03d}",
                '最新价': round(np.random.uniform(10, 50), 2),
                '涨跌幅': round(np.random.uniform(pct_min, pct_max), 2),  # 在3-5%范围内
                '量比': round(np.random.uniform(volume_ratio, 3.0), 2),  # 大于1
                '换手率': round(np.random.uniform(turnover_min, turnover_max), 2),  # 5-10%
                '流通市值': round(np.random.uniform(mktcap_min, mktcap_max) * 1e8, 2),  # 50-200亿
                '成交量': int(np.random.uniform(100000, 1000000))
            }
        else:
            # 生成随机股票
            stock = {
                '代码': f"sh600{200+i:03d}" if i < 150 else f"sz002{200+i:03d}",
                '名称': f"普通股{i+1:03d}",
                '最新价': round(np.random.uniform(5, 100), 2),
                '涨跌幅': round(np.random.uniform(-10, 10), 2),
                '量比': round(np.random.uniform(0.5, 5), 2),
                '换手率': round(np.random.uniform(1, 20), 2),
                '流通市值': round(np.random.uniform(10, 500) * 1e8, 2),
                '成交量': int(np.random.uniform(10000, 1000000))
            }
        stocks.append(stock)
    
    df = pd.DataFrame(stocks)
    df['流通市值_亿'] = df['流通市值'] / 1e8
    df['总市值_亿'] = df['流通市值_亿'] * 1.5
    
    # 打乱顺序
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    return df

def get_data_from_akshare():
    """从AKShare获取数据（主数据源）"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        
        if df is None or df.empty:
            return None, "AKShare返回空数据"
        
        if enable_debug:
            st.info(f"AKShare原始数据形状: {df.shape}")
            st.info(f"AKShare列名: {list(df.columns)}")
        
        # 统一列名映射
        column_mapping = {}
        for col in df.columns:
            col_lower = str(col).lower()
            if '代码' in col_lower or 'symbol' in col_lower:
                column_mapping[col] = '代码'
            elif '名称' in col_lower or 'name' in col_lower:
                column_mapping[col] = '名称'
            elif '最新' in col_lower or 'close' in col_lower or 'price' in col_lower:
                column_mapping[col] = '最新价'
            elif '涨跌' in col_lower or 'pct' in col_lower or 'change' in col_lower:
                column_mapping[col] = '涨跌幅'
            elif '量比' in col_lower or 'volume_ratio' in col_lower:
                column_mapping[col] = '量比'
            elif '换手' in col_lower or 'turnover' in col_lower:
                column_mapping[col] = '换手率'
            elif '流通市值' in col_lower or 'circ_mv' in col_lower:
                column_mapping[col] = '流通市值'
            elif '总市值' in col_lower or 'total_mv' in col_lower:
                column_mapping[col] = '总市值'
            elif '成交' in col_lower and '量' in col_lower or 'volume' in col_lower:
                column_mapping[col] = '成交量'
        
        df = df.rename(columns=column_mapping)
        
        # 确保必要的列存在
        required_cols = ['代码', '名称', '涨跌幅', '量比', '换手率']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.warning(f"AKShare数据缺少列: {missing_cols}")
            return None, f"AKShare数据不完整，缺少{missing_cols}"
        
        # 转换数据类型
        numeric_cols = ['最新价', '涨跌幅', '量比', '换手率', '流通市值', '总市值', '成交量']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        if '流通市值' in df.columns:
            df['流通市值_亿'] = df['流通市值'] / 1e8
        else:
            df['流通市值_亿'] = np.nan
            
        if '总市值' in df.columns:
            df['总市值_亿'] = df['总市值'] / 1e8
        else:
            df['总市值_亿'] = np.nan
        
        return df, "AKShare数据"
    except Exception as e:
        return None, f"AKShare失败: {str(e)[:100]}"

def get_data_from_backup1():
    """备用数据源1：尝试从其他公开接口获取"""
    try:
        # 使用更稳定的接口
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1",
            "pz": "5000",  # 获取更多数据
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
        
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("data") and data["data"].get("diff"):
                records = data["data"]["diff"]
                df = pd.DataFrame(records)
                
                mapping = {
                    'f12': '代码',
                    'f14': '名称',
                    'f2': '最新价',
                    'f3': '涨跌幅',
                    'f5': '量比',
                    'f8': '换手率',
                    'f20': '流通市值_亿',
                }
                
                df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
                
                if '代码' in df.columns and '名称' in df.columns:
                    if '流通市值_亿' in df.columns:
                        df['流通市值'] = df['流通市值_亿'] * 1e8
                    else:
                        df['流通市值'] = np.nan
                        df['流通市值_亿'] = np.nan
                    
                    df['总市值_亿'] = df.get('流通市值_亿', 0) * 1.2
                    
                    # 转换数据类型
                    numeric_cols = ['最新价', '涨跌幅', '量比', '换手率', '流通市值_亿']
                    for col in numeric_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    return df, "备用数据源1(东方财富)"
        
        return None, "备用数据源1无数据"
    except Exception as e:
        return None, f"备用数据源1失败: {str(e)[:50]}"

def get_data_from_backup2():
    """备用数据源2：本地缓存或简单API"""
    try:
        df = generate_demo_data()
        df['数据源'] = '模拟数据增强版'
        return df, "模拟数据增强版"
    except Exception as e:
        return None, f"备用数据源2失败: {str(e)[:50]}"

@st.cache_data(ttl=300)
def get_stock_data(source_type="auto"):
    """获取股票数据，支持多层回退"""
    if source_type == "模拟数据(稳定)":
        df = generate_demo_data()
        return df, "模拟数据", True
    
    data_sources = []
    
    if source_type == "自动选择(推荐)":
        data_sources = [
            ("akshare", get_data_from_akshare),
            ("backup1", get_data_from_backup1),
            ("backup2", get_data_from_backup2)
        ]
    elif source_type == "备用数据源1":
        data_sources = [("backup1", get_data_from_backup1)]
    elif source_type == "备用数据源2":
        data_sources = [("backup2", get_data_from_backup2)]
    
    for source_name, source_func in data_sources:
        with st.spinner(f"正在尝试从{source_name}获取数据..."):
            result, msg = source_func()
            if result is not None and not result.empty:
                st.success(f"✓ 数据获取成功: {msg}")
                return result, msg, False
    
    st.warning("所有数据源都失败了，使用模拟数据")
    df = generate_demo_data()
    return df, "模拟数据(回退)", True

@st.cache_data(ttl=300)
def get_kline_data(symbol, days=60, use_demo=False):
    """获取K线数据"""
    if use_demo:
        # 为演示数据生成合理的K线
        dates = pd.date_range(end=datetime.now(), periods=days, freq='B')
        n = len(dates)
        
        # 生成有趋势的价格
        base_price = np.random.uniform(10, 50)
        
        # 随机选择趋势方向
        trend_type = np.random.choice(['up', 'down', 'flat'], p=[0.4, 0.3, 0.3])
        if trend_type == 'up':
            trend = np.random.uniform(0.001, 0.003)
        elif trend_type == 'down':
            trend = np.random.uniform(-0.003, -0.001)
        else:
            trend = 0
        
        prices = []
        volumes = []
        current_price = base_price
        
        for i in range(n):
            # 价格变化
            daily_change = np.random.normal(trend, 0.02)
            current_price = max(0.1, current_price * (1 + daily_change))
            prices.append(current_price)
            
            # 成交量，有一定趋势
            base_volume = np.random.randint(10000, 1000000)
            if trend_type == 'up' and i > n//2:
                volume = int(base_volume * np.random.uniform(1.2, 1.8))
            else:
                volume = base_volume
            volumes.append(volume)
        
        prices = np.array(prices)
        volumes = np.array(volumes)
        
        df = pd.DataFrame({
            '日期': dates,
            '开盘': prices * np.random.uniform(0.98, 1.02, n),
            '最高': prices * np.random.uniform(1.01, 1.05, n),
            '最低': prices * np.random.uniform(0.95, 0.99, n),
            '收盘': prices,
            '成交量': volumes
        })
        
        # 确保开盘<收盘的比例
        for i in range(n):
            if df.loc[i, '开盘'] > df.loc[i, '收盘']:
                # 交换
                df.loc[i, '开盘'], df.loc[i, '收盘'] = df.loc[i, '收盘'], df.loc[i, '开盘']
        
        df['MA5'] = df['收盘'].rolling(5, min_periods=1).mean()
        df['MA10'] = df['收盘'].rolling(10, min_periods=1).mean()
        df['MA20'] = df['收盘'].rolling(20, min_periods=1).mean()
        
        return df
    
    try:
        import akshare as ak
        if symbol.startswith(('sh', 'sz')):
            code = symbol[2:]
        else:
            code = symbol
            
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')
        
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        if df is not None and not df.empty:
            if len(df) >= 5:
                df['MA5'] = df['收盘'].rolling(5, min_periods=1).mean()
            if len(df) >= 10:
                df['MA10'] = df['收盘'].rolling(10, min_periods=1).mean()
            if len(df) >= 20:
                df['MA20'] = df['收盘'].rolling(20, min_periods=1).mean()
            
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        if enable_debug:
            st.warning(f"获取K线数据失败: {str(e)[:100]}")
        return pd.DataFrame()

# 筛选按钮
if st.sidebar.button("🚀 开始筛选", type="primary", use_container_width=True):
    with st.spinner("正在加载数据..."):
        df, data_source_msg, is_demo = get_stock_data(data_source)
        
        st.sidebar.markdown(f"**数据源**: {data_source_msg}")
        if is_demo:
            st.sidebar.warning("⚠️ 当前使用演示数据")
        else:
            st.sidebar.success("✅ 使用实时数据")
        
        if df.empty:
            st.error("无法获取股票数据")
        else:
            # 显示原始数据（调试用）
            if show_raw_data:
                with st.expander("📄 原始数据预览", expanded=False):
                    st.write(f"数据形状: {df.shape}")
                    st.write("前10行数据:")
                    st.dataframe(df.head(10))
                    st.write("数据列信息:")
                    st.write(df.dtypes)
                    st.write("数据统计信息:")
                    st.write(df.describe())
            
            initial_count = len(df)
            filtered = df.copy()
            steps_log = []
            
            # 步骤1：涨跌幅筛选
            if enable_step1:
                mask = (filtered['涨跌幅'] >= pct_min) & (filtered['涨跌幅'] <= pct_max)
                before_count = len(filtered)
                filtered = filtered[mask]
                after_count = len(filtered)
                steps_log.append(f"✅ 涨跌幅筛选 ({pct_min}%-{pct_max}%): {before_count} → {after_count} 只")
                
                if enable_debug and after_count == 0:
                    st.warning(f"涨跌幅筛选后无数据，涨跌幅范围: {filtered['涨跌幅'].min():.2f}% ~ {filtered['涨跌幅'].max():.2f}%")
            
            # 步骤2：量比筛选
            if enable_step2 and len(filtered) > 0:
                mask = filtered['量比'] >= volume_ratio
                before_count = len(filtered)
                filtered = filtered[mask]
                after_count = len(filtered)
                steps_log.append(f"✅ 量比筛选 (≥{volume_ratio}): {before_count} → {after_count} 只")
                
                if enable_debug and after_count == 0:
                    st.warning(f"量比筛选后无数据，量比范围: {filtered['量比'].min():.2f} ~ {filtered['量比'].max():.2f}")
            
            # 步骤3：换手率筛选
            if enable_step3 and len(filtered) > 0:
                mask = (filtered['换手率'] >= turnover_min) & (filtered['换手率'] <= turnover_max)
                before_count = len(filtered)
                filtered = filtered[mask]
                after_count = len(filtered)
                steps_log.append(f"✅ 换手率筛选 ({turnover_min}%-{turnover_max}%): {before_count} → {after_count} 只")
                
                if enable_debug and after_count == 0:
                    st.warning(f"换手率筛选后无数据，换手率范围: {filtered['换手率'].min():.2f}% ~ {filtered['换手率'].max():.2f}%")
            
            # 步骤4：流通市值筛选
            if enable_step4 and len(filtered) > 0:
                if '流通市值_亿' in filtered.columns:
                    mask = (filtered['流通市值_亿'] >= mktcap_min) & (filtered['流通市值_亿'] <= mktcap_max)
                    before_count = len(filtered)
                    filtered = filtered[mask]
                    after_count = len(filtered)
                    steps_log.append(f"✅ 流通市值筛选 ({mktcap_min}-{mktcap_max}亿元): {before_count} → {after_count} 只")
                    
                    if enable_debug and after_count == 0:
                        st.warning(f"流通市值筛选后无数据，流通市值范围: {filtered['流通市值_亿'].min():.2f}亿 ~ {filtered['流通市值_亿'].max():.2f}亿")
                else:
                    steps_log.append("⚠️ 流通市值筛选: 无流通市值数据，跳过此步骤")
            
            # 如果启用"放宽筛选条件"，则跳过步骤5和6
            actual_enable_step5 = enable_step5 and not disable_strict_filters
            actual_enable_step6 = enable_step6 and not disable_strict_filters
            
            # 步骤5和6需要历史数据，限制数量
            if len(filtered) > max_results * 3:
                filtered = filtered.head(max_results * 3)
            
            # 步骤5：成交量趋势筛选
            if actual_enable_step5 and len(filtered) > 0:
                keep_indices = []
                for idx, row in filtered.iterrows():
                    kline = get_kline_data(row['代码'], 20, use_demo=is_demo)
                    if len(kline) >= 5:
                        recent_vol = kline['成交量'].tail(5).values
                        if len(recent_vol) >= 5 and all(recent_vol[i] <= recent_vol[i+1] for i in range(len(recent_vol)-1)):
                            keep_indices.append(idx)
                if keep_indices:
                    before_count = len(filtered)
                    filtered = filtered.loc[keep_indices]
                    after_count = len(filtered)
                    steps_log.append(f"✅ 成交量趋势筛选: {before_count} → {after_count} 只")
                else:
                    steps_log.append("⚠️ 成交量趋势筛选: 无股票满足条件")
            
            # 步骤6：K线形态筛选
            if actual_enable_step6 and len(filtered) > 0:
                keep_indices = []
                for idx, row in filtered.iterrows():
                    kline = get_kline_data(row['代码'], 30, use_demo=is_demo)
                    if len(kline) >= 20:
                        latest = kline.iloc[-1]
                        if 'MA5' in kline.columns and 'MA10' in kline.columns and 'MA20' in kline.columns:
                            if latest['MA5'] > latest['MA10'] > latest['MA20']:
                                keep_indices.append(idx)
                if keep_indices:
                    before_count = len(filtered)
                    filtered = filtered.loc[keep_indices]
                    after_count = len(filtered)
                    steps_log.append(f"✅ K线形态筛选: {before_count} → {after_count} 只")
                else:
                    steps_log.append("⚠️ K线形态筛选: 无股票满足条件")
            
            # 如果筛选后无数据，提供建议
            if len(filtered) == 0:
                st.warning("⚠️ 筛选后无符合条件的股票，建议：")
                st.markdown("""
                1. **放宽筛选条件**：在侧边栏启用"放宽筛选条件"选项
                2. **调整筛选参数**：降低涨幅下限、量比要求等
                3. **禁用部分筛选步骤**：特别是成交量趋势和K线形态筛选
                4. **检查数据源**：尝试使用"模拟数据"测试筛选逻辑
                5. **减少筛选步骤**：只启用最重要的1-2个筛选条件
                """)
                
                # 显示各步骤的统计信息帮助调试
                if enable_debug:
                    with st.expander("🔍 各步骤数据统计（调试）"):
                        st.write("初始数据统计:")
                        st.write(df[['涨跌幅', '量比', '换手率']].describe())
                        
                        if '流通市值_亿' in df.columns:
                            st.write(f"流通市值范围: {df['流通市值_亿'].min():.2f}亿 ~ {df['流通市值_亿'].max():.2f}亿")
                
                st.stop()
            
            # 排序
            if sort_by == "涨跌幅":
                filtered = filtered.sort_values('涨跌幅', ascending=False)
            elif sort_by == "量比":
                filtered = filtered.sort_values('量比', ascending=False)
            elif sort_by == "换手率":
                filtered = filtered.sort_values('换手率', ascending=False)
            elif sort_by == "流通市值":
                if '流通市值_亿' in filtered.columns:
                    filtered = filtered.sort_values('流通市值_亿', ascending=False)
                else:
                    st.warning("无流通市值数据，按涨跌幅排序")
                    filtered = filtered.sort_values('涨跌幅', ascending=False)
            
            # 限制结果数量
            filtered = filtered.head(max_results)
            
            # 显示筛选步骤日志
            with st.expander("📋 筛选步骤详情", expanded=True):
                st.write(f"初始股票数量: {initial_count} 只")
                for log in steps_log:
                    st.write(log)
                st.write(f"最终结果: {len(filtered)} 只")
            
            # 显示结果
            if len(filtered) > 0:
                st.success(f"🎉 找到 {len(filtered)} 只符合条件的股票")
                
                # 格式化显示
                display_columns = ['代码', '名称', '涨跌幅', '量比', '换手率']
                if '流通市值_亿' in filtered.columns:
                    display_columns.append('流通市值_亿')
                if '最新价' in filtered.columns:
                    display_columns.append('最新价')
                if '成交量' in filtered.columns:
                    display_columns.append('成交量')
                
                # 确保列存在
                available_columns = [col for col in display_columns if col in filtered.columns]
                display_df = filtered[available_columns].copy()
                
                # 重命名显示列
                column_names = {
                    '代码': '代码',
                    '名称': '名称',
                    '涨跌幅': '涨跌幅%',
                    '量比': '量比',
                    '换手率': '换手率%',
                    '流通市值_亿': '流通市值(亿)',
                    '最新价': '最新价',
                    '成交量': '成交量(手)'
                }
                display_df = display_df.rename(columns={k: v for k, v in column_names.items() if k in display_df.columns})
                
                # 格式化数值
                if '涨跌幅%' in display_df.columns:
                    display_df['涨跌幅%'] = display_df['涨跌幅%'].round(2)
                if '量比' in display_df.columns:
                    display_df['量比'] = display_df['量比'].round(2)
                if '换手率%' in display_df.columns:
                    display_df['换手率%'] = display_df['换手率%'].round(2)
                if '流通市值(亿)' in display_df.columns:
                    display_df['流通市值(亿)'] = display_df['流通市值(亿)'].round(2)
                if '最新价' in display_df.columns:
                    display_df['最新价'] = display_df['最新价'].round(2)
                
                st.dataframe(display_df, use_container_width=True)
                
                # 下载功能
                csv = display_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下载结果(CSV)",
                    data=csv,
                    file_name=f"股票筛选_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                # 股票详情
                if len(filtered) > 0:
                    st.subheader("📈 股票详情")
                    selected = st.selectbox(
                        "选择股票查看K线图",
                        options=[f"{row['名称']} ({row['代码']})" for _, row in filtered.iterrows()],
                        key="stock_selector"
                    )
                    
                    if selected:
                        code = selected.split('(')[-1].rstrip(')')
                        kline_data = get_kline_data(code, 60, use_demo=is_demo)
                        
                        if not kline_data.empty:
                            fig = go.Figure(data=[
                                go.Candlestick(
                                    x=kline_data['日期'],
                                    open=kline_data['开盘'],
                                    high=kline_data['最高'],
                                    low=kline_data['最低'],
                                    close=kline_data['收盘'],
                                    name='K线'
                                )
                            ])
                            
                            if 'MA5' in kline_data.columns:
                                fig.add_trace(go.Scatter(
                                    x=kline_data['日期'], y=kline_data['MA5'],
                                    mode='lines', name='MA5',
                                    line=dict(color='orange', width=1)
                                ))
                            if 'MA10' in kline_data.columns:
                                fig.add_trace(go.Scatter(
                                    x=kline_data['日期'], y=kline_data['MA10'],
                                    mode='lines', name='MA10',
                                    line=dict(color='green', width=1)
                                ))
                            if 'MA20' in kline_data.columns:
                                fig.add_trace(go.Scatter(
                                    x=kline_data['日期'], y=kline_data['MA20'],
                                    mode='lines', name='MA20',
                                    line=dict(color='blue', width=1)
                                ))
                            
                            fig.update_layout(
                                title=f"{selected} K线图",
                                yaxis_title="价格",
                                xaxis_title="日期",
                                template="plotly_white",
                                height=500
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning("无法获取该股票的K线数据")

# 使用说明
with st.expander("📖 使用说明", expanded=False):
    st.markdown("""
    ### 使用步骤：
    1. 在左侧边栏选择数据源（推荐"自动选择"）
    2. 配置筛选条件（六步筛选均可独立启用/禁用）
    3. 点击"开始筛选"按钮运行筛选
    4. 查看筛选结果和股票详情
    
    ### 常见问题解决：
    - **无符合条件的股票**：启用"放宽筛选条件"或调整筛选参数
    - **数据获取失败**：切换到"模拟数据"测试功能
    - **筛选结果异常**：启用"调试模式"查看详细过程
    
    ### 数据源说明：
    - **自动选择(推荐)**：尝试多种数据源，确保最高可用性
    - **模拟数据(稳定)**：使用本地生成的模拟数据，100%可用
    - **备用数据源1/2**：尝试其他公开数据接口
    
    ### 部署建议：
    1. 首次部署时，建议先选择"模拟数据"测试功能
    2. 如果实时数据获取失败，会自动回退到模拟数据
    3. 在Streamlit Cloud部署时，网络限制较严，模拟数据最稳定
    
    ### 注意事项：
    - 实时数据可能有15分钟左右延迟
    - 筛选条件可根据需要灵活调整
    - 投资有风险，决策需谨慎
    """)

# 页脚
st.sidebar.markdown("---")
st.sidebar.caption(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
if disable_strict_filters:
    st.sidebar.caption("⚡ 放宽筛选条件已启用")
