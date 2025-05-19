import os
import re

# 输入文件夹路径，里面存放待处理的原始文本文件（.txt）
input_folder = "MDA训练集"

# 输出文件夹路径，用来保存清理后的文本文件
output_folder = "output_txt"

# 如果输出文件夹不存在，则创建该文件夹，保证后续写文件不会出错
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

def is_table_like(line):
    """
    判断一行文本是否类似表格内容的函数
    依据几个特征判断：
    1. 是否存在连续两个或以上的空格或制表符（一般表格是对齐格式）
    2. 是否包含三个及以上的数字（表格常包含多数字）
    3. 是否包含表格相关的关键词（金额、比例、资产等）
    4. 是否由多个字段组成，字段数达到或超过3个（列数较多）
    如果符合任一条件则判定为“表格行”，返回True，否则False
    """
    # 特征1：连续两个或以上的空格或tab符
    if len(re.findall(r'[\t ]{2,}', line)) >= 1:
        return True

    # 特征2：数字数量不少于3个
    if len(re.findall(r'\d+', line)) >= 3:
        return True

    # 特征3：包含表格相关的关键词
    if re.search(r'(金额|比例|占比|资产|负债|说明|人数|本期|上期|变动)', line):
        return True

    # 特征4：列数达到3列以上
    columns = re.split(r'[\t ]{2,}', line.strip())
    if len(columns) >= 3:
        return True

    # 不满足上述任何条件，返回False
    return False

def remove_table_blocks(text):
    """
    从文本中删除所有连续的表格类内容块。
    处理流程：
    1. 按行切割文本
    2. 遍历每行，检测是否为表格行（调用 is_table_like）
    3. 连续的表格行合并为一个块，标记所有这些行索引为删除对象
    4. 遍历完成后，过滤掉所有被标记的行，剩余文本重新合并成字符串
    5. 进一步去除多余的空行，返回清理后的文本
    """
    lines = text.splitlines()  # 按行拆分
    n = len(lines)
    to_delete = set()  # 存储待删除行的索引
    i = 0

    # 遍历每一行
    while i < n:
        if is_table_like(lines[i]):
            # 发现表格行，开始向前向后扩展寻找整个连续的表格块
            start = i
            end = i

            # 向前扩展连续的表格行
            while start > 0 and is_table_like(lines[start - 1]):
                start -= 1
            # 向后扩展连续的表格行
            while end + 1 < n and is_table_like(lines[end + 1]):
                end += 1

            # 把整块表格行的索引加入删除集合
            for j in range(start, end + 1):
                to_delete.add(j)

            # 跳过这整块表格行，继续后面查找
            i = end + 1
        else:
            i += 1  # 非表格行，继续遍历下一行

    # 过滤掉所有待删除行，剩余内容合并成文本
    cleaned = [line for idx, line in enumerate(lines) if idx not in to_delete]
    cleaned_text = '\n'.join(cleaned)

    # 删除多余空行（多个空行缩减成一个），并去除首尾多余空白
    cleaned_text = re.sub(r'\n\s*\n+', '\n', cleaned_text).strip()
    return cleaned_text

# 主处理流程：遍历输入文件夹中的所有txt文件，进行表格内容清理，输出结果到新文件夹
for filename in os.listdir(input_folder):
    # 只处理以 .txt 结尾的文件
    if filename.endswith(".txt"):
        input_path = os.path.join(input_folder, filename)  # 输入文件路径
        base_name = os.path.splitext(filename)[0]  # 去掉扩展名的文件名
        output_filename = f"{base_name}_notable.txt"  # 新文件名，添加后缀_notable
        output_path = os.path.join(output_folder, output_filename)  # 输出文件路径

        # 读取原始文件内容
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 清理文本中的表格块
        cleaned = remove_table_blocks(content)

        # 将清理后的文本写入新文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned)

        # 打印处理进度
        print(f"已处理: {filename} -> {output_filename}")

# 全部文件处理完成提示
print("所有文件处理完成！")