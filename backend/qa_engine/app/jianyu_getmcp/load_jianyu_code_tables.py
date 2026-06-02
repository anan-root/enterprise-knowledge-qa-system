import json

import pandas as pd
from typing import Dict


def load_jianyu_code_tables(file_path: str) -> Dict[str, Dict]:
    """
    从剑鱼标讯代码表 Excel 文件中提取各类代码表
    """
    xls = pd.ExcelFile(file_path)
    code_tables = {}

    for sheet_name in xls.sheet_names:
        if '目录' in sheet_name:
            continue

        print(f"\n正在处理: {sheet_name}")

        # 先读取无header的数据来找到header行
        df_raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
        header_row = _find_header_row(df_raw)
        print(f"  找到header行: {header_row}")

        # 用正确的header重新读取
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
        print(f"  列名: {df.columns.tolist()[:6]}")  # 打印前6列
        print(f"  数据行数: {len(df)}")

        if '地区代码表' in sheet_name or 'code_area' in sheet_name:
            code_tables['area'] = _parse_area_table(df)
        elif '信息行业代码表' in sheet_name or 'code_bidscope' in sheet_name:
            code_tables['industry'] = _parse_industry_table(df)
        elif '信息类型代码表' in sheet_name or 'code_bidtopsubtype' in sheet_name:
            code_tables['info_type'] = _parse_info_type_table(df)
        elif '采购单位类型代码表' in sheet_name or 'code_buyerclass' in sheet_name:
            code_tables['buyer_type'] = _parse_buyer_type_table(df)
        elif '拟在建项目阶段代码表' in sheet_name or 'nzj_code_project_stage' in sheet_name:
            code_tables['project_stage'] = _parse_project_stage_table(df)
        elif '拟在建业主类型代码表' in sheet_name or 'nzj_code_ownerclass' in sheet_name:
            code_tables['owner_type'] = _parse_owner_type_table(df)
        elif '拟在建分类代码规则表' in sheet_name or 'nzj_code_category' in sheet_name:
            code_tables['category'] = _parse_category_table(df)

    return code_tables


def _find_header_row(df: pd.DataFrame) -> int:
    """查找表头所在行 - 找包含'code'或'字段名'的行"""
    for idx, row in df.iterrows():
        row_values = [str(x).lower() if pd.notna(x) else '' for x in row]
        row_str = ' '.join(row_values)
        # 找包含 code 或 字段名 的行
        if ('code' in row_str and 'id' in row_str) or '字段名' in row_str:
            return idx
    return 1


def _clean_code(code) -> str:
    """清理代码格式"""
    if pd.isna(code):
        return None
    code = str(code).strip()
    # 去掉小数点后面的0（如 110000.0 → 110000）
    if '.' in code:
        code = code.split('.')[0]
    # 确保是数字字符串
    if not code.isdigit():
        return None
    return code


def _parse_area_table(df: pd.DataFrame) -> Dict[str, str]:
    """
    解析地区代码表
    结构：id, code, area(省份), city(城市), district(区县), alias
    我们需要：省份 -> 省级代码(以0000结尾)，城市 -> 市级代码(以00结尾但不是0000)
    """
    result = {}

    # 打印前几行调试
    print(f"  地区表前3行:")
    for i in range(min(3, len(df))):
        row = df.iloc[i]
        print(
            f"    行{i}: {row.iloc[0] if len(row) > 0 else '-'}, {row.iloc[1] if len(row) > 1 else '-'}, {row.iloc[2] if len(row) > 2 else '-'}, {row.iloc[3] if len(row) > 3 else '-'}")

    # 遍历所有行
    for idx, row in df.iterrows():
        if len(row) < 3:
            continue

        code = _clean_code(row.iloc[1])  # 第2列是code
        area = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else None  # 第3列是area/省份
        city = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else None  # 第4列是city/城市

        if not code:
            continue

        # 省级代码：6位数字，以0000结尾（如110000）
        if code.endswith('0000') and area and area != 'nan':
            result[area] = code
        # 市级代码：6位数字，以00结尾但不是0000（如110100）
        elif code.endswith('00') and not code.endswith('0000') and city and city != 'nan':
            # 城市名称可能包含"市"字，统一处理
            city_clean = city.replace('市', '').replace('地区', '').replace('盟', '')
            if city_clean and len(city_clean) > 0:
                result[city] = code

    return result


def _parse_generic_table(df: pd.DataFrame, code_col_idx: int = 1, name_col_idx: int = 4) -> Dict[str, str]:
    """
    通用解析函数
    根据观察到的Excel结构：id, code, pcode, level, name, remark...
    code在第2列(索引1)，name在第5列(索引4)
    """
    result = {}

    # 打印前几行调试
    print(f"  表前3行数据:")
    for i in range(min(3, len(df))):
        row = df.iloc[i]
        code_val = row.iloc[code_col_idx] if len(row) > code_col_idx else None
        name_val = row.iloc[name_col_idx] if len(row) > name_col_idx else None
        print(f"    行{i}: code={code_val}, name={name_val}")

    for idx, row in df.iterrows():
        if len(row) <= max(code_col_idx, name_col_idx):
            continue

        code = _clean_code(row.iloc[code_col_idx])
        name = str(row.iloc[name_col_idx]).strip() if pd.notna(row.iloc[name_col_idx]) else None

        if code and name and name != 'nan' and len(name) > 0 and name != 'name':
            result[name] = code

    return result


def _parse_industry_table(df: pd.DataFrame) -> Dict[str, str]:
    """解析信息行业代码表"""
    return _parse_generic_table(df, code_col_idx=1, name_col_idx=4)


def _parse_info_type_table(df: pd.DataFrame) -> Dict[str, str]:
    """解析信息类型代码表"""
    return _parse_generic_table(df, code_col_idx=1, name_col_idx=4)


def _parse_buyer_type_table(df: pd.DataFrame) -> Dict[str, str]:
    """解析采购单位类型代码表"""
    return _parse_generic_table(df, code_col_idx=1, name_col_idx=4)


def _parse_project_stage_table(df: pd.DataFrame) -> Dict[str, str]:
    """解析拟在建项目阶段代码表"""
    return _parse_generic_table(df, code_col_idx=1, name_col_idx=4)


def _parse_owner_type_table(df: pd.DataFrame) -> Dict[str, str]:
    """解析拟在建业主类型代码表"""
    return _parse_generic_table(df, code_col_idx=1, name_col_idx=4)


def _parse_category_table(df: pd.DataFrame) -> Dict[str, str]:
    """解析拟在建分类代码规则表"""
    return _parse_generic_table(df, code_col_idx=1, name_col_idx=4)


# ========== 使用示例 ==========

if __name__ == "__main__":
    file_path = "jianyu_code.xlsx"

    code_tables = load_jianyu_code_tables(file_path)
    with open('jianyu_code.json', 'w', encoding='utf-8') as f:
        json.dump(code_tables, f, ensure_ascii=False, indent=4)

    # print(code_tables)
    # print(f"\n{'=' * 60}")
    # print("【最终结果汇总】")
    # print(f"{'=' * 60}")
    #
    # for table_name, table_data in code_tables.items():
    #     print(f"\n【{table_name}】共 {len(table_data)} 条记录")
    #
    #     # 只打印前5条作为示例
    #     items = list(table_data.items())[:5]
    #     for name, code in items:
    #         print(f"  {name}: {code}")
    #
    #     if len(table_data) > 5:
    #         print(f"  ... 还有 {len(table_data) - 5} 条记录")
    #
    # print(f"\n{'=' * 60}")
    # print("【查询示例】")
    # print(f"{'=' * 60}")
    #
    # if 'area' in code_tables:
    #     print(f"北京的代码: {code_tables['area'].get('北京', '未找到')}")
    #     print(f"上海的代码: {code_tables['area'].get('上海', '未找到')}")
    #     print(f"广州的代码: {code_tables['area'].get('广州', '未找到')}")
    #
    # if 'info_type' in code_tables:
    #     print(f"招标的代码: {code_tables['info_type'].get('招标', '未找到')}")
    #     print(f"预告的代码: {code_tables['info_type'].get('预告', '未找到')}")
    #     print(f"结果的代码: {code_tables['info_type'].get('结果', '未找到')}")
    #
    # if 'industry' in code_tables:
    #     print(f"建筑工程的代码: {code_tables['industry'].get('建筑工程', '未找到')}")
    #     print(f"行政办公的代码: {code_tables['industry'].get('行政办公', '未找到')}")
    #
    # if 'buyer_type' in code_tables:
    #     print(f"教育的代码: {code_tables['buyer_type'].get('教育', '未找到')}")
    #     print(f"医疗的代码: {code_tables['buyer_type'].get('医疗', '未找到')}")