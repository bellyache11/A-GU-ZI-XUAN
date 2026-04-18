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

# 步骤6：K线形态筛选
st.sidebar.subheader("步骤6：K线形态筛选")
enable_step6 = st.sidebar.checkbox("启用", value=False, key="step6_enable")

# 其他设置
st.sidebar.subheader("其他设置")
max_results = st.sidebar.slider("最大显示结果", 10, 100, 30, 5, key="max_res")
sort_by = st.sidebar.selectbox("排序方式", ["涨跌幅", "量比", "换手率", "流通市值"], key="sort")

# 模拟数据生成函数
def generate_demo_data():
    """生成演示数据，用于测试和演示"""
    np.random.seed(42)
    n_stocks = 150
    
    stocks = []
    codes = [f"sh600{100+i:03d}" for i in range(75)] + [f"sz002{i:03d}" for i in range(75, 150)]
    names = [f"股票A{i}" for i in range(1, 76)] + [f"股票B{i}" for i in range(76, 151)]
    
    for i in range(n_stocks):
        stock = {
            '代码': codes[i],
            '名称': names[i],
            '最新价': round(np.random.uniform(5, 100), 2),
            '涨跌幅': round(np.random.uniform(-2, 8), 2),
            '量比': round(np.random.uniform(0.5, 5), 2),
            '换手率': round(np.random.uniform(3, 12), 2),
            '流通市值': round(np.random.uniform(30, 300) * 1e8, 2),
            '成交量': int(np.random.uniform(10000, 1000000))
        }
        stocks.append(stock)
    
    df = pd.DataFrame(stocks)
    df['流通市值_亿'] = df['流通市值'] / 1e8
    df['总市值_亿'] = df['流通市值_亿'] * 1.5
    return df

def get_data_from_akshare():
    """从AKShare获取数据（主数据源）"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        
        if df is None or df.empty:
            return None, "AKShare返回空数据"
        
        rename_map = {
            '代码': '代码',
            '名称': '名称',
            '最新价': '最新价',
            '涨跌幅': '涨跌幅',
            '量比': '量比',
            '换手率': '换手率',
            '流通市值': '流通市值',
            '总市值': '总市值',
            '成交量': '成交量'
        }
        
        rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=rename_map)
        
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
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1",
            "pz": "100",
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23",
            "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152",
            "_": str(int(time.time() * 1000))
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("data"):
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
                    'f15': '最高',
                    'f16': '最低',
                    'f17': '今开',
                    'f6': '成交额',
                    'f7': '振幅'
                }
                
                df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
                
                if '代码' in df.columns and '名称' in df.columns:
                    df['流通市值'] = df.get('流通市值_亿', 0) * 1e8
                    df['总市值_亿'] = df.get('流通市值_亿', 0) * 1.2
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
        dates = pd.date_range(end=datetime.now(), periods=days, freq='B')
        n = len(dates)
        
        base_price = np.random.uniform(10, 50)
        trend = np.random.choice([-0.001, 0, 0.001])
        prices = []
        
        for i in range(n):
            if i == 0:
                price = base_price
            else:
                change = np.random.normal(trend, 0.02)
                price = prices[-1] * (1 + change)
            prices.append(max(0.1, price))
        
        prices = np.array(prices)
        
        df = pd.DataFrame({
            '日期': dates,
            '开盘': prices * np.random.uniform(0.98, 1.02, n),
            '最高': prices * np.random.uniform(1.01, 1.05, n),
            '最低': prices * np.random.uniform(0.95, 0.99, n),
            '收盘': prices,
            '成交量': np.random.randint(10000, 1000000, n)
        })
        
        df['MA5'] = df['收盘'].rolling(5).mean()
        df['MA10'] = df['收盘'].rolling(10).mean()
        df['MA20'] = df['收盘'].rolling(20).mean()
        
        return df
    
    try:
        import akshare as ak
        if symbol.startswith(('sh', 'sz')):
            code = symbol[2:]
        else:
            code = symbol
            
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        if df is not None and not df.empty and len(df) > 20:
            df['MA5'] = df['收盘'].rolling(5).mean()
            df['MA10'] = df['收盘'].rolling(10).mean()
            df['MA20'] = df['收盘'].rolling(20).mean()
            
        return df if df is not None else pd.DataFrame()
    except Exception as e:
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
            initial_count = len(df)
            filtered = df.copy()
            steps_log = []
            
            # 步骤1：涨跌幅筛选
            if enable_step1:
                mask = (filtered['涨跌幅'] >= pct_min) & (filtered['涨跌幅'] <= pct_max)
                filtered = filtered[mask]
                steps_log.append(f"✅ 涨跌幅筛选 ({pct_min}%-{pct_max}%): {len(filtered)} 只")
            
            # 步骤2：量比筛选
            if enable_step2:
                mask = filtered['量比'] >= volume_ratio
                filtered = filtered[mask]
                steps_log.append(f"✅ 量比筛选 (≥{volume_ratio}): {len(filtered)} 只")
            
            # 步骤3：换手率筛选
            if enable_step3:
                mask = (filtered['换手率'] >= turnover_min) & (filtered['换手率'] <= turnover_max)
                filtered = filtered[mask]
                steps_log.append(f"✅ 换手率筛选 ({turnover_min}%-{turnover_max}%): {len(filtered)} 只")
            
            # 步骤4：流通市值筛选
            if enable_step4:
                mask = (filtered['流通市值_亿'] >= mktcap_min) & (filtered['流通市值_亿'] <= mktcap_max)
                filtered = filtered[mask]
                steps_log.append(f"✅ 流通市值筛选 ({mktcap_min}-{mktcap_max}亿元): {len(filtered)} 只")
            
            # 步骤5和6需要历史数据，限制数量
            if len(filtered) > max_results * 3:
                filtered = filtered.head(max_results * 3)
            
            # 步骤5：成交量趋势筛选
            if enable_step5 and len(filtered) > 0:
                keep_indices = []
                for idx, row in filtered.iterrows():
                    kline = get_kline_data(row['代码'], 20, use_demo=is_demo)
                    if len(kline) >= 5:
                        recent_vol = kline['成交量'].tail(5).values
                        if len(recent_vol) >= 5 and all(recent_vol[i] <= recent_vol[i+1] for i in range(len(recent_vol)-1)):
                            keep_indices.append(idx)
                if keep_indices:
                    filtered = filtered.loc[keep_indices]
                steps_log.append(f"✅ 成交量趋势筛选: {len(filtered)} 只")
            
            # 步骤6：K线形态筛选
            if enable_step6 and len(filtered) > 0:
                keep_indices = []
                for idx, row in filtered.iterrows():
                    kline = get_kline_data(row['代码'], 30, use_demo=is_demo)
                    if len(kline) >= 20:
                        latest = kline.iloc[-1]
                        if 'MA5' in kline.columns and 'MA10' in kline.columns and 'MA20' in kline.columns:
                            if latest['MA5'] > latest['MA10'] > latest['MA20']:
                                keep_indices.append(idx)
                if keep_indices:
                    filtered = filtered.loc[keep_indices]
                steps_log.append(f"✅ K线形态筛选: {len(filtered)} 只")
            
            # 排序
            if sort_by == "涨跌幅":
                filtered = filtered.sort_values('涨跌幅', ascending=False)
            elif sort_by == "量比":
                filtered = filtered.sort_values('量比', ascending=False)
            elif sort_by == "换手率":
                filtered = filtered.sort_values('换手率', ascending=False)
            elif sort_by == "流通市值":
                filtered = filtered.sort_values('流通市值_亿', ascending=False)
            
            # 限制结果数量
            filtered = filtered.head(max_results)
            
            # 显示筛选步骤日志
            with st.expander("📋 筛选步骤详情", expanded=True):
                st.write(f"初始股票数量: {initial_count} 只")
                for log in steps_log:
                    st.write(log)
            
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
                
                display_df = filtered[display_columns].copy()
                
                column_names = {
                    '代码': '代码',
                    '名称': '名称',
                    '涨跌幅': '涨跌幅%',
                    '量比': '量比',
                    '换手率': '换手率%',
                    '流通市值_亿': '流通市值(亿)',
                    '最新价': '最新价',
                    '成交量': '成交量'
                }
                display_df = display_df.rename(columns=column_names)
                
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
            else:
                st.warning("没有找到符合条件的股票，请调整筛选条件。")

# 使用说明
with st.expander("📖 使用说明", expanded=False):
    st.markdown("""
    ### 使用步骤：
    1. 在左侧边栏选择数据源（推荐"自动选择"）
    2. 配置筛选条件（六步筛选均可独立启用/禁用）
    3. 点击"开始筛选"按钮运行筛选
    4. 查看筛选结果和股票详情
    
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
