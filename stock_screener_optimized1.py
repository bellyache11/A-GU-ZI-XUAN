import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import time
import random
from typing import Optional, Tuple
import sys

# 页面配置
st.set_page_config(
    page_title="A股智能筛选系统",
    page_icon="📈",
    layout="wide"
)

# 应用标题
st.title("📊 A股智能筛选系统")
st.markdown("根据自定义条件筛选A股股票，支持六步筛选流程")

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
use_demo_data = st.sidebar.checkbox("使用演示数据(当实时数据获取失败时)", value=False, key="use_demo")

# 模拟数据生成函数
def generate_demo_data():
    """生成演示数据，用于测试和演示"""
    np.random.seed(42)
    n_stocks = 100
    
    stocks = []
    codes = [f"sh600{100+i:03d}" for i in range(50)] + [f"sz002{i:03d}" for i in range(50, 100)]
    names = [f"股票{i}" for i in range(1, 101)]
    
    for i in range(n_stocks):
        stock = {
            '代码': codes[i],
            '名称': names[i],
            '最新价': round(np.random.uniform(5, 100), 2),
            '涨跌幅': round(np.random.uniform(-2, 8), 2),  # 有些在3-5%范围内
            '量比': round(np.random.uniform(0.5, 5), 2),
            '换手率': round(np.random.uniform(3, 12), 2),
            '流通市值': round(np.random.uniform(30, 300) * 1e8, 2),
            '成交量': int(np.random.uniform(10000, 1000000))
        }
        stocks.append(stock)
    
    df = pd.DataFrame(stocks)
    df['流通市值_亿'] = df['流通市值'] / 1e8
    df['总市值_亿'] = df['流通市值_亿'] * 1.5  # 简单估算
    return df

def safe_akshare_request(func_name, *args, max_retries=3, **kwargs):
    """安全的AKShare请求函数，带重试机制"""
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                # 随机延迟，避免请求过于频繁
                delay = random.uniform(1, 3)
                time.sleep(delay)
            
            if func_name == "stock_zh_a_spot_em":
                result = ak.stock_zh_a_spot_em()
            elif func_name == "stock_zh_a_hist":
                result = ak.stock_zh_a_hist(*args, **kwargs)
            else:
                raise ValueError(f"未知的函数名: {func_name}")
            
            return result
        except Exception as e:
            st.warning(f"第{attempt+1}次尝试获取数据失败: {str(e)[:100]}")
            if attempt == max_retries - 1:
                raise
    return None

@st.cache_data(ttl=300)
def get_stock_data(use_demo=False):
    """获取股票数据，带错误处理和演示数据回退"""
    if use_demo:
        st.info("正在使用演示数据...")
        return generate_demo_data()
    
    try:
        df = safe_akshare_request("stock_zh_a_spot_em")
        
        if df is None or df.empty:
            st.warning("实时数据获取失败，使用演示数据")
            return generate_demo_data()
        
        # 重命名列
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
        
        # 只重命名存在的列
        rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=rename_map)
        
        # 转换为亿为单位
        if '流通市值' in df.columns:
            df['流通市值_亿'] = df['流通市值'] / 1e8
        else:
            df['流通市值_亿'] = np.nan
            
        if '总市值' in df.columns:
            df['总市值_亿'] = df['总市值'] / 1e8
        else:
            df['总市值_亿'] = np.nan
        
        return df
    except Exception as e:
        st.error(f"数据获取失败，使用演示数据: {str(e)[:100]}")
        return generate_demo_data()

@st.cache_data(ttl=300)
def get_kline_data(symbol, days=60, use_demo=False):
    """获取K线数据，带演示数据生成"""
    if use_demo:
        # 生成演示K线数据
        dates = pd.date_range(end=datetime.now(), periods=days, freq='B')
        n = len(dates)
        
        # 模拟股价走势
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
        
        # 生成OHLC数据
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
        # 清理代码
        if symbol.startswith(('sh', 'sz')):
            code = symbol[2:]
        else:
            code = symbol
            
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        
        df = safe_akshare_request(
            "stock_zh_a_hist",
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
        # 获取数据
        df = get_stock_data(use_demo=use_demo_data)
        
        if df.empty:
            st.error("无法获取股票数据，请检查网络连接或使用演示数据")
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
                    kline = get_kline_data(row['代码'], 20, use_demo=use_demo_data)
                    if len(kline) >= 5:
                        # 简单判断最近5天成交量是否递增
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
                    kline = get_kline_data(row['代码'], 30, use_demo=use_demo_data)
                    if len(kline) >= 20:
                        latest = kline.iloc[-1]
                        # 判断均线是否多头排列
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
                
                # 重命名列
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
                        kline_data = get_kline_data(code, 60, use_demo=use_demo_data)
                        
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
            else:
                st.warning("没有找到符合条件的股票，请调整筛选条件。")

# 使用说明
with st.expander("📖 使用说明", expanded=False):
    st.markdown("""
    ### 使用步骤：
    1. 在左侧边栏配置筛选条件（六步筛选均可独立启用/禁用）
    2. 点击"开始筛选"按钮运行筛选
    3. 查看筛选结果和股票详情
    
    ### 故障排除：
    - 如果实时数据获取失败，请勾选"使用演示数据"选项
    - 演示数据为随机生成，仅用于测试筛选逻辑
    - 在Streamlit Cloud部署时，由于网络限制，可能需要使用演示数据
    
    ### 注意事项：
    - 数据来源：AKShare，有15分钟左右延迟
    - 在云端部署时，可能遇到网络限制，建议使用演示数据测试
    - 筛选条件可根据需要灵活调整
    - 投资有风险，决策需谨慎
    """)

# 页脚
st.sidebar.markdown("---")
st.sidebar.caption(f"数据更新于: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
if use_demo_data:
    st.sidebar.caption("⚠️ 当前使用演示数据")
else:
    st.sidebar.caption("🔗 使用实时数据")

# 添加一个清空缓存的按钮（用于开发调试）
if st.sidebar.button("🔄 清除缓存", type="secondary"):
    st.cache_data.clear()
    st.success("缓存已清除")
