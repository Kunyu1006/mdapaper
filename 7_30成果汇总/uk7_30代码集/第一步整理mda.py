import os
import shutil
import pandas as pd
import time

# ==== 配置区 ====
index_file   = "/Users/yukun/Desktop/mda/uk_try/所有行业成分股.xlsx"  # 存储行业成分股及关键词的Excel路径
source_root  = "/Users/yukun/Desktop/mda/2000-2022MDA文本(按年份)"    # 按年份归档的原始数据文件夹
output_root  = "/Users/yukun/Desktop/mda/行业"                         # 输出（拷贝）文件的根目录
years        = list(range(2000, 2023))                               # 需要处理的年份列表（2000-2022）
pointer_file = os.path.join(output_root, "resume_pointer.txt")       # 存放断点指针的文件（用于断点续跑）
# ================

def safe_copy(src, dst, retries=3, delay=5):
    """
    安全复制文件，支持失败重试。
    参数：
        src: 源文件路径
        dst: 目标文件路径
        retries: 最大重试次数（默认3次）
        delay: 重试间隔秒数（默认5秒）
    返回值：
        True：复制成功
        False：复制失败
    """
    for attempt in range(1, retries + 1):
        try:
            shutil.copy2(src, dst)  # 使用shutil.copy2可以保留元数据
            return True
        except Exception as e:
            print(f"⚠️ Copy 错误（第{attempt}次）：{e}")
            if attempt < retries:
                time.sleep(delay)
    return False  # 多次尝试失败后返回False


def build_year_index(year):
    """
    为指定年份构建文件索引。
    返回该年份下所有文件的规范化名称与完整路径的列表。
    格式：[(标准化文件名, 文件全路径), ...]
    """
    year_dir = os.path.join(source_root, str(year))
    index = []
    for root, _, files in os.walk(year_dir):
        for fname in files:
            norm = fname.lower().replace(" ", "")  # 文件名全部转小写并去除空格便于匹配
            index.append((norm, os.path.join(root, fname)))
    return index


def load_pointer():
    """
    加载断点续跑指针文件，若文件存在则读取返回索引，否则返回0（从头开始）。
    """
    if os.path.exists(pointer_file):
        try:
            return int(open(pointer_file, "r").read().strip())
        except:
            pass  # 文件格式不符等异常均返回0
    return 0


def save_pointer(idx):
    """
    保存断点指针到文件，记录当前处理到的任务索引。
    """
    os.makedirs(output_root, exist_ok=True)
    with open(pointer_file, "w") as f:
        f.write(str(idx))


def build_tasks(df):
    """
    由DataFrame构建所有待处理的任务（行业, 年份, 关键词）三元组列表。
    每个行业的每个关键词，每年都生成一条任务。
    """
    tasks = []
    for _, row in df.iterrows():
        industry = row["行业"].strip()      # 行业名称
        raw = row.get("关键词列表", "")      # 关键词（字符串，逗号分隔）
        keywords = [s.strip().strip('"\'') for s in raw.split(",") if s.strip()]  # 分割并去空白
        if not industry or not keywords:
            continue
        for year in years:
            for key in keywords:
                tasks.append((industry, year, key))
    return tasks


def main():
    # 1. 读取并清洗Excel表格
    df = pd.read_excel(index_file, dtype=str)
    df.columns = df.columns.str.strip()  # 列名去除空白，避免匹配错误

    # 2. 构建全部任务 & 加载上次运行的断点（若有）
    tasks = build_tasks(df)
    total = len(tasks)
    start = load_pointer()
    print(f"▶️ 共 {total} 项任务，续跑从 #{start+1} 开始")

    # 3. 缓存每年所有文件索引，减少多次IO遍历
    year_indices = {}

    try:
        # 遍历所有任务（三元组）
        for idx in range(start, total):
            industry, year, keyword = tasks[idx]

            # 如未缓存则生成该年份的文件索引
            if year not in year_indices:
                year_indices[year] = build_year_index(year)

            # 规范化关键词，用于文件名模糊匹配
            key_norm = keyword.lower().replace(" ", "")
            matches = [path for norm, path in year_indices[year] if key_norm in norm]
            if not matches:
                # 没有找到匹配文件，保存断点，继续下一个任务
                save_pointer(idx + 1)
                continue

            # 有匹配则复制到指定目录（按行业和年份分类）
            dst_dir = os.path.join(output_root, industry, str(year))
            os.makedirs(dst_dir, exist_ok=True)
            for src_path in matches:
                dst_path = os.path.join(dst_dir, os.path.basename(src_path))
                if safe_copy(src_path, dst_path):
                    print(f"✅ 已复制 {keyword}: {dst_path}")

            # 每处理完一个任务就保存指针（便于中断续跑）
            save_pointer(idx + 1)

        # 所有任务完成后，删除续跑指针文件
        if os.path.exists(pointer_file):
            os.remove(pointer_file)
        print("🎉 全部任务完成，已清除续跑指针。")

    except KeyboardInterrupt:
        # 支持Ctrl+C安全中断，指针会自动记录，下次可从断点继续
        print(f"\n⏸️ 手动中断，指针已记录至 #{idx+1}，下次续跑。")
    except Exception as e:
        # 捕获其他异常并记录断点
        print(f"\n❌ 脚本异常中断：{e}\n   指针已记录至 #{idx+1}")


if __name__ == "__main__":
    main()