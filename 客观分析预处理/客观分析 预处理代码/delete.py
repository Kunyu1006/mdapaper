import os
import re

# 判断一行是否可能是表格行
def is_probable_table_line(line):
    # 如果该行制表符（tab）数量 >= 3，基本可以判定为表格
    if line.count('\t') >= 3:
        return True
    # 如果该行的数字占比较高（>30%）且包含制表符，也可能是表格
    digit_ratio = sum(c.isdigit() for c in line) / (len(line) + 1)  # +1 防止除以0
    if digit_ratio > 0.3 and '\t' in line:
        return True
    return False

# 删除文本中类似表格的区块
def remove_table_blocks(text):
    lines = text.splitlines()  # 将文本按行分割
    output_lines = []          # 保存非表格行
    in_table = False           # 是否当前处于表格段落中
    table_buffer = []          # 临时缓存表格行（实际未使用）

    for line in lines:
        if is_probable_table_line(line):  # 如果该行是表格行
            table_buffer.append(line)     # 加入缓存
            in_table = True               # 标记当前处于表格中
        else:
            if in_table:                 # 一旦跳出表格
                table_buffer = []        # 清空缓存（虽然未使用）
                in_table = False
            output_lines.append(line)    # 记录正常行

    return "\n".join(output_lines)       # 拼接为新的文本返回

# 删除“适用/不适用”选项标识，如“□适用√不适用”
def clean_applicability_flags(text):
    """删除如 ‘□适用√不适用’、‘√适用□不适用’、‘□适用’ 等片段，但不删整行"""
    patterns = [
        r"□\s*适用\s*√\s*不适用",   # 正则匹配各种形式的适用标识
        r"√\s*适用\s*□\s*不适用",
        r"□\s*适用",
        r"√\s*适用",
        r"□\s*不适用",
        r"√\s*不适用"
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text)  # 用空字符串替换匹配项
    return text

# 删除“单位：万元”、“单位：人民币万元”等字段，仅清除字段不删整行
def remove_unit_lines(text):
    pattern = r"单位：\S+"  # 匹配“单位：”后接任意非空白字符
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        cleaned_line = re.sub(pattern, "", line)  # 替换掉单位字段
        cleaned_lines.append(cleaned_line)
    return "\n".join(cleaned_lines)

# 删除所有空白行（只保留非空行）
def remove_blank_lines(text):
    lines = text.splitlines()
    non_blank_lines = [line for line in lines if line.strip() != ""]  # 排除空行
    return "\n".join(non_blank_lines)

# 主函数：处理指定文件夹下的 .txt 文件并保存到输出目录
def process_txt_files(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)  # 如果输出文件夹不存在就创建

    for filename in os.listdir(input_folder):  # 遍历所有文件
        if filename.endswith(".txt"):  # 只处理 .txt 文件
            input_path = os.path.join(input_folder, filename)
            with open(input_path, "r", encoding="utf-8") as f:
                text = f.read()  # 读取原始文本内容

            # 逐步清洗文本内容
            cleaned_text = remove_table_blocks(text)           # 移除表格段落
            cleaned_text = clean_applicability_flags(cleaned_text)  # 移除“适用”标记
            cleaned_text = remove_unit_lines(cleaned_text)     # 移除“单位”标识
            cleaned_text = remove_blank_lines(cleaned_text)    # 移除空行

            # 保存新文件名：原名 + "_fine"
            base_name, ext = os.path.splitext(filename)
            output_name = base_name + "_fine" + ext
            output_path = os.path.join(output_folder, output_name)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(cleaned_text)  # 写入清洗后的文本

            print(f"Saved: {output_path}")  # 打印保存信息

# 程序入口，指定输入输出路径（你可以自行修改）
if __name__ == "__main__":
    input_folder = "MDA训练集"      # 输入目录（原始txt文件）
    output_folder = "output_txt"    # 输出目录（清洗后的文件）
    process_txt_files(input_folder, output_folder)