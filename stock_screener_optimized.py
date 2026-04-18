# 在 get_data_from_akshare_em 函数中，修改为使用更完整的接口
def get_data_from_akshare_em() -> Optional[Tuple[pd.DataFrame, str]]:
    """数据源4: AKShare东方财富接口 - 使用更完整的接口"""
    try:
        import akshare as ak
        
        # 尝试多个AKShare函数，优先使用更完整的接口
        funcs_to_try = [
            ("ak.stock_zh_a_spot_em", {}),  # 东方财富接口，字段更全
            ("ak.stock_zh_a_spot", {}),     # 新浪接口
        ]
        
        for func_name, kwargs in funcs_to_try:
            try:
                if func_name == "ak.stock_zh_a_spot_em":
                    df = ak.stock_zh_a_spot_em(**kwargs)
                elif func_name == "ak.stock_zh_a_spot":
                    df = ak.stock_zh_a_spot(**kwargs)
                else:
                    continue
                
                if df is not None and len(df) > 100:
                    # 显示获取的字段（调试用）
                    if debug_mode:
                        st.info(f"AKShare接口 {func_name} 返回字段: {list(df.columns)}")
                    
                    # 智能字段映射
                    df = intelligent_field_mapper(df, f"AKShare-{func_name}")
                    
                    # 检查是否有关键字段
                    missing_required = []
                    for field in ['量比', '换手率']:
                        if field not in df.columns:
                            missing_required.append(field)
                    
                    if missing_required:
                        st.warning(f"AKShare接口缺少字段: {missing_required}")
                        # 尝试补充缺失字段
                        if '量比' not in df.columns:
                            df['量比'] = 1.0  # 默认值
                        if '换手率' not in df.columns:
                            df['换手率'] = 2.0  # 默认值
                        st.info("已为缺失字段添加默认值，筛选结果可能不准确")
                    
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
        
        return None, "AKShare所有接口都失败"
        
    except ImportError:
        return None, "AKShare 未安装"
    except Exception as e:
        return None, f"AKShare 异常: {str(e)[:100]}"