import pdfplumber
import pandas as pd
import os
from datetime import datetime


def extract_pdf_tables_to_excel(pdf_path, excel_path=None, sheet_prefix="Table"):
    """
    从PDF中提取表格并输出到Excel的多个sheet中

    参数:
        pdf_path: PDF文件路径
        excel_path: 输出的Excel文件路径(默认为PDF同目录)
        sheet_prefix: sheet名称前缀
    """

    # 设置默认输出路径
    if excel_path is None:
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        excel_path = f"{pdf_name}_tables.xlsx"

    # 用于存储所有表格数据
    all_tables_data = []

    print(f"开始处理PDF文件: {pdf_path}")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, 1):
                print(f"正在处理第 {page_num}/{total_pages} 页...")

                # 提取当前页表格
                tables = page.extract_tables()

                if not tables:
                    print(f"  第 {page_num} 页未发现表格")
                    continue

                print(f"  第 {page_num} 页发现 {len(tables)} 个表格")

                for table_num, table_data in enumerate(tables, 1):
                    if not table_data or not any(any(cell for cell in row) for row in table_data):
                        print(f"    表格 {table_num} 为空，跳过")
                        continue

                    # 处理表格数据
                    processed_table = process_table_data(table_data, page_num, table_num)

                    if processed_table is not None:
                        all_tables_data.append(processed_table)
                        print(f"    表格 {table_num} 处理完成，共 {len(processed_table['data'])} 行")

    except Exception as e:
        print(f"处理PDF时出错: {e}")
        return False

    # 导出到Excel
    if not all_tables_data:
        print("未找到任何有效表格数据")
        return False

    return export_to_excel(all_tables_data, excel_path, sheet_prefix)


def process_table_data(table_data, page_num, table_num):
    """
    处理表格数据，自动识别列名
    """
    if not table_data:
        return None

    # 清理数据：去除空行和全空的行
    cleaned_data = []
    for row in table_data:
        # 过滤掉None和空字符串，只保留有内容的单元格
        cleaned_row = [str(cell).strip() if cell is not None and str(cell).strip() != '' else ''
                       for cell in row]
        # 如果整行都有内容，则保留
        if any(cleaned_row):
            cleaned_data.append(cleaned_row)

    if len(cleaned_data) < 2:  # 至少需要标题行和一行数据
        return None

    # 自动识别列名（假设第一行是列名）
    headers = cleaned_data[0]
    data_rows = cleaned_data[1:]

    # 如果列名全是空的，尝试用第二行作为列名
    if not any(headers):
        if len(cleaned_data) > 2:
            headers = cleaned_data[1]
            data_rows = cleaned_data[2:]
        else:
            # 如果没有合适的列名，生成默认列名
            num_cols = max(len(row) for row in cleaned_data) if cleaned_data else 0
            headers = [f"列_{i + 1}" for i in range(num_cols)]
            data_rows = cleaned_data

    # 确保所有行都有相同的列数
    max_cols = len(headers)
    standardized_data = []

    for row in data_rows:
        standardized_row = []
        for i in range(max_cols):
            if i < len(row):
                standardized_row.append(row[i])
            else:
                standardized_row.append('')
        standardized_data.append(standardized_row)

    return {
        'sheet_name': f"Page{page_num}_Table{table_num}",
        'headers': headers,
        'data': standardized_data
    }


def export_to_excel(tables_data, excel_path, sheet_prefix):
    """
    将表格数据导出到Excel
    """
    try:
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            for i, table_info in enumerate(tables_data, 1):
                sheet_name = f"{sheet_prefix}_{i}"

                # 创建DataFrame
                df = pd.DataFrame(table_info['data'], columns=table_info['headers'])

                # 写入Excel
                df.to_excel(writer, sheet_name=sheet_name, index=False)

                # 自动调整列宽
                worksheet = writer.sheets[sheet_name]
                for idx, col in enumerate(df.columns):
                    max_len = max(
                        df[col].astype(str).str.len().max(),
                        len(col)
                    ) + 2  # 额外留点空间
                    worksheet.column_dimensions[chr(65 + idx)].width = min(max_len, 50)

        print(f"\n✅ 导出成功！")
        print(f"📁 文件位置: {excel_path}")
        print(f"📊 共导出 {len(tables_data)} 个表格")
        print(f"⏰ 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return True

    except Exception as e:
        print(f"导出到Excel时出错: {e}")
        return False


# 使用示例
if __name__ == "__main__":
    # 方法1: 直接指定文件路径
    pdf_file = "DASS数据接口发布平台数据集成.pdf"
    extract_pdf_tables_to_excel(pdf_file)

    # 方法2: 自定义输出路径和sheet前缀
    # extract_pdf_tables_to_excel(
    #     pdf_path="input.pdf",
    #     excel_path="output_tables.xlsx",
    #     sheet_prefix="Data"
    # )