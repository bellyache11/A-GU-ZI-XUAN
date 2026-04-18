import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import time
import random
import requests
import json
import re

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
    ["模拟数据(稳定)", "备用数据源(推荐)", "AKShare数据源"],
    index=0,
    help="模拟数据100%稳定，备用数据源使用公开API，AKShare可能受网络限制"
)

# 侧边栏 - 调试选项
st.sidebar.header("🔍 调试选项")
show_data_info = st.sidebar.checkbox("显示数据信息", value=False, help="显示数据形状和列信息")
force_demo_data = st.sidebar.checkbox("强制使用模拟数据", value=False, help="无论选择什么数据源都使用模拟数据")

# 侧边栏 - 筛选条件
st.sidebar.header("🔧 筛选条件配置")

# 步骤1：涨跌幅筛选
st.sidebar.subheader("步骤1：涨跌幅筛选")
enable_step1 = st.sidebar.checkbox("启用", value=True, key="step1_enable")
if enable_step1:
    pct_min = st.sidebar.number_input("最小涨幅(%)", 0.0, 20.0, 3.0, 0.1, key="pct_min")
    pct_max = st.sidebar.number_input("最大涨幅(%)", 0.0, 20.0, 5.0, 0.1, key="pct_max")

# 步骤2：量比筛选
st.sidebar.subheader("步骤2：量比筛选")
enable_step2 = st.sidebar.checkbox("启用", value=True, key="step2_enable")
if enable_step2:
    volume_ratio = st.sidebar.number_input("最小量比", 0.5, 10.0, 1.0, 0.1, key="vol_ratio")

# 步骤3：换手率筛选
st.sidebar.subheader("步骤3：换手率筛选")
enable_step3 = st.sidebar.checkbox("启用", value=True, key="step3_enable")
if enable_step3:
    turnover_min = st.sidebar.number_input("最小换手率(%)", 0.0, 50.0, 5.0, 0.1, key="turn_min")
    turnover_max = st.sidebar.number_input("最大换手率(%)", 0.0, 50.0, 10.0, 0.1, key="turn_max")

# 步骤4：流通市值筛选
st.sidebar.subheader("步骤4：流通市值筛选")
enable_step4 = st.sidebar.checkbox("启用", value=True, key="step4_enable")
if enable_step4:
    mktcap_min = st.sidebar.number_input("最小流通市值(亿元)", 1.0, 1000.0, 50.0, 1.0, key="mkt_min")
    mktcap_max = st.sidebar.number_input("最大流通市值(亿元)", 1.0, 2000.0, 200.0, 1.0, key="mkt_max")

# 步骤5：成交量趋势筛选
st.sidebar.subheader("步骤5：成交量趋势筛选")
enable_step5 = st.sidebar.checkbox("启用", value=False, key="step5_enable")

# 步骤6：K线形态筛选
st.sidebar.subheader("步骤6：K线形态筛选")
enable_step6 = st.sidebar.checkbox("启用", value=False, key="step6_enable")

# 其他设置
st.sidebar.header("⚙️ 其他设置")
max_results = st.sidebar.slider("最大显示结果", 10, 200, 50, 5, key="max_res")
sort_by = st.sidebar.selectbox("排序方式", ["涨跌幅", "量比", "换手率", "流通市值"], key="sort")

# ==================== 数据获取模块 ====================

def clean_percentage_string(value):
    """清理百分比字符串，转换为浮点数"""
    if pd.isna(value):
        return np.nan
    
    try:
        # 如果是字符串，移除百分号
        if isinstance(value, str):
            value = value.replace('%', '').replace(' ', '')
        
        # 转换为浮点数
        return float(value)
    except:
        return np.nan

def clean_numeric_string(value):
    """清理数值字符串，转换为浮点数"""
    if pd.isna(value):
        return np.nan
    
    try:
        if isinstance(value, str):
            # 移除逗号、空格等
            value = value.replace(',', '').replace(' ', '')
            # 如果是百分数，特殊处理
            if '%' in value:
                return clean_percentage_string(value)
        return float(value)
    except:
        return np.nan

def generate_demo_data():
    """生成高质量的演示数据"""
    np.random.seed(int(time.time()))
    n_stocks = 300
    
    stocks = []
    
    for i in range(n_stocks):
        # 生成股票代码和名称
        if i < 150:
            code = f"sh600{100+i:03d}"
            name = f"沪市股票{i+1:03d}"
        else:
            code = f"sz002{i-50:03d}"
            name = f"深市股票{i-149:03d}"
        
        # 随机生成涨跌幅，但确保有一部分在3-5%之间
        if i < 50:  # 前50只股票满足3-5%条件
            pct_change = round(np.random.uniform(3.0, 5.0), 2)
        else:
            pct_change = round(np.random.uniform(-5.0, 10.0), 2)
        
        # 随机生成量比，但确保有一部分大于1
        if i < 100:  # 前100只股票量比大于1
            vol_ratio = round(np.random.uniform(1.0, 5.0), 2)
        else:
            vol_ratio = round(np.random.uniform(0.5, 5.0), 2)
        
        # 随机生成换手率，但确保有一部分在5-10%之间
        if i < 80:  # 前80只股票换手率在5-10%之间
            turnover = round(np.random.uniform(5.0, 10.0), 2)
        else:
            turnover = round(np.random.uniform(1.0, 20.0), 2)
        
        # 随机生成流通市值，但确保有一部分在50-200亿之间
        if i < 120:  # 前120只股票市值在50-200亿之间
            circ_mv = round(np.random.uniform(50.0, 200.0) * 1e8, 2)
        else:
            circ_mv = round(np.random.uniform(10.0, 500.0) * 1e8, 2)
        
        stock = {
            '代码': code,
            '名称': name,
            '最新价': round(np.random.uniform(5.0, 100.0), 2),
            '涨跌幅': pct_change,
            '量比': vol_ratio,
            '换手率': turnover,
            '流通市值': circ_mv,
            '成交量': int(np.random.uniform(10000, 1000000)),
            '成交额': round(np.random.uniform(1000000, 100000000), 2)
        }
        stocks.append(stock)
    
    df = pd.DataFrame(stocks)
    
    # 计算衍生字段
    df['流通市值_亿'] = df['流通市值'] / 1e8
    df['总市值_亿'] = df['流通市值_亿'] * np.random.uniform(1.2, 2.0, len(df))
    
    # 打乱顺序
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    return df

@st.cache_data(ttl=300)
def get_data_from_eastmoney():
    """从东方财富获取数据 - 主用数据源"""
    try:
        # 使用多个接口尝试获取
        urls = [
            "https://push2.eastmoney.com/api/qt/clist/get",
            "https://63.push2.eastmoney.com/api/qt/clist/get"
        ]
        
        for url_idx, url in enumerate(urls):
            try:
                params = {
                    "pn": "1",
                    "pz": "5000",
                    "po": "1",
                    "np": "1",
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                    "fltt": "2",
                    "invt": "2",
                    "fid": "f3",
                    "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23",
                    "fields": "f12,f14,f2,f3,f5,f8,f20,f15,f16,f17,f6,f7,f10,f18,f21,f23,f4,f22",
                    "_": str(int(time.time() * 1000))
                }
                
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("data") and data["data"].get("diff"):
                        records = data["data"]["diff"]
                        df = pd.DataFrame(records)
                        
                        # 定义字段映射
                        field_mapping = {
                            'f12': '代码',
                            'f14': '名称',
                            'f2': '最新价',
                            'f3': '涨跌幅',
                            'f5': '量比',
                            'f8': '换手率',
                            'f20': '流通市值_亿',
                            'f4': '昨收',
                            'f6': '成交额',
                            'f7': '振幅',
                            'f10': '行业',
                            'f15': '最高',
                            'f16': '最低',
                            'f17': '今开',
                            'f18': '换手率(实)',
                            'f21': '市净率',
                            'f22': '市盈率',
                            'f23': '市销率'
                        }
                        
                        # 重命名列
                        rename_dict = {}
                        for field, col_name in field_mapping.items():
                            if field in df.columns:
                                rename_dict[field] = col_name
                        
                        df = df.rename(columns=rename_dict)
                        
                        # 确保必要的列存在
                        required_columns = ['代码', '名称', '涨跌幅', '量比', '换手率']
                        
                        # 如果缺少必要列，尝试另一个接口
                        missing_cols = [col for col in required_columns if col not in df.columns]
                        if missing_cols:
                            continue
                        
                        # 清理和转换数据
                        numeric_columns = ['最新价', '涨跌幅', '量比', '换手率', '流通市值_亿', '成交额']
                        
                        for col in numeric_columns:
                            if col in df.columns:
                                df[col] = df[col].apply(clean_numeric_string)
                        
                        # 确保流通市值存在
                        if '流通市值_亿' in df.columns:
                            df['流通市值'] = df['流通市值_亿'] * 1e8
                        else:
                            df['流通市值'] = np.nan
                            df['流通市值_亿'] = np.nan
                        
                        # 删除完全为空的行
                        df = df.dropna(subset=['代码', '名称'])
                        
                        if not df.empty:
                            return df, f"东方财富数据(接口{url_idx+1})"
                        
            except Exception as e:
                continue
        
        return None, "所有东方财富接口都失败"
        
    except Exception as e:
        return None, f"东方财富数据获取失败: {str(e)[:100]}"

@st.cache_data(ttl=300)
def get_data_from_akshare():
    """从AKShare获取数据"""
    try:
        import akshare as ak
        
        # 尝试多个AKShare接口
        try:
            df = ak.stock_zh_a_spot_em()
            source_name = "AKShare(东方财富)"
        except:
            df = ak.stock_zh_a_spot()
            source_name = "AKShare(新浪)"
        
        if df is None or df.empty:
            return None, f"{source_name}返回空数据"
        
        # 标准化列名
        column_mapping = {}
        actual_columns = list(df.columns)
        
        # 常见列名模式
        patterns = {
            '代码': ['代码', 'symbol', 'Symbol', 'CODE'],
            '名称': ['名称', 'name', 'Name', '股票名'],
            '最新价': ['最新价', 'close', 'Close', 'price', 'Price', 'current', 'Current'],
            '涨跌幅': ['涨跌幅', 'change', 'Change', '涨跌', '涨幅', 'pct', 'Pct', 'chg'],
            '量比': ['量比', 'volume_ratio', 'VolumeRatio', 'vol_ratio'],
            '换手率': ['换手率', 'turnover', 'Turnover', 'turn', '换手'],
            '流通市值': ['流通市值', 'circ_mv', 'CircMV', '流通市值', 'circ市值'],
            '成交量': ['成交量', 'volume', 'Volume', 'vol', '成交']
        }
        
        # 匹配列名
        for target_col, possible_names in patterns.items():
            for col in actual_columns:
                if any(pattern in str(col) for pattern in possible_names):
                    column_mapping[col] = target_col
                    break
        
        df = df.rename(columns=column_mapping)
        
        # 清理数据
        numeric_cols = ['最新价', '涨跌幅', '量比', '换手率', '流通市值', '成交量']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].apply(clean_numeric_string)
        
        # 计算流通市值（亿）
        if '流通市值' in df.columns:
            df['流通市值_亿'] = df['流通市值'] / 1e8
        else:
            df['流通市值_亿'] = np.nan
        
        return df, source_name
        
    except Exception as e:
        return None, f"AKShare失败: {str(e)[:100]}"

@st.cache_data(ttl=300)
def get_stock_data(source_type, force_demo=False):
    """获取股票数据的主函数"""
    if force_demo or source_type == "模拟数据(稳定)":
        df = generate_demo_data()
        return df, "模拟数据", True
    
    if source_type == "备用数据源(推荐)":
        df, msg = get_data_from_eastmoney()
        if df is not None and not df.empty:
            return df, msg, False
    
    if source_type == "AKShare数据源":
        df, msg = get_data_from_akshare()
        if df is not None and not df.empty:
            return df, msg, False
    
    # 所有数据源都失败，回退到模拟数据
    st.warning("所有数据源都失败了，使用模拟数据")
    df = generate_demo_data()
    return df, "模拟数据(回退)", True

# ==================== K线数据获取 ====================

@st.cache_data(ttl=300)
def get_kline_data(symbol, days=60, use_demo=False):
    """获取K线数据"""
    if use_demo:
        # 生成模拟K线数据
        dates = pd.date_range(end=datetime.now(), periods=days, freq='B')
        n = len(dates)
        
        # 生成随机但合理的价格序列
        base_price = np.random.uniform(10, 50)
        trend = np.random.choice([-0.002, 0, 0.002])
        
        closes = [base_price]
        for i in range(1, n):
            change = np.random.normal(trend, 0.02)
            new_price = closes[-1] * (1 + change)
            closes.append(max(0.1, new_price))
        
        closes = np.array(closes)
        
        # 生成OHLC
        opens = closes * np.random.uniform(0.98, 1.02, n)
        highs = closes * np.random.uniform(1.01, 1.05, n)
        lows = closes * np.random.uniform(0.95, 0.99, n)
        
        df = pd.DataFrame({
            '日期': dates,
            '开盘': opens,
            '最高': highs,
            '最低': lows,
            '收盘': closes,
            '成交量': np.random.randint(10000, 1000000, n)
        })
        
        # 计算移动平均线
        df['MA5'] = df['收盘'].rolling(5, min_periods=1).mean()
        df['MA10'] = df['收盘'].rolling(10, min_periods=1).mean()
        df['MA20'] = df['收盘'].rolling(20, min_periods=1).mean()
        
        return df
    
    # 真实K线数据获取
    try:
        import akshare as ak
        
        # 清理代码
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
            # 计算移动平均线
            if len(df) >= 5:
                df['MA5'] = df['收盘'].rolling(5, min_periods=1).mean()
            if len(df) >= 10:
                df['MA10'] = df['收盘'].rolling(10, min_periods=1).mean()
            if len(df) >= 20:
                df['MA20'] = df['收盘'].rolling(20, min_periods=1).mean()
        
        return df if df is not None else pd.DataFrame()
        
    except Exception as e:
        return pd.DataFrame()

# ==================== 筛选逻辑 ====================

def apply_filters(df, filters, is_demo=False):
    """应用筛选条件"""
    filtered = df.copy()
    steps_log = []
    
    # 步骤1：涨跌幅筛选
    if filters['enable_step1']:
        if '涨跌幅' in filtered.columns:
            # 处理NaN值
            valid_mask = filtered['涨跌幅'].notna()
            filtered_valid = filtered[valid_mask].copy()
            filtered_invalid = filtered[~valid_mask]
            
            # 应用筛选
            pct_mask = (filtered_valid['涨跌幅'] >= filters['pct_min']) & (filtered_valid['涨跌幅'] <= filters['pct_max'])
            before_count = len(filtered)
            filtered = pd.concat([filtered_valid[pct_mask], filtered_invalid])
            after_count = len(filtered)
            
            steps_log.append(f"涨跌幅筛选 ({filters['pct_min']}%-{filters['pct_max']}%): {before_count} → {after_count} 只")
            
            if show_data_info and after_count == 0:
                st.warning(f"涨跌幅数据范围: {filtered_valid['涨跌幅'].min():.2f}% ~ {filtered_valid['涨跌幅'].max():.2f}%")
        else:
            steps_log.append("⚠️ 涨跌幅筛选: 无涨跌幅数据，跳过此步骤")
    
    # 步骤2：量比筛选
    if filters['enable_step2'] and len(filtered) > 0:
        if '量比' in filtered.columns:
            valid_mask = filtered['量比'].notna()
            filtered_valid = filtered[valid_mask].copy()
            filtered_invalid = filtered[~valid_mask]
            
            vol_mask = filtered_valid['量比'] >= filters['volume_ratio']
            before_count = len(filtered)
            filtered = pd.concat([filtered_valid[vol_mask], filtered_invalid])
            after_count = len(filtered)
            
            steps_log.append(f"量比筛选 (≥{filters['volume_ratio']}): {before_count} → {after_count} 只")
        else:
            steps_log.append("⚠️ 量比筛选: 无量比数据，跳过此步骤")
    
    # 步骤3：换手率筛选
    if filters['enable_step3'] and len(filtered) > 0:
        if '换手率' in filtered.columns:
            valid_mask = filtered['换手率'].notna()
            filtered_valid = filtered[valid_mask].copy()
            filtered_invalid = filtered[~valid_mask]
            
            turn_mask = (filtered_valid['换手率'] >= filters['turnover_min']) & (filtered_valid['换手率'] <= filters['turnover_max'])
            before_count = len(filtered)
            filtered = pd.concat([filtered_valid[turn_mask], filtered_invalid])
            after_count = len(filtered)
            
            steps_log.append(f"换手率筛选 ({filters['turnover_min']}%-{filters['turnover_max']}%): {before_count} → {after_count} 只")
        else:
            steps_log.append("⚠️ 换手率筛选: 无换手率数据，跳过此步骤")
    
    # 步骤4：流通市值筛选
    if filters['enable_step4'] and len(filtered) > 0:
        if '流通市值_亿' in filtered.columns:
            valid_mask = filtered['流通市值_亿'].notna()
            filtered_valid = filtered[valid_mask].copy()
            filtered_invalid = filtered[~valid_mask]
            
            mkt_mask = (filtered_valid['流通市值_亿'] >= filters['mktcap_min']) & (filtered_valid['流通市值_亿'] <= filters['mktcap_max'])
            before_count = len(filtered)
            filtered = pd.concat([filtered_valid[mkt_mask], filtered_invalid])
            after_count = len(filtered)
            
            steps_log.append(f"流通市值筛选 ({filters['mktcap_min']}-{filters['mktcap_max']}亿元): {before_count} → {after_count} 只")
        else:
            steps_log.append("⚠️ 流通市值筛选: 无流通市值数据，跳过此步骤")
    
    # 步骤5：成交量趋势筛选
    if filters['enable_step5'] and len(filtered) > 0:
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
            steps_log.append(f"成交量趋势筛选: {before_count} → {after_count} 只")
        else:
            steps_log.append("⚠️ 成交量趋势筛选: 无股票满足条件")
    
    # 步骤6：K线形态筛选
    if filters['enable_step6'] and len(filtered) > 0:
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
            steps_log.append(f"K线形态筛选: {before_count} → {after_count} 只")
        else:
            steps_log.append("⚠️ K线形态筛选: 无股票满足条件")
    
    return filtered, steps_log

# ==================== 主程序 ====================

# 筛选按钮
if st.sidebar.button("🚀 开始筛选", type="primary", use_container_width=True):
    with st.spinner("正在加载数据..."):
        # 获取数据
        df, data_source_msg, is_demo = get_stock_data(data_source, force_demo_data)
        
        # 显示数据源信息
        st.sidebar.markdown(f"**数据源**: {data_source_msg}")
        if is_demo:
            st.sidebar.warning("⚠️ 当前使用模拟数据")
        else:
            st.sidebar.success("✅ 使用实时数据")
        
        if df.empty:
            st.error("无法获取股票数据，请检查网络连接或切换到模拟数据")
        else:
            initial_count = len(df)
            
            # 显示数据信息
            if show_data_info:
                with st.expander("📊 数据信息", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("股票数量", f"{initial_count:,}")
                    with col2:
                        st.metric("数据列数", len(df.columns))
                    with col3:
                        st.metric("数据大小", f"{df.memory_usage().sum()/1024/1024:.2f} MB")
                    
                    st.write("**数据列信息:**")
                    for col in df.columns:
                        non_null = df[col].notna().sum()
                        null_percent = (df[col].isna().sum() / len(df)) * 100
                        st.write(f"- {col}: {non_null} 非空 ({null_percent:.1f}% 为空)")
                    
                    st.write("**前5行数据:**")
                    st.dataframe(df.head(), use_container_width=True)
            
            # 准备筛选条件
            filters = {
                'enable_step1': enable_step1,
                'pct_min': pct_min,
                'pct_max': pct_max,
                'enable_step2': enable_step2,
                'volume_ratio': volume_ratio,
                'enable_step3': enable_step3,
                'turnover_min': turnover_min,
                'turnover_max': turnover_max,
                'enable_step4': enable_step4,
                'mktcap_min': mktcap_min,
                'mktcap_max': mktcap_max,
                'enable_step5': enable_step5,
                'enable_step6': enable_step6
            }
            
            # 应用筛选
            filtered, steps_log = apply_filters(df, filters, is_demo)
            
            # 显示筛选步骤
            with st.expander("📋 筛选步骤详情", expanded=True):
                st.write(f"初始股票数量: {initial_count:,} 只")
                for log in steps_log:
                    st.write(f"✅ {log}")
                st.write(f"**最终结果: {len(filtered):,} 只**")
            
            # 处理筛选结果
            if len(filtered) == 0:
                st.warning("⚠️ 筛选后无符合条件的股票，建议：")
                st.markdown("""
                1. **放宽筛选条件**：调整涨跌幅、量比、换手率等参数的取值范围
                2. **禁用部分筛选步骤**：取消勾选一些筛选条件
                3. **检查数据质量**：启用"显示数据信息"查看数据详情
                4. **切换数据源**：尝试使用"模拟数据"测试筛选逻辑
                """)
                
                # 显示数据统计信息
                with st.expander("🔍 数据统计信息", expanded=False):
                    st.write("**数值列统计:**")
                    numeric_cols = df.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) > 0:
                        stats_df = df[numeric_cols].describe()
                        st.dataframe(stats_df, use_container_width=True)
                
                st.stop()
            
            # 排序
            if sort_by == "涨跌幅" and '涨跌幅' in filtered.columns:
                filtered = filtered.sort_values('涨跌幅', ascending=False, na_position='last')
            elif sort_by == "量比" and '量比' in filtered.columns:
                filtered = filtered.sort_values('量比', ascending=False, na_position='last')
            elif sort_by == "换手率" and '换手率' in filtered.columns:
                filtered = filtered.sort_values('换手率', ascending=False, na_position='last')
            elif sort_by == "流通市值" and '流通市值_亿' in filtered.columns:
                filtered = filtered.sort_values('流通市值_亿', ascending=False, na_position='last')
            
            # 限制结果数量
            filtered = filtered.head(max_results)
            
            # 显示结果
            st.success(f"🎉 找到 {len(filtered):,} 只符合条件的股票")
            
            # 准备显示列
            display_cols = ['代码', '名称']
            if '涨跌幅' in filtered.columns:
                display_cols.append('涨跌幅')
            if '量比' in filtered.columns:
                display_cols.append('量比')
            if '换手率' in filtered.columns:
                display_cols.append('换手率')
            if '流通市值_亿' in filtered.columns:
                display_cols.append('流通市值_亿')
            if '最新价' in filtered.columns:
                display_cols.append('最新价')
            
            display_df = filtered[display_cols].copy()
            
            # 重命名列
            rename_map = {
                '代码': '代码',
                '名称': '名称',
                '涨跌幅': '涨跌幅%',
                '量比': '量比',
                '换手率': '换手率%',
                '流通市值_亿': '流通市值(亿)',
                '最新价': '最新价'
            }
            display_df = display_df.rename(columns=rename_map)
            
            # 格式化数值
            for col in display_df.columns:
                if '涨跌幅%' in col:
                    display_df[col] = display_df[col].round(2)
                elif '量比' in col:
                    display_df[col] = display_df[col].round(2)
                elif '换手率%' in col:
                    display_df[col] = display_df[col].round(2)
                elif '流通市值' in col:
                    display_df[col] = display_df[col].round(2)
                elif '最新价' in col:
                    display_df[col] = display_df[col].round(2)
            
            # 显示表格
            st.dataframe(display_df, use_container_width=True)
            
            # 下载功能
            csv = display_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 下载筛选结果(CSV)",
                data=csv,
                file_name=f"股票筛选_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            # 股票详情
            if len(filtered) > 0:
                st.subheader("📈 股票详情")
                selected_options = [f"{row['名称']} ({row['代码']})" for _, row in filtered.iterrows()]
                selected = st.selectbox("选择股票查看K线图", options=selected_options, key="stock_selector")
                
                if selected:
                    code = selected.split('(')[-1].rstrip(')')
                    kline_data = get_kline_data(code, 60, use_demo=is_demo)
                    
                    if not kline_data.empty and len(kline_data) > 0:
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
                        
                        # 添加均线
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
    1. **选择数据源**：推荐使用"模拟数据"测试功能，"备用数据源"获取实时数据
    2. **配置筛选条件**：六步筛选均可独立启用/禁用
    3. **点击开始筛选**：运行筛选流程
    4. **查看结果**：查看筛选结果和股票详情
    
    ### 数据源说明：
    - **模拟数据(稳定)**：本地生成的模拟数据，100%可用，适合测试
    - **备用数据源(推荐)**：使用公开API获取实时数据
    - **AKShare数据源**：使用AKShare库获取数据，可能受网络限制
    
    ### 常见问题解决：
    - **无符合条件的股票**：放宽筛选条件或减少筛选步骤
    - **数据获取失败**：切换到"模拟数据"或启用"强制使用模拟数据"
    - **数据显示异常**：启用"显示数据信息"查看数据详情
    
    ### 注意事项：
    - 实时数据可能有15分钟左右延迟
    - 筛选条件可根据需要灵活调整
    - 投资有风险，决策需谨慎
    """)

# 页脚
st.sidebar.markdown("---")
st.sidebar.caption(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.caption("💡 提示: 首次使用建议选择'模拟数据'测试功能")
