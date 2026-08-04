import os
import io
import requests
from datetime import datetime, timedelta
import pytz
from docx import Document
from google import genai 
from supabase import create_client, Client

# ==========================================
# 1. 配置与环境变量
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
WXPUSHER_APP_TOKEN = os.environ.get("WXPUSHER_APP_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

ADMIN_UID = "UID_U5GlQEGcsb24mLT0M5wupOdDd6L0" 

# 核心配置
STORAGE_BUCKET_NAME = "work_logs"
TIMEZONE = pytz.timezone('Asia/Shanghai')

# ==========================================
# 2. 初始化 Supabase 客户端
# ==========================================
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def send_wxpusher_message(content, summary, uids):
    """通过 WxPusher 发送消息给管理员"""
    url = "https://wxpusher.zjiecode.com/api/send/message"
    payload = {
        "appToken": WXPUSHER_APP_TOKEN,
        "content": content,
        "summary": summary,
        "contentType": 3,
        "uids": uids
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("WxPusher 消息发送成功")
    except Exception as e:
        print(f"WxPusher 发送失败: {e}")

def extract_text_from_docx(file_bytes):
    """从 docx 字节流中提取纯文本"""
    try:
        doc = Document(io.BytesIO(file_bytes))
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text.strip())
        return '\n'.join(full_text)
    except Exception as e:
        print(f"解析文档失败: {e}")
        return ""

def main():
    if not GEMINI_API_KEY:
        print("错误：未找到 GEMINI_API_KEY 环境变量，请检查 GitHub Secrets 配置。")
        return
        
    print(f"🔍 检查点：当前加载的 API Key 前缀为 [{GEMINI_API_KEY[:6]}]")

    # =======================================================
    # 🚀 日期控制中心
    # =======================================================
    # 在每天早上 7:15 运行时，减去 1 天，完美匹配昨天上传的日志
    target_date = (datetime.now(TIMEZONE) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # [调试专用]
    # target_date = "2026-08-04" 
    
    print(f"开始执行 {target_date} 的日志分析任务...")

    all_logs_text = ""
    file_count = 0
    
    # 用于存储每位同事的直达下载/查看链接
    individual_links = []

    # =======================================================
    # 📂 通过数据库查询，解析日志并生成独立外链
    # =======================================================
    try:
        three_days_ago = (datetime.now(TIMEZONE) - timedelta(days=3)).strftime("%Y-%m-%d")
        response = supabase.table("work_logs").select("*").gte("submit_time", three_days_ago).execute()
        logs_data = response.data

        if not logs_data:
            print("近三天内数据库中无任何日志记录。")
        else:
            for log in logs_data:
                submit_time_str = log.get('submit_time')
                
                if not submit_time_str:
                    continue

                try:
                    utc_dt = datetime.strptime(submit_time_str[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
                    utc_dt = pytz.utc.localize(utc_dt)
                    cn_dt = utc_dt.astimezone(TIMEZONE)
                    file_date = cn_dt.strftime("%Y-%m-%d")
                    
                    if file_date == target_date:
                        real_file_name = log.get('file_name', '未知文件名')
                        submitter_name = log.get('name', '未知提交人')
                        storage_path = log.get('file_path')
                        
                        print(f"成功匹配到日志: {submitter_name} - {real_file_name}")
                        
                        # 下载实际的文件字节流用于 AI 解析
                        file_bytes = supabase.storage.from_(STORAGE_BUCKET_NAME).download(storage_path)
                        
                        # 获取该文件的公共直达链接，并存入列表
                        file_url = supabase.storage.from_(STORAGE_BUCKET_NAME).get_public_url(storage_path)
                        individual_links.append(f"- 👤 **{submitter_name}**: [{real_file_name}]({file_url})")
                        
                        # 解析文本供 AI 使用
                        text = extract_text_from_docx(file_bytes)
                        if text:
                            all_logs_text += f"\n\n========================================\n"
                            all_logs_text += f"【日志提交人】: {submitter_name}\n"
                            all_logs_text += f"【原始文件名】: {real_file_name}\n"
                            all_logs_text += f"【具体工作内容】:\n{text}\n"
                            all_logs_text += f"========================================\n"
                            file_count += 1
                            
                except Exception as e:
                    print(f"处理日志条目时失败 ({log.get('file_name')}): {e}")
                    
    except Exception as e:
        error_msg = f"访问 Supabase 数据库/存储桶失败或发生异常: {e}"
        print(error_msg)
        send_wxpusher_message(f"## ❌ 日志分析系统异常\n\n{error_msg}", "日志分析系统报错", [ADMIN_UID])
        return

    if file_count == 0 or not all_logs_text.strip():
        print(f"{target_date} 暂无有效日志提取。")
        send_wxpusher_message(
            f"## 📭 实验室日志简报 ({target_date})\n\n系统未能在数据库中检测到 {target_date} 的任何有效 Word 日志，请核实团队成员提交情况。",
            f"无日志提交 ({target_date})",
            [ADMIN_UID]
        )
        return

    # =======================================================
    # 🧠 生成 AI 分析 Prompt
    # =======================================================
    prompt = f"""
你是一个专业的科研团队效能分析与数据审查专家。以下是（{target_date}）团队成员提交的 {file_count} 份工作日志汇总。
请帮助我深度剖析日志内容，并严格按照以下维度生成一份直击痛点的 Markdown 简报。

【重点审查领域】：
1. **项目试验进展分类**：将杂乱的日志按具体的项目或研究领域进行结构化归纳。
2. **工作效能与负荷评估**：犀利地评估工作饱和度，敏锐抓取进度异常迟缓或“摸鱼/偷懒”的迹象。
3. **跨领域问题与风险排查**：在不同项目和实验中，敏锐地嗅探隐藏的技术瓶颈、工艺缺陷或潜在隐患。

【严格过滤规则】：
彻底剔除任何关于教学任务、行政事务等不相关的内容。无需汇报常规的细胞培养或环境巡检流水账，将所有算力集中在“项目实质性进展”、“异常排查”和“效能监督”上。

需生成的简报结构：
## 📊 实验室科研效能与项目简报 ({target_date})

### 🔬 项目试验进展归纳
(请将当天的日志内容按不同的“项目名称”或“研究领域”进行分类，提炼每个领域的核心实质性进展。结构要求极度清晰，必须采用列表形式，不要写废话)

### ⏱️ 效能追踪与工作量穿透
(客观、犀利地评估当天汇总的工作量。明确表扬哪些项目推进迅速、工作量极度饱满；**必须严厉指出**哪些环节或人员的日志内容单薄、实质性产出少、进度明显停滞，存在“偷懒”或效率低下的嫌疑)

### ⚠️ 各领域问题与潜在风险剖析
(打通各领域信息，指出目前实验中已暴露或预测即将遇到的问题。例如：某工艺步骤不稳定、材料制备存在缺陷、数据验证可能遇到的瓶颈等，并给出简明的技术预警)

---
以下是收集到的原始日志内容：
{all_logs_text}
"""

    print("正在调用 Gemini API 进行深度智能分析...")
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    models_to_try = ['gemini-2.5-pro', 'gemini-1.5-pro', 'gemini-2.5-flash', 'gemini-flash-latest']
    try:
        available_models = client.models.list()
        for m in available_models:
            name = m.name.replace("models/", "") if m.name.startswith("models/") else m.name
            if "gemini" in name:
                models_to_try.append(name)
    except Exception as e:
        print(f"⚠️ 动态获取模型列表失败: {e}")
        models_to_try = ['gemini-2.0-flash', 'gemini-flash', 'gemini-pro']

    ai_summary = None
    
    if not models_to_try:
        send_wxpusher_message(f"## ❌ AI 分析失败\n\n未找到任何支持的 Gemini 模型", "无可用模型", [ADMIN_UID])
    else:
        for model_name in models_to_try:
            try:
                print(f"尝试使用 {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                ai_summary = response.text
                print(f"✅ 成功使用 {model_name} 完成分析！")
                break
            except Exception as e:
                print(f"⚠️ {model_name} 报错: {e}")

    # =======================================================
    # 📲 推送最终结果（包含独立下载链接清单）
    # =======================================================
    if ai_summary:
        # 将生成的单链接列表拼接成 Markdown 文本
        links_markdown = "\n".join(individual_links)
        
        # 将所有人日志的独立链接拼接到 AI 简报的末尾
        final_message = f"{ai_summary}\n\n---\n### 🔗 原始日志直达链接\n{links_markdown}"
        
        send_wxpusher_message(final_message, f"🤖 实验室智能简报 ({target_date})", [ADMIN_UID])
        print("智能简报及单文件快捷链接已成功推送到您的微信！")
    else:
        error_msg = "扫描到的所有可用模型均生成失败，请检查 API 调用额度或网络状态。"
        send_wxpusher_message(f"## ❌ AI 分析失败\n\n{error_msg}", "AI 分析接口报错", [ADMIN_UID])

if __name__ == "__main__":
    main()
