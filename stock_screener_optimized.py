import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import time
import requests
import json
import sys

# 页面配置
st.set_page_config(
    page_title="A股智能筛选系统",
    page_icon="📈",
    layout="wide"
)

# 初始化session_state
if 'filter_params' not in st.session_state:
    st.session_state.filter_params = {
        'pct_min': 3.0,
        'pct_max': 5.0,
        'volume_ratio': 1.0,
        'turnover_min': 5.0,
        'turnover_max': 10.0,
        'mktcap_min': 50.0,
        'mktcap_max': 200.0
    }

# 应用标题
st.title("📊 A股智能筛选系统")
st.markdown("根据自定义条件筛选A股股票，支持六步筛选流程")

# 侧边栏 - 数据源配置
st.sidebar.header("🔧 数据源配置")
data_source = st.sidebar.radio(
    "选择数据源",
    ["模拟数据(100%稳定)", "备用数据源(东方财富)", "AKShare数据源"],
    index=0,
    help="推荐先使用模拟数据测试，再尝试实时数据"
)

# 侧边栏 - 调试选项
st.sidebar.header("🔍 调试选项")
show_data_stats = st.sidebar.checkbox("显示数据统计", value=True)
show_detailed_logs = st.sidebar.checkbox("详细日志", value=False)
show_raw_sample = st.sidebar.checkbox("显示原始样本", value=False)

# 侧边栏 - 筛选条件
st.sidebar.header("🔧 筛选条件配置")

# 步骤1：涨跌幅筛选
st.sidebar.subheader("步骤1：涨跌幅筛选")
enable_step1 = st.sidebar.checkbox("启用", value=True, key="step1_enable")
if enable_step1:
    st.session_state.filter_params['pct_min'] = st.sidebar.number_input(
        "最小涨幅(%)", 0.0, 20.0, 3.0, 0.1, key="pct_min"
    )
    st.session_state.filter_params['pct_max'] = st.sidebar.number_input(
        "最大涨幅(%)", 0.0, 20.0, 5.0, 0.1, key="pct_max"
    )

# 步骤2：量比筛选
st.sidebar.subheader("步骤2：量比筛选")
enable_step2 = st.sidebar.checkbox("启用", value=True, key="step2_enable")
if enable_step2:
    st.session_state.filter_params['volume_ratio'] = st.sidebar.number_input(
        "最小量比", 0.1, 20.0, 1.0, 0.1, key="vol_ratio"
    )

# 步骤3：换手率筛选
st.sidebar.subheader("步骤3：换手率筛选")
enable_step3 = st.sidebar.checkbox("启用", value=True, key="step3_enable")
if enable_step3:
    st.session_state.filter_params['turnover_min'] = st.sidebar.number_input(
        "最小换手率(%)", 0.0, 100.0, 5.0, 0.1, key="turn_min"
    )
    st.session_state.filter_params['turnover_max'] = st.sidebar.number_input(
        "最大换手率(%)", 0.0, 100.0, 10.0, 0.1, key="turn_max"
    )

# 步骤4：流通市值筛选
st.sidebar.subheader("步骤4：流通市值筛选")
enable_step4 = st.sidebar.checkbox("启用", value=True, key="step4_enable")
if enable_step4:
    st.session_state.filter_params['mktcap_min'] = st.sidebar.number_input(
        "最小流通市值(亿元)", 0.0, 1000.0, 50.0, 1.0, key="mkt_min"
    )
    st.session_state.filter_params['mktcap_max'] = st.sidebar.number_input(
        "最大流通市值(亿元)", 0.0, 5000.0, 200.0, 1.0, key="mkt_max"
    )

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

# ==================== 工具函数 ====================

def convert_to_float(x):
    """将各种格式的数据转换为浮点数"""
    if pd.isna(x):
        return np.nan
    
    try:
        # 如果是字符串
        if isinstance(x, str):
            # 移除百分号、逗号、空格
            x = x.replace('%', '').replace(',', '').replace(' ', '')
            # 处理特殊情况
            if x == '-' or x == '' or x == '--':
                return np.nan
        
        # 尝试转换为浮点数
        return float(x)
    except:
        return np.nan

def normalize_column_names(df, source_type):
    """统一列名，适应不同数据源"""
    df = df.copy()
    column_map = {}
    
    if source_type == "模拟数据":
        # 模拟数据已经是我们需要的格式
        return df
    
    # 查找可能的列名模式
    for col in df.columns:
        col_str = str(col).lower()
        
        # 匹配代码
        if any(pattern in col_str for pattern in ['代码', 'symbol', 'f12']):
            column_map[col] = '代码'
        # 匹配名称
        elif any(pattern in col_str for pattern in ['名称', 'name', 'f14']):
            column_map[col] = '名称'
        # 匹配最新价
        elif any(pattern in col_str for pattern in ['最新价', 'price', 'f2']):
            column_map[col] = '最新价'
        # 匹配涨跌幅
        elif any(pattern in col_str for pattern in ['涨跌幅', '涨幅', 'change', 'f3']):
            column_map[col] = '涨跌幅'
        # 匹配量比
        elif any(pattern in col_str for pattern in ['量比', 'volume_ratio', 'f5']):
            column_map[col] = '量比'
        # 匹配换手率
        elif any(pattern in col_str for pattern in ['换手率', 'turnover', 'turn', 'f8']):
            column_map[col] = '换手率'
        # 匹配流通市值
        elif any(pattern in col_str for pattern in ['流通市值', 'circ_mv', 'circ市值', 'f20']):
            column_map[col] = '流通市值'
        # 匹配成交量
        elif any(pattern in col_str for pattern in ['成交量', 'volume', 'vol', 'f6']):
            column_map[col] = '成交量'
    
    # 重命名列
    df = df.rename(columns=column_map)
    
    return df

def clean_and_convert_data(df, source_type):
    """清洗和转换数据"""
    df = df.copy()
    
    # 统一列名
    df = normalize_column_names(df, source_type)
    
    # 转换数值列
    numeric_columns = ['最新价', '涨跌幅', '量比', '换手率', '流通市值', '成交量']
    
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].apply(convert_to_float)
            if show_detailed_logs:
                st.info(f"{col}转换后示例: {df[col].iloc[:3].tolist() if len(df) > 3 else df[col].tolist()}")
    
    # 计算流通市值（亿元）
    if '流通市值' in df.columns:
        df['流通市值_亿'] = df['流通市值'] / 1e8
    else:
        df['流通市值_亿'] = np.nan
    
    return df

# ==================== 数据获取模块 ====================

def generate_simulated_data():
    """生成模拟数据，确保一定有符合条件的股票"""
    np.random.seed(42)
    n_stocks = 300
    
    stocks = []
    
    # 确保有30%的股票满足默认条件
    n_good_stocks = int(n_stocks * 0.3)  # 90只股票
    
    for i in range(n_stocks):
        if i < n_good_stocks:
            # 生成满足所有默认条件的股票
            stock = {
                '代码': f"sh600{i+1:06d}" if i < 150 else f"sz002{i-149:06d}",
                '名称': f"优质股{i+1:04d}",
                '最新价': round(np.random.uniform(10, 100), 2),
                '涨跌幅': round(np.random.uniform(3.0, 5.0), 2),  # 3-5%
                '量比': round(np.random.uniform(1.0, 3.0), 2),  # 大于1
                '换手率': round(np.random.uniform(5.0, 10.0), 2),  # 5-10%
                '流通市值': round(np.random.uniform(50, 200) * 1e8, 2),  # 50-200亿
                '成交量': int(np.random.uniform(100000, 1000000))
            }
        else:
            # 生成随机股票
            stock = {
                '代码': f"sh600{i+1000:06d}" if i < 150 else f"sz002{i-149+1000:06d}",
                '名称': f"普通股{i+1:04d}",
                '最新价': round(np.random.uniform(1, 200), 2),
                '涨跌幅': round(np.random.uniform(-10, 20), 2),
                '量比': round(np.random.uniform(0.1, 10), 2),
                '换手率': round(np.random.uniform(0.1, 50), 2),
                '流通市值': round(np.random.uniform(1, 1000) * 1e8, 2),
                '成交量': int(np.random.uniform(1000, 10000000))
            }
        stocks.append(stock)
    
    df = pd.DataFrame(stocks)
    df['流通市值_亿'] = df['流通市值'] / 1e8
    
    # 打乱顺序
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    return df

@st.cache_data(ttl=300)
def get_data_from_eastmoney():
    """从东方财富获取数据"""
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1",
            "pz": "10000",  # 获取大量数据
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
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("data") and data["data"].get("diff"):
                records = data["data"]["diff"]
                df = pd.DataFrame(records)
                
                if show_raw_sample and len(df) > 0:
                    st.info("原始数据样本（前3行）:")
                    st.dataframe(df.head(3))
                
                return df, True
            else:
                return None, "东方财富返回空数据"
        else:
            return None, f"HTTP错误: {response.status_code}"
            
    except Exception as e:
        return None, f"请求失败: {str(e)[:200]}"

@st.cache_data(ttl=300)
def get_data_from_akshare():
    """从AKShare获取数据"""
    try:
        import akshare as ak
        
        # 尝试多个接口
        try:
            df = ak.stock_zh_a_spot_em()
            source = "东方财富"
        except:
            df = ak.stock_zh_a_spot()
            source = "新浪"
        
        if df is None or df.empty:
            return None, f"{source}返回空数据"
        
        if show_raw_sample and len(df) > 0:
            st.info(f"AKShare原始数据样本（前3行）:")
            st.dataframe(df.head(3))
            st.info(f"列名: {list(df.columns)}")
        
        return df, True
        
    except Exception as e:
        return None, f"AKShare失败: {str(e)[:200]}"

def get_stock_data(source_type):
    """获取股票数据的主函数"""
    if source_type == "模拟数据(100%稳定)":
        df = generate_simulated_data()
        return clean_and_convert_data(df, "模拟数据"), "模拟数据", True
    
    elif source_type == "备用数据源(东方财富)":
        result, success = get_data_from_eastmoney()
        if success is True and result is not None:
            df = clean_and_convert_data(result, "东方财富")
            return df, "东方财富", False
        else:
            st.error(f"备用数据源获取失败: {success}")
            return None, f"失败: {success}", False
    
    elif source_type == "AKShare数据源":
        result, success = get_data_from_akshare()
        if success is True and result is not None:
            df = clean_and_convert_data(result, "AKShare")
            return df, "AKShare", False
        else:
            st.error(f"AKShare数据源获取失败: {success}")
            return None, f"失败: {success}", False
    
    return None, "未知数据源", False

# ==================== 筛选逻辑 ====================

def apply_filter_step(df, column, condition_str, step_name, step_num):
    """应用单个筛选步骤"""
    if column not in df.columns:
        return df, f"步骤{step_num}: 无{column}数据，跳过{step_name}"
    
    # 获取有效数据（非空）
    valid_data = df[column].dropna()
    if len(valid_data) == 0:
        return df, f"步骤{step_num}: {column}数据全为空，跳过{step_name}"
    
    # 应用筛选条件
    try:
        # 使用eval执行条件字符串
        mask = eval(f"df['{column}']{condition_str}", {'df': df, 'np': np})
        filtered = df[mask]
        
        before_count = len(df)
        after_count = len(filtered)
        
        if show_detailed_logs:
            st.info(f"{step_name} - {column}范围: {valid_data.min():.2f} ~ {valid_data.max():.2f}")
            st.info(f"{step_name} - 条件: {condition_str}")
        
        return filtered, f"步骤{step_num}: {step_name}: {before_count} → {after_count}只"
    except Exception as e:
        return df, f"步骤{step_num}: {step_name}错误: {str(e)[:100]}"

# ==================== 主程序 ====================

# 筛选按钮
if st.sidebar.button("🚀 开始筛选", type="primary", use_container_width=True):
    with st.spinner("正在获取数据..."):
        # 获取数据
        df, data_source_msg, is_demo = get_stock_data(data_source)
        
        if df is None or df.empty:
            st.error(f"无法从{data_source}获取数据，请切换到模拟数据测试")
            st.stop()
        
        # 显示数据源信息
        st.sidebar.markdown(f"**数据源**: {data_source_msg}")
        if is_demo:
            st.sidebar.warning("⚠️ 当前使用模拟数据")
        else:
            st.sidebar.success("✅ 使用实时数据")
        
        initial_count = len(df)
        
        # 显示数据统计
        if show_data_stats:
            with st.expander("📊 数据统计信息", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("总股票数", f"{initial_count:,}")
                with col2:
                    st.metric("数据列数", len(df.columns))
                with col3:
                    st.metric("数据大小", f"{df.memory_usage().sum()/1024/1024:.1f} MB")
                
                st.write("**关键字段统计:**")
                key_columns = ['代码', '名称', '涨跌幅', '量比', '换手率', '流通市值_亿']
                
                stats_data = []
                for col in key_columns:
                    if col in df.columns:
                        non_null = df[col].notna().sum()
                        null_pct = (df[col].isna().sum() / initial_count) * 100
                        
                        if non_null > 0 and col not in ['代码', '名称']:
                            col_min = df[col].min()
                            col_max = df[col].max()
                            col_mean = df[col].mean()
                            stats_data.append({
                                '字段': col,
                                '非空数': non_null,
                                '空值率%': f"{null_pct:.1f}%",
                                '最小值': f"{col_min:.2f}" if not pd.isna(col_min) else "NaN",
                                '最大值': f"{col_max:.2f}" if not pd.isna(col_max) else "NaN",
                                '平均值': f"{col_mean:.2f}" if not pd.isna(col_mean) else "NaN"
                            })
                        else:
                            stats_data.append({
                                '字段': col,
                                '非空数': non_null,
                                '空值率%': f"{null_pct:.1f}%",
                                '最小值': "-",
                                '最大值': "-",
                                '平均值': "-"
                            })
                
                stats_df = pd.DataFrame(stats_data)
                st.dataframe(stats_df, use_container_width=True)
        
        # 开始筛选
        filtered = df.copy()
        steps_log = []
        step_num = 1
        
        # 步骤1：涨跌幅筛选
        if enable_step1:
            condition = f">= {st.session_state.filter_params['pct_min']} and df['涨跌幅'] <= {st.session_state.filter_params['pct_max']}"
            filtered, log = apply_filter_step(
                filtered, '涨跌幅', condition, 
                f"涨跌幅筛选({st.session_state.filter_params['pct_min']}%-{st.session_state.filter_params['pct_max']}%)", 
                step_num
            )
            steps_log.append(log)
            step_num += 1
        
        # 步骤2：量比筛选
        if enable_step2 and len(filtered) > 0:
            condition = f">= {st.session_state.filter_params['volume_ratio']}"
            filtered, log = apply_filter_step(
                filtered, '量比', condition, 
                f"量比筛选(≥{st.session_state.filter_params['volume_ratio']})", 
                step_num
            )
            steps_log.append(log)
            step_num += 1
        
        # 步骤3：换手率筛选
        if enable_step3 and len(filtered) > 0:
            condition = f">= {st.session_state.filter_params['turnover_min']} and df['换手率'] <= {st.session_state.filter_params['turnover_max']}"
            filtered, log = apply_filter_step(
                filtered, '换手率', condition, 
                f"换手率筛选({st.session_state.filter_params['turnover_min']}%-{st.session_state.filter_params['turnover_max']}%)", 
                step_num
            )
            steps_log.append(log)
            step_num += 1
        
        # 步骤4：流通市值筛选
        if enable_step4 and len(filtered) > 0:
            condition = f">= {st.session_state.filter_params['mktcap_min']} and df['流通市值_亿'] <= {st.session_state.filter_params['mktcap_max']}"
            filtered, log = apply_filter_step(
                filtered, '流通市值_亿', condition, 
                f"流通市值筛选({st.session_state.filter_params['mktcap_min']}-{st.session_state.filter_params['mktcap_max']}亿元)", 
                step_num
            )
            steps_log.append(log)
            step_num += 1
        
        # 显示筛选步骤
        with st.expander("📋 筛选步骤详情", expanded=True):
            st.write(f"初始股票数量: {initial_count:,} 只")
            for log in steps_log:
                if "→" in log:
                    st.success(log)
                elif "错误" in log or "跳过" in log:
                    st.warning(log)
                else:
                    st.write(log)
            st.write(f"**最终结果: {len(filtered):,} 只**")
        
        # 处理筛选结果
        if len(filtered) == 0:
            st.error("⚠️ 筛选后无符合条件的股票")
            
            with st.expander("🔍 问题诊断", expanded=True):
                st.markdown("""
                ### 可能的原因：
                
                1. **数据格式不匹配** - 实时数据的字段名或数值格式与筛选条件不匹配
                2. **数据范围不符** - 当前市场可能没有股票满足您的筛选条件
                3. **网络数据延迟** - 实时数据可能有延迟或错误
                
                ### 解决方法：
                
                1. **查看数据统计** - 启用"显示数据统计"查看各字段的实际范围
                2. **使用模拟数据测试** - 切换到模拟数据验证筛选逻辑是否正确
                3. **放宽筛选条件** - 调整涨跌幅、量比等参数的范围
                4. **检查字段映射** - 确保筛选字段在数据中实际存在
                """)
                
                # 显示字段映射信息
                st.write("**当前数据字段:**")
                for col in df.columns[:10]:  # 只显示前10个字段
                    st.write(f"- {col}")
            
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
        display_cols = []
        for col in ['代码', '名称', '涨跌幅', '量比', '换手率', '流通市值_亿', '最新价']:
            if col in filtered.columns:
                display_cols.append(col)
        
        display_df = filtered[display_cols].copy()
        
        # 重命名显示列
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
            if col in ['涨跌幅%', '量比', '换手率%', '流通市值(亿)', '最新价']:
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

# 使用说明
with st.expander("📖 使用说明", expanded=False):
    st.markdown("""
    ### 解决备用数据源无结果的问题：
    
    经过分析，备用数据源（东方财富）返回的数据格式与模拟数据不同，导致筛选失败。我已经：
    
    1. **统一字段映射** - 将不同数据源的字段名统一为标准名称
    2. **数据清洗** - 处理百分比、逗号等特殊格式
    3. **增强调试** - 显示详细的数据统计和转换日志
    4. **错误处理** - 每个筛选步骤都有独立的错误处理
    
    ### 使用步骤：
    
    1. **先用模拟数据测试** - 选择"模拟数据(100%稳定)"，验证筛选逻辑
    2. **查看数据统计** - 启用"显示数据统计"，了解各字段的实际范围
    3. **切换到实时数据** - 使用"备用数据源"或"AKShare数据源"
    4. **对比数据差异** - 如果实时数据无结果，查看字段映射是否正确
    
    ### 调试技巧：
    
    - 启用"显示数据统计"查看各字段范围
    - 启用"详细日志"查看筛选过程的详细信息
    - 启用"显示原始样本"查看原始数据格式
    
    ### 常见问题：
    
    - **涨跌幅筛选为0**：检查涨跌幅字段是否存在，数值范围是否匹配
    - **量比筛选为0**：检查量比字段名称和数值格式
    - **换手率筛选为0**：检查换手率字段和数值范围
    
    ### 重要提示：
    
    如果实时数据仍然无结果，请提供以下信息帮助调试：
    1. 启用"显示数据统计"的截图
    2. 启用"详细日志"的截图
    3. 筛选步骤详情的截图
    """)

# 页脚
st.sidebar.markdown("---")
st.sidebar.caption(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")