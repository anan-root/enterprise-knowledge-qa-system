import os


def merge_md_files(file1, file2, output_file, separator="\n\n"):
    """
    合并两个 Markdown 文件

    Args:
        file1: 第一个文件路径
        file2: 第二个文件路径
        output_file: 输出文件路径
        separator: 文件间分隔符（默认添加水平线）
    """
    with open(file1, 'r', encoding='utf-8') as f:
        content1 = f.read()

    with open(file2, 'r', encoding='utf-8') as f:
        content2 = f.read()

    # 合并内容
    merged = content1 + separator + content2

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(merged)

    print(f"✅ 已合并: {output_file}")
    print(f"   文件1: {file1} ({len(content1)} 字符)")
    print(f"   文件2: {file2} ({len(content2)} 字符)")
    print(f"   总计: {len(merged)} 字符")


if __name__ == '__main__':
    merge_md_files(
        file1="./招标投标法律解读与风险防范实务-1.md",
        file2="./招标投标法律解读与风险防范实务-2.md",
        output_file="招标投标法律解读与风险防范实务.md",
        separator="\n\n"  # 或用 "---" 分隔线
    )