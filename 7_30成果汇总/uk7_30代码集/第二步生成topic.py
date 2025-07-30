# -*- coding: utf-8 -*-
import os
import re
import pandas as pd
from tqdm import tqdm
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from collections import Counter
import jieba
import jieba.analyse

# ==== 路径配置 ====
base_input_path = "/Users/yukun/Desktop/mda/行业"        # 输入：各行业按年归档的文本目录
base_output_path = "/Users/yukun/Desktop/mda/topic"      # 输出：行业主题分析结果保存目录
pointer_file = os.path.join(base_output_path, "progress_pointer.txt")  # 进度指针文件，断点续跑用
os.makedirs(base_output_path, exist_ok=True)             # 确保输出目录存在

# ==== 自动补全指针，防止重复分析 ====
existing_keys = set()  # 用于记录已输出的行业+年份组合
for industry_dir in os.listdir(base_output_path):
    output_industry_path = os.path.join(base_output_path, industry_dir)
    if not os.path.isdir(output_industry_path):
        continue
    for fname in os.listdir(output_industry_path):
        # 识别形如“行业名2022topic.xlsx”的输出文件
        match = re.match(r"^(.*?)(\d{4})topic\.xlsx$", fname)
        if match:
            industry_name = match.group(1)
            year = match.group(2)
            existing_keys.add(f"{industry_name}{year}")

# ==== 合并指针文件中的历史已处理key ====
if os.path.exists(pointer_file):
    with open(pointer_file, "r") as f:
        old_keys = set(line.strip() for line in f if line.strip())
else:
    old_keys = set()
new_keys = existing_keys | old_keys  # 合并历史与最新key，保证断点续跑
with open(pointer_file, "w") as f:   # 持久化进度指针
    for k in sorted(new_keys):
        f.write(k + "\n")
done_keys = new_keys                 # 用于后续跳过已完成的任务

# ==== 加载中文句嵌入模型（用于BERTopic） ====
embedding_model = SentenceTransformer("BAAI/bge-small-zh")

# ==== 定义通用主题及关键词，便于自动标签归类 ====
common_topics = {
    "未来研发": ["研发", "创新", "技术升级", "技术投入", "技术创新"],
    "风险因素": ["风险", "不确定", "挑战", "隐患", "波动"],
    "公司战略": ["战略", "目标", "布局", "方向", "蓝图"],
    "市场趋势": ["市场", "需求", "客户", "竞争", "占有率"],
    "财务状况": ["收入", "利润", "毛利", "营收", "增长"],
    "经营成果": ["经营", "回报", "绩效", "业绩"],
    "政策环境": ["政策", "监管", "法规", "法律", "合规"]
}

# ==== 遍历所有行业文件夹 ====
for industry_dir in os.listdir(base_input_path):
    industry_path = os.path.join(base_input_path, industry_dir)
    if not os.path.isdir(industry_path):
        continue
    if industry_dir in ["topic", "rank_andoutput"]:  # 跳过特定目录
        continue

    # 解析行业名称（若有“行业名+数字”命名，则只取行业名部分）
    match = re.match(r'^(.+?)(\d+)$', industry_dir)
    industry_name = match.group(1) if match else industry_dir
    output_industry_path = os.path.join(base_output_path, industry_name)
    os.makedirs(output_industry_path, exist_ok=True)

    # ==== 遍历该行业下的所有年份子文件夹 ====
    for year_dir in sorted(os.listdir(industry_path)):
        year_path = os.path.join(industry_path, year_dir)
        # 只处理4位数字的年份目录
        if not os.path.isdir(year_path) or not re.match(r'^\d{4}$', year_dir):
            continue

        industry_year_key = f"{industry_name}{year_dir}"
        if industry_year_key in done_keys:
            print(f"已处理，跳过：{industry_year_key}")
            continue

        try:
            # ==== 收集所有txt文件 ====
            file_list = sorted([f for f in os.listdir(year_path) if f.endswith('.txt')])
            if not file_list:
                continue

            # === 文档与句子分割 ===
            documents, all_sentences, doc_indices = [], [], []
            for fname in file_list:
                file_path = os.path.join(year_path, fname)
                text = None
                # 兼容多种常见编码（防止乱码/报错）
                for enc in ['utf-8', 'gbk', 'latin1', 'utf-16', 'big5']:
                    try:
                        with open(file_path, 'r', encoding=enc) as f:
                            text = f.read()
                        break
                    except Exception:
                        continue
                if not text:
                    print(f"⚠️ 跳过文件（无法读取编码）: {file_path}")
                    continue
                doc_id = len(documents)
                documents.append((fname, text))
                # 按“。！？\n”切句，句长大于10字符才纳入
                for s in re.split(r"[。！？\n]", text):
                    s = s.strip()
                    if len(s) > 10:
                        all_sentences.append(s)
                        doc_indices.append(doc_id)

            if not documents or not all_sentences:
                continue

            # ==== 提取行业关键词（用于主题二次归类）====
            combined_text = " ".join(doc_text for _, doc_text in documents)
            candidate_keywords = jieba.analyse.extract_tags(combined_text, topK=50)
            industry_keywords = candidate_keywords.copy()
            if industry_name and industry_name not in industry_keywords:
                industry_keywords.insert(0, industry_name)

            # ==== 通用主题归类 ====
            # 建立每个文档的通用主题句子列表
            common_assignments = [[] for _ in range(len(documents))]
            assigned_idx = set()  # 已经被分配通用主题的句子索引
            for topic, keywords in common_topics.items():
                for i, sent in enumerate(all_sentences):
                    if i in assigned_idx:
                        continue
                    if any(kw in sent for kw in keywords):
                        doc_id = doc_indices[i]
                        if doc_id >= len(common_assignments):
                            continue
                        common_assignments[doc_id].append((topic, sent))
                        assigned_idx.add(i)

            # ==== 行业主题归类（用BERTopic做未归类部分聚类） ====
            # 只对未归类的句子做聚类
            unassigned_sentences = [s for idx, s in enumerate(all_sentences) if idx not in assigned_idx]
            unassigned_indices = [doc_indices[idx] for idx in range(len(all_sentences)) if idx not in assigned_idx]

            if unassigned_sentences and len(unassigned_sentences) > 10:
                # 聚类主题数最多为句子数或6（二者取小）
                topic_model = BERTopic(
                    embedding_model=embedding_model,
                    language="chinese",
                    nr_topics=min(len(unassigned_sentences), 6)
                )
                topics, _ = topic_model.fit_transform(unassigned_sentences)

                # 统计每个聚类主题出现的行业关键词次数
                theme2indices = {}
                for j, topic_id in enumerate(topics):
                    theme2indices.setdefault(topic_id, []).append(j)
                theme_scores = {}
                theme_topword = {}
                for tid, idx_list in theme2indices.items():
                    cnt = Counter()
                    for j in idx_list:
                        sent = unassigned_sentences[j]
                        for kw in industry_keywords:
                            if kw in sent:
                                cnt[kw] += 1
                    theme_scores[tid] = sum(cnt.values())
                    theme_topword[tid] = cnt.most_common(1)[0][0] if cnt else None
                # 选行业主题
                if theme_scores:
                    top_theme_id = max(theme_scores.items(), key=lambda x: x[1])[0]
                else:
                    top_theme_id = max(theme2indices.items(), key=lambda x: len(x[1]))[0]
                main_keyword = theme_topword.get(top_theme_id) or "行业主题"
                industry_column_name = f"行业主题：{main_keyword}"
            else:
                top_theme_id = None
                industry_column_name = "行业主题"

            # ==== 汇总输出DataFrame ====
            result = pd.DataFrame()
            # 文件名列
            result["文件名"] = [os.path.splitext(name)[0] for name, _ in documents]
            # 通用主题列
            for topic in common_topics:
                result[topic] = [
                    " ".join([sent for t, sent in common_assignments[file_idx] if t == topic])
                    for file_idx in range(len(documents))
                ]
            # 行业主题列
            industry_column_data = []
            if top_theme_id is not None:
                for file_idx in range(len(documents)):
                    sentences_for_file = []
                    for j, sent in enumerate(unassigned_sentences):
                        if topics[j] == top_theme_id and unassigned_indices[j] == file_idx:
                            if any(kw in sent for kw in industry_keywords):
                                sentences_for_file.append(sent)
                    # 只取唯一句子，且最多5句，拼成一个字符串
                    unique_sents = []
                    for s in sentences_for_file:
                        if s not in unique_sents:
                            unique_sents.append(s)
                    industry_column_data.append(" ".join(unique_sents[:5]))
            else:
                industry_column_data = [""] * len(documents)
            result[industry_column_name] = industry_column_data

            # ==== 清洗非法控制字符，避免Excel读取报错 ====
            def clean_excel_string(x):
                if not isinstance(x, str):
                    x = str(x) if x is not None else ""
                return re.sub(r'[\x00-\x1F\x7F-\x9F]', '', x)
            result = result.applymap(clean_excel_string)

            # ==== 保存结果 ====
            output_file = os.path.join(output_industry_path, f"{industry_name}{year_dir}topic.xlsx")
            result.to_excel(output_file, index=False)
            print(f"✅ 已保存: {output_file}")

            # ==== 指针更新，防止重复处理 ====
            with open(pointer_file, "a") as f:
                f.write(industry_year_key + "\n")
            done_keys.add(industry_year_key)

        except Exception as e:
            print(f"❌ 处理 [{industry_name} {year_dir}] 时发生异常：{e}")
            continue  # 关键：异常也不影响后续行业/年份处理

print("🏁 全部任务执行完毕")