import os
import re

input_folder = "MDA训练集"
output_folder = "output_txt"

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

def is_table_like(line):
    # 特征1：出现至少2个空格或tab对齐
    if len(re.findall(r'[\t ]{2,}', line)) >= 1:
        return True

    # 特征2：包含3个以上数字（不要求格式）
    if len(re.findall(r'\d+', line)) >= 3:
        return True

    # 特征3：含有表格相关字段词
    if re.search(r'(金额|比例|占比|资产|负债|说明|人数|本期|上期|变动)', line):
        return True

    # 特征4：以多字段构成，列数多
    columns = re.split(r'[\t ]{2,}', line.strip())
    if len(columns) >= 3:
        return True

    return False

def remove_table_blocks(text):
    lines = text.splitlines()
    n = len(lines)
    to_delete = set()
    i = 0

    while i < n:
        if is_table_like(lines[i]):
            # 开始识别表格块
            start = i
            end = i

            while start > 0 and is_table_like(lines[start - 1]):
                start -= 1
            while end + 1 < n and is_table_like(lines[end + 1]):
                end += 1

            for j in range(start, end + 1):
                to_delete.add(j)

            i = end + 1  # 跳过这段
        else:
            i += 1

    # 清除标记的行
    cleaned = [line for idx, line in enumerate(lines) if idx not in to_delete]
    cleaned_text = '\n'.join(cleaned)
    cleaned_text = re.sub(r'\n\s*\n+', '\n', cleaned_text).strip()
    return cleaned_text

# 主处理流程
for filename in os.listdir(input_folder):
    if filename.endswith(".txt"):
        input_path = os.path.join(input_folder, filename)
        base_name = os.path.splitext(filename)[0]
        output_filename = f"{base_name}_notable.txt"
        output_path = os.path.join(output_folder, output_filename)

        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        cleaned = remove_table_blocks(content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned)

        print(f"已处理: {filename} -> {output_filename}")

print("所有文件处理完成！")