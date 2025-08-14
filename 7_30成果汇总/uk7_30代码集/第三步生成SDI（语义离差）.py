import os
import re
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# 这里已无skip_list相关内容

def text_to_vecs(text, model):
    """
    功能：将一段文本分割成多个句子，并用预训练的模型将每个句子转成向量。
    参数：
        text：输入的字符串文本
        model：句向量模型（SentenceTransformer）
    返回：
        如果文本中有有效句子，则返回所有句子的向量数组（二维ndarray）。
        如果没有有效句子，则返回空列表。
    """
    if pd.isna(text):  # 判空，防止输入是空值
        return []
    sents = [s.strip() for s in re.split(r"[。！？\n]", str(text)) if len(s.strip()) > 5]
    if not sents:
        return []
    return model.encode(sents)

# ==== 路径与模型准备 ====
base_input_path = '/Users/yukun/Desktop/mda/topic'    # 输入文件夹：存放每个行业的主题聚类Excel
base_output_path = '/Users/yukun/Desktop/mda/SDI'     # 输出文件夹：用于保存SDI结果Excel
model = SentenceTransformer('BAAI/bge-small-zh')      # 加载一个中文句向量模型
os.makedirs(base_output_path, exist_ok=True)          # 如果输出文件夹不存在就自动创建

# ==== 主循环：遍历每个行业 ====
for industry in os.listdir(base_input_path):
    industry_folder = os.path.join(base_input_path, industry)
    if not os.path.isdir(industry_folder):
        continue  # 跳过非文件夹内容

    # 下面内容全部保留不变……
    files = sorted([f for f in os.listdir(industry_folder)
                    if f.endswith('.xlsx') and re.search(r'(\d{4})topic', f)])
    files_year = sorted([(f, int(re.search(r'(\d{4})topic', f).group(1)))
                        for f in files], key=lambda x: x[1])

    if len(files_year) < 2:
        print(f"⚠️ 行业{industry}可比年份不足，跳过")
        continue

    for idx in range(1, len(files_year)):
        file_prev, year_prev = files_year[idx - 1]
        file_now, year_now = files_year[idx]

        try:
            df_prev = pd.read_excel(os.path.join(industry_folder, file_prev))
            df_now = pd.read_excel(os.path.join(industry_folder, file_now))
        except Exception as e:
            print(f"❌ 读取文件失败: {industry} {file_prev} {file_now}，错误：{e}")
            continue

        # 5.2 文件名转公司名辅助函数，统一不同年份公司名格式，便于对齐
        def extract_company(x):
            """
            例子：'000002-万科A' 会返回 '万科A'；
                  '万科A' 会返回 '万科A'
                  其它情况原样返回
            """
            if isinstance(x, str) and '-' in x:
                parts = x.split('-')
                if len(parts) > 1:
                    return parts[1]
                return parts[0]
            return x

        # 5.3 必须有“文件名”列，否则无法对齐公司，跳过这对年份
        if '文件名' not in df_prev.columns or '文件名' not in df_now.columns:
            print(f"⚠️ 缺少文件名列，跳过：{industry} {year_prev}-{year_now}")
            continue

        # 5.4 增加一列“公司”，提取标准化公司名
        df_prev['公司'] = df_prev['文件名'].apply(extract_company)
        df_now['公司'] = df_now['文件名'].apply(extract_company)

        # 5.5 确定所有要做对比的主题名
        # 通用主题列：去掉“文件名”“公司”和以“行业主题”开头的所有列
        exclude_cols = ['文件名', '公司']
        common_cols_now = set([c for c in df_now.columns
                              if c not in exclude_cols and not c.startswith("行业主题")])
        common_cols_prev = set([c for c in df_prev.columns
                               if c not in exclude_cols and not c.startswith("行业主题")])
        common_cols = sorted(list(common_cols_now & common_cols_prev))  # 取两个年份的主题交集，保证主题一致

        # 行业主题列：一般只有一个，也可能有多个，依次两两配对
        industry_cols_now = [c for c in df_now.columns if "行业主题" in c]
        industry_cols_prev = [c for c in df_prev.columns if "行业主题" in c]
        industry_pairs = []
        for i in range(min(len(industry_cols_now), len(industry_cols_prev))):
            industry_pairs.append((industry_cols_now[i], industry_cols_prev[i]))

        # 5.6 只对两个年份都出现的公司进行SDI比较
        company_list = sorted(list(set(df_now['公司']) & set(df_prev['公司'])))
        result_rows = []

        # 5.7 针对每一个通用主题，计算每个公司的SDI
        for topic in common_cols:
            # 构造前一年/当前年 主题文本的“公司→内容”字典
            t_prev = dict(zip(df_prev['公司'], df_prev[topic]))
            t_now = dict(zip(df_now['公司'], df_now[topic]))
            sdis = []
            for company in company_list:
                # 获取某公司的前一年和当前年主题内容，并转为句向量
                v1 = text_to_vecs(t_prev.get(company, ""), model)
                v2 = text_to_vecs(t_now.get(company, ""), model)
                # 如果任何一年没有有效文本，则SDI为空
                if len(v1) == 0 or len(v2) == 0:
                    sdis.append(np.nan)
                else:
                    # 句向量两两算余弦相似度，取所有配对的均值（代表文本变化幅度）
                    sim_matrix = cosine_similarity(v1, v2)
                    sdi = np.mean(1 - sim_matrix)  # SDI=1-平均相似度，越大越不相似，变动越大
                    sdis.append(sdi)
            # 计算行业均值/中位数，用于后续归一化
            arr = np.array([x for x in sdis if not pd.isna(x)])
            mean = np.mean(arr) if arr.size > 0 else np.nan
            median = np.median(arr) if arr.size > 0 else np.nan
            # 保存每家公司每个主题的SDI及相对行业均值/中位数的差值
            for i, company in enumerate(company_list):
                row = {
                    "公司": company,
                    f"{topic}SDI": sdis[i],
                    f"{topic}SDI-行业均值": None if pd.isna(sdis[i]) or pd.isna(mean) else sdis[i] - mean,
                    f"{topic}SDI-行业中位数": None if pd.isna(sdis[i]) or pd.isna(median) else sdis[i] - median,
                }
                result_rows.append(row)

        # 5.8 针对行业主题，同理，计算每家公司每个行业主题的SDI
        for idx, (col_now, col_prev) in enumerate(industry_pairs):
            t_prev = dict(zip(df_prev['公司'], df_prev[col_prev]))
            t_now = dict(zip(df_now['公司'], df_now[col_now]))
            sdis = []
            topic = "行业主题SDI"
            for company in company_list:
                v1 = text_to_vecs(t_prev.get(company, ""), model)
                v2 = text_to_vecs(t_now.get(company, ""), model)
                if len(v1) == 0 or len(v2) == 0:
                    sdis.append(np.nan)
                else:
                    sim_matrix = cosine_similarity(v1, v2)
                    sdi = np.mean(1 - sim_matrix)
                    sdis.append(sdi)
            arr = np.array([x for x in sdis if not pd.isna(x)])
            mean = np.mean(arr) if arr.size > 0 else np.nan
            median = np.median(arr) if arr.size > 0 else np.nan
            for i, company in enumerate(company_list):
                row = {
                    "公司": company,
                    f"{topic}": sdis[i],
                    f"{topic}-行业均值": None if pd.isna(sdis[i]) or pd.isna(mean) else sdis[i] - mean,
                    f"{topic}-行业中位数": None if pd.isna(sdis[i]) or pd.isna(median) else sdis[i] - median,
                }
                result_rows.append(row)

        # 5.9 把所有结果合并成一个大表，每行一个公司，每列一个主题的SDI和相关差值
        df_result = pd.DataFrame(result_rows)
        if df_result.empty or "公司" not in df_result.columns:
            print(f"⚠️ 跳过无有效数据：{industry} {year_now}")
            continue

        # 合并后，可能同一公司多行（每个主题各一行），按公司聚合成一行
        df_final = df_result.groupby("公司").first().reset_index()
        # 确定输出的列顺序
        col_list = ["公司"]
        for topic in common_cols:
            col_list.extend([f"{topic}SDI", f"{topic}SDI-行业均值", f"{topic}SDI-行业中位数"])
        for idx in range(len(industry_pairs)):
            col_list.extend([
                "行业主题SDI", "行业主题SDI-行业均值", "行业主题SDI-行业中位数"
            ])
        df_final = df_final[col_list]

        # 5.10 在表格最后再加一行，汇总每个主题的行业均值和中位数
        summary = {}
        for topic in common_cols:
            vals = df_final[f"{topic}SDI"].values
            vals = vals[~pd.isna(vals)]
            summary[f"{topic}SDI-行业均值"] = np.mean(vals) if vals.size > 0 else ""
            summary[f"{topic}SDI-行业中位数"] = np.median(vals) if vals.size > 0 else ""
        for idx in range(len(industry_pairs)):
            vals = df_final["行业主题SDI"].values
            vals = vals[~pd.isna(vals)]
            summary["行业主题SDI-行业均值"] = np.mean(vals) if vals.size > 0 else ""
            summary["行业主题SDI-行业中位数"] = np.median(vals) if vals.size > 0 else ""
        df_final = pd.concat([df_final, pd.DataFrame([summary])], ignore_index=True)

        # 5.11 输出到指定文件夹和文件
        out_dir = os.path.join(base_output_path, industry)
        os.makedirs(out_dir, exist_ok=True)
        outfile = os.path.join(out_dir, f"{industry}{year_now}SDI.xlsx")
        df_final.to_excel(outfile, index=False)
        print(f"✅ 已保存: {outfile}")

# 代码执行结束，所有行业、所有年份SDI对比和输出都已完成。