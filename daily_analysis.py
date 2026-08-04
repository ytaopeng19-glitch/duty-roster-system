import os
import io
import requests
from datetime import datetime, timedelta
import pytz
from docx import Document
import google.generativeai as genai
from supabase import create_client, Client

# ==========================================
# 1. 配置与环境变量
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
WXPUSHER_APP_TOKEN = os.environ.get("WXPUSHER_APP_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 核心配置
STORAGE_BUCKET_NAME = "work_logs"
ADMIN_UID = "UID_U5GlQEGcsb24mLT0M5wupOdDd6L0" 
TIMEZONE = pytz.timezone('Asia/Shanghai')

# ==========================================
# 2. 初始化客户端
# ==========================================
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel('gemini-1.5-pro')

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
        # 如果上传的不是 Word 文档，这里会静默拦截报错
        print(f"解析文档失败 (可能不是有效的Word文件): {e}")
        return ""

def main():
    # =======================================================
    # 🚀 日期控制中心
    # =======================================================
    # 默认模式：自动获取前一天（昨天）
    target_date = (datetime.now(TIMEZONE) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 想要测试特定日期（如 8月3日），请取消下一行的注释（注意删除行首 # 时，不要破坏对齐的空格！）
    target_date = "2026-08-03" 
    
    print(f"开始执行 {target_date} 的日志分析任务...")

    all_logs_text = ""
    file_count = 0

    try:
        # 【关键修改 1】进入 logs 文件夹读取列表
        files = supabase.storage.from_(STORAGE_BUCKET_NAME).list("logs")
        
        for file in files:
            file_name = file.get('name', '')
            
            # 跳过空文件或隐藏文件
            if not file_name or file_name.startswith('.'):
                continue
                
            # 【关键修改 2】利用 Supabase 记录的创建时间，而不是文件名来判定日期
            created_at_str = file.get('created_at') 
            is_target_date = False
            
            if created_at_str:
                try:
                    # 将 Supabase 的 UTC 时间转换为北京时间
                    utc_dt = datetime.strptime(created_at_str[:19], "%Y-%m-%dT%H:%M:%S")
                    utc_dt = pytz.utc.localize(utc_dt)
                    cn_dt = utc_dt.astimezone(TIMEZONE)
                    file_date = cn_dt.strftime("%Y-%m-%d")
                    
                    if file_date == target_date:
                        is_target_date = True
                except Exception as e:
                    print(f"时间解析失败 {file_name}: {e}")

            if is_target_date:
                # 【关键修改 3】下载时的路径必须补全 logs/ 文件夹路径
                file_path = f"logs/{file_name}"
                print(f"成功匹配到文件: {file_path}")
                
                # 下载文件
                response = supabase.storage.from_(STORAGE_BUCKET_NAME).download(file_path)
                
                # 提取文本
                text = extract_text_from_docx(response)
                if text:
                    all_logs_text += f"\n\n--- 【日志 ID: {file_name[:8]}...】 ---\n{text}"
                    file_count += 1
                    
    except Exception as e:
        error_msg = f"访问 Supabase 存储桶失败或发生异常: {e}"
        print(error_msg)
        send_wxpusher_message(f"## ❌ 日志分析系统异常\n\n{error_msg}", "日志分析系统报错", [ADMIN_UID])
        return

    if file_count == 0 or not all_logs_text.strip():
        print(f"{target_date} 暂无有效日志提取。")
        send_wxpusher_message(
            f"## 📭 实验室日志简报 ({target_date})\n\n系统未能在 `{STORAGE_BUCKET_NAME}` 存储桶的 `logs` 文件夹中检测到 {target_date} 的任何有效 Word 日志，请核实团队成员提交情况。",
            f"无日志提交 ({target_date})",
            [ADMIN_UID]
        )
        return

    # 组织 Prompt
    prompt = f"""
你是一个专业的实验室数据分析助手。以下是（{target_date}）团队成员提交的 {file_count} 份工作日志汇总。
作为实验室的管理者，我需要你帮我从繁杂的日志中提炼关键信息。请严格按照以下维度生成一份清晰、专业的 Markdown 简报。

重点关注领域：
1. **仪器管理与维护**：所有涉及仪器的运行状态、故障报警、维修进度或保养记录。
2. **细胞房管理**：细胞培养环境状态、污染风险、消耗品使用情况及合规操作记录。

需生成的简报结构：
## 🔬 实验室综合运行简报 ({target_date})

### 🟢 核心运行动态
(简明扼要地总结当天实验室整体的仪器和细胞房运转情况)

### ⚠️ 潜在隐患与异常排查
(仔细检查日志，是否有任何仪器异常、细胞污染风险、耗材短缺或违规操作。如果没有，请明确回复“未见异常”)

### 🛠️ 仪器维护追踪
(列出提到的具体仪器名称及其状态，方便后续跟进)

### 📊 其他值得注意的事项
(剔除行政管理、教学等无关事项，仅保留与科研实验、技术服务进展相关的有价值信息)

---
以下是收集到的原始日志内容：
{all_logs_text}
"""

    print("正在调用 Gemini Pro 进行深度智能分析...")
    try:
        response = model.generate_content(prompt)
        ai_summary = response.text
        
        send_wxpusher_message(ai_summary, f"🤖 实验室智能简报 ({target_date})", [ADMIN_UID])
        print("智能简报已成功推送到您的微信！")
        
    except Exception as e:
        error_msg = f"Gemini API 调用失败: {e}"
        print(error_msg)
        send_wxpusher_message(f"## ❌ AI 分析失败\n\n{error_msg}", "AI 分析接口报错", [ADMIN_UID])

if __name__ == "__main__":
    main()
