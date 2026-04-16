import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go

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
enable_step1 = st.sidebar.checkbox("启用", value=True)
if enable_step1:
    pct_min = st.sidebar.slider("最小涨幅(%)", 0.0, 10.0, 3.0, 0.1, key="pct_min")
    pct_max = st.sidebar.slider("最大涨幅(%)", 0.0, 10.0, 5.0, 0.1, key="pct_max")

# 步骤2：量比筛选
st.sidebar.subheader("步骤2：量比筛选")
enable_step2 = st.sidebar.checkbox("启用", value=True, key="step2")
if enable_step2:
    volume_ratio = st.sidebar.slider("最小量比", 0.5, 5.0, 1.0, 0.1, key="vol_ratio")

# 步骤3：换手率筛选
st.sidebar.subheader("步骤3：换手率筛选")
enable_step3 = st.sidebar.checkbox("启用", value=True, key="step3")
if enable_step3:
    turnover_min = st.sidebar.slider("最小换手率(%)", 0.0, 20.0, 5.0, 0.1, key="turn_min")
    turnover_max = st.sidebar.slider("最大换手率(%)", 0.0, 20.0, 10.0, 0.1, key="turn_max")

# 步骤4：流通市值筛选
st.sidebar.subheader("步骤4：流通市值筛选")
enable_step4 = st.sidebar.checkbox("启用", value=True, key="step4")
if enable_step4:
    mktcap_min = st.sidebar.slider("最小流通市值(亿元)", 10, 500, 50, 10, key="mkt_min")
    mktcap_max = st.sidebar.slider("最大流通市值(亿元)", 50, 1000, 200, 10, key="mkt_max")

# 步骤5：成交量趋势筛选
st.sidebar.subheader("步骤5：成交量趋势筛选")
enable_step5 = st.sidebar.checkbox("启用", value=False, key="step5")

# 步骤6：K线形态筛选
st.sidebar.subheader("步骤6：K线形态筛选")
enable_step6 = st.sidebar.checkbox("启用", value=False, key="step6")

# 其他设置
st.sidebar.subheader("其他设置")
max_results = st.sidebar.slider("最大显示结果", 10, 100, 30, 5, key="max_res")
sort_by = st.sidebar.selectbox("排序方式", ["涨跌幅", "量比", "换手率", "流通市值"], key="sort")

@st.cache_data(ttl=300)
def get_stock_data():
    """获取股票数据"""
    try:
        df = ak.stock_zh_a_spot_em()
        # 重命名列
        df = df.rename(columns={
            '代码': '代码',
            '名称': '名称',
            '最新价': '最新价',
            '涨跌幅': '涨跌幅',
            '量比': '量比',
            '换手率': '换手率',
            '流通市值': '流通市值',
            '总市值': '总市值',
            '成交量': '成交量'
        })
        
        # 转换为亿为单位
        df['流通市值_亿'] = df['流通市值'] / 1e8
        df['总市值_亿'] = df['总市值'] / 1e8
        
        return df
    except Exception as e:
        st.error(f"数据获取失败: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_kline_data(symbol, days=60):
    """获取K线数据"""
    try:
        # 清理代码
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
        
        if not df.empty and len(df) > 20:
            df['MA5'] = df['收盘'].rolling(5).mean()
            df['MA10'] = df['收盘'].rolling(10).mean()
            df['MA20'] = df['收盘'].rolling(20).mean()
            
        return df
    except:
        return pd.DataFrame()

# 筛选按钮
if st.sidebar.button("🚀 开始筛选", type="primary", use_container_width=True):
    with st.spinner("正在加载数据..."):
        # 获取数据
        df = get_stock_data()
        
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
                steps_log.append(f"涨跌幅筛选: {len(filtered)} 只")
            
            # 步骤2：量比筛选
            if enable_step2:
                mask = filtered['量比'] >= volume_ratio
                filtered = filtered[mask]
                steps_log.append(f"量比筛选: {len(filtered)} 只")
            
            # 步骤3：换手率筛选
            if enable_step3:
                mask = (filtered['换手率'] >= turnover_min) & (filtered['换手率'] <= turnover_max)
                filtered = filtered[mask]
                steps_log.append(f"换手率筛选: {len(filtered)} 只")
            
            # 步骤4：流通市值筛选
            if enable_step4:
                mask = (filtered['流通市值_亿'] >= mktcap_min) & (filtered['流通市值_亿'] <= mktcap_max)
                filtered = filtered[mask]
                steps_log.append(f"流通市值筛选: {len(filtered)} 只")
            
            # 步骤5和6需要历史数据，限制数量
            if len(filtered) > max_results * 3:
                filtered = filtered.head(max_results * 3)
            
            # 步骤5：成交量趋势筛选（简化版）
            if enable_step5 and len(filtered) > 0:
                keep_indices = []
                for idx, row in filtered.iterrows():
                    kline = get_kline_data(row['代码'], 20)
                    if len(kline) >= 5:
                        # 简单判断最近5天成交量是否递增
                        recent_vol = kline['成交量'].tail(5).values
                        if all(recent_vol[i] <= recent_vol[i+1] for i in range(4)):
                            keep_indices.append(idx)
                filtered = filtered.loc[keep_indices]
                steps_log.append(f"成交量趋势筛选: {len(filtered)} 只")
            
            # 步骤6：K线形态筛选（简化版）
            if enable_step6 and len(filtered) > 0:
                keep_indices = []
                for idx, row in filtered.iterrows():
                    kline = get_kline_data(row['代码'], 30)
                    if len(kline) >= 20:
                        latest = kline.iloc[-1]
                        # 简单判断均线是否多头排列
                        if latest['MA5'] > latest['MA10'] > latest['MA20']:
                            keep_indices.append(idx)
                filtered = filtered.loc[keep_indices]
                steps_log.append(f"K线形态筛选: {len(filtered)} 只")
            
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
            with st.expander("📋 筛选步骤详情"):
                for log in steps_log:
                    st.write(log)
            
            # 显示结果
            if len(filtered) > 0:
                st.success(f"✅ 找到 {len(filtered)} 只符合条件的股票")
                
                # 格式化显示
                display_df = filtered[[
                    '代码', '名称', '涨跌幅', '量比', 
                    '换手率', '流通市值_亿', '最新价', '成交量'
                ]].copy()
                display_df.columns = ['代码', '名称', '涨跌幅%', '量比', '换手率%', '流通市值(亿)', '最新价', '成交量']
                display_df['涨跌幅%'] = display_df['涨跌幅%'].round(2)
                display_df['量比'] = display_df['量比'].round(2)
                display_df['换手率%'] = display_df['换手率%'].round(2)
                display_df['流通市值(亿)'] = display_df['流通市值(亿)'].round(2)
                display_df['最新价'] = display_df['最新价'].round(2)
                
                st.dataframe(display_df, use_container_width=True)
                
                # 下载功能
                csv = display_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下载结果(CSV)",
                    data=csv,
                    file_name=f"股票筛选_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
                
                # 股票详情
                if len(filtered) > 0:
                    st.subheader("📈 股票详情")
                    selected = st.selectbox(
                        "选择股票查看K线图",
                        options=[f"{row['名称']} ({row['代码']})" for _, row in filtered.iterrows()]
                    )
                    
                    if selected:
                        code = selected.split('(')[-1].rstrip(')')
                        kline_data = get_kline_data(code, 60)
                        
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
                                template="plotly_white"
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("没有找到符合条件的股票，请调整筛选条件。")

# 使用说明
with st.expander("📖 使用说明", expanded=False):
    st.markdown("""
    ### 使用步骤：
    1. 在左侧边栏配置筛选条件（六步筛选均可独立启用/禁用）
    2. 点击"开始筛选"按钮运行筛选
    3. 查看筛选结果和股票详情
    
    ### 注意事项：
    - 数据来源：AKShare，有15分钟左右延迟
    - 筛选条件可根据需要灵活调整
    - 历史数据获取需要时间，请耐心等待
    - 投资有风险，决策需谨慎
    """)

# 页脚
st.sidebar.markdown("---")
st.sidebar.caption("数据更新于: " + datetime.now().strftime("%Y-%m-%d %H:%M"))
