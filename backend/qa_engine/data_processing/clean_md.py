import re
import os


def clean_markdown(md_path):
    """
    清洗 Markdown 文档：
    1. 合并段落内的多余换行（保留真正的段落分隔）
    2. 保留标题、列表等结构
    3. 清理空行
    """
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()

    # 步骤1：保护代码块（如果有的话）
    code_blocks = []

    def save_code_block(match):
        code_blocks.append(match.group(0))
        return f"___CODE_BLOCK_{len(code_blocks) - 1}___"

    # 临时替换代码块
    text = re.sub(r'```[\s\S]*?```', save_code_block, text)
    text = re.sub(r'`[^`]+`', save_code_block, text)

    # 步骤2：处理段落
    # 将单个换行替换为空格（合并同一段落）
    # 但保留段落分隔（两个以上换行）

    # 先标准化换行符
    text = text.replace('\r\n', '\n')

    # 保护标题（以 # 开头的行）
    lines = text.split('\n')
    result_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # 标题行：保留原样
        if re.match(r'^#{1,6}\s', line):
            result_lines.append(line)
            i += 1
            continue

        # 列表项：保留原样
        if re.match(r'^(\s*)([-*+]|\d+\.)\s', line):
            result_lines.append(line)
            i += 1
            continue

        # 空行：保留一个
        if not line.strip():
            result_lines.append('')
            i += 1
            continue

        # 普通段落行：合并后续的非空行（去除多余换行）
        paragraph = line
        i += 1

        while i < len(lines):
            next_line = lines[i]

            # 遇到空行、标题、列表停止合并
            if not next_line.strip() or re.match(r'^#{1,6}\s', next_line) or re.match(r'^(\s*)([-*+]|\d+\.)\s',
                                                                                      next_line):
                break

            # 合并到当前段落（加空格）
            paragraph = paragraph.rstrip() + ' ' + next_line.lstrip()
            i += 1

        result_lines.append(paragraph)

    # 步骤3：清理连续空行（最多保留一个）
    cleaned = []
    prev_empty = False

    for line in result_lines:
        is_empty = not line.strip()

        if is_empty:
            if not prev_empty:
                cleaned.append('')
            prev_empty = True
        else:
            cleaned.append(line)
            prev_empty = False

    text = '\n'.join(cleaned)

    # 步骤4：恢复代码块
    for i, block in enumerate(code_blocks):
        text = text.replace(f"___CODE_BLOCK_{i}___", block)

    # ✅ 修复：赋值给变量
    text = text.strip()

    # ✅ 修复：更安全的文件名处理
    base, ext = os.path.splitext(md_path)
    cleaned_path = f"{base}_clean{ext}"

    # 保存
    with open(cleaned_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"✅ 清洗完成：{cleaned_path}")

def simple_clean(md_path):
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()

    """简单清洗：合并段落内换行，保留结构"""

    # 1. 保护标题和列表（加标记防止被合并）
    text = re.sub(r'^(#{1,6}\s.+)$', r'\1___PROTECT___', text, flags=re.M)
    text = re.sub(r'^(\s*[-*+\d]\.?\s.+)$', r'\1___PROTECT___', text, flags=re.M)  # 改进：支持数字列表

    # 2. 合并非保护行的换行（行末不是句号/换行，且下一行不是特殊结构）
    text = re.sub(r'([^。\n])\n(?![\n#\-*\d])', r'\1', text)

    # 3. 恢复保护标记
    text = text.replace('___PROTECT___', '')

    # 4. 清理多余空行（3个以上换行变2个）
    text = re.sub(r'\n{3,}', '\n\n', text)

    # ✅ 修复：赋值给变量
    text = text.strip()

    # ✅ 修复：更安全的文件名处理
    base, ext = os.path.splitext(md_path)
    cleaned_path = f"{base}_clean{ext}"

    # 保存
    with open(cleaned_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"✅ 清洗完成：{cleaned_path}")


if __name__ == '__main__':
    clean_markdown('中华人民共和国招标投标法律法规全书.md')