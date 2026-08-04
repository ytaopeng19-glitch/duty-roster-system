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

# 从 GitHub Secrets 中读取您的 API Key (AQ. 开头的那个)
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
    # 默认模式：自动获取前一天（昨天）
    target_date = (datetime.now(TIMEZONE) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 想要测试特定日期（如 8月3日），请取消下一行的注释
    target_date = "2026-08-03" 
    
    print(f"开始执行 {target_date} 的日志分析任务...")

    all_logs_text = ""
    file_count = 0

    try:
        files = supabase.storage.from_(STORAGE_BUCKET_NAME).list("logs")
        
        for file in files:
            file_name = file.get('name', '')
            
            if not file_name or file_name.startswith('.'):
                continue
                
            created_at_str = file.get('created_at') 
            is_target_date = False
            
            if created_at_str:
                try:
                    utc_dt = datetime.strptime(created_at_str[:19], "%Y-%m-%dT%H:%M:%S")
                    utc_dt = pytz.utc.localize(utc_dt)
                    cn_dt = utc_dt.astimezone(TIMEZONE)
                    file_date = cn_dt.strftime("%Y-%m-%d")
                    
                    if file_date == target_date:
                        is_target_date = True
                except Exception as e:
                    print(f"时间解析失败 {file_name}: {e}")

            if is_target_date:
                file_path = f"logs/{file_name}"
                print(f"成功匹配到文件: {file_path}")
                
                response = supabase.storage.from_(STORAGE_BUCKET_NAME).download(file_path)
                
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

    prompt = f"""
你是一个专业的实验室数据分析助手。以下是（{target_date}）团队成员提交的 {file_count} 份工作日志汇总。
请帮助我从繁杂的日志中提炼关键信息，并严格按照以下维度生成一份清晰、专业的 Markdown 简报。

【重点关注领域】：
1. **仪器管理与维护**：所有涉及仪器的运行状态、故障报警、维修进度或保养记录。
2. **细胞房管理**：细胞培养环境状态、污染风险、消耗品使用情况及合规操作记录。

【严格过滤规则】：
请在简报中彻底剔除任何关于教学任务、行政领导管理或团队建设凝聚力等不相关的内容，仅保留纯粹的技术服务、实验进展和硬件管理信息。

需生成的简报结构：
## 🔬 实验室综合运行简报 ({target_date})

### 🟢 核心运行动态
(简明扼要地总结当天实验室整体的仪器和细胞房运转情况)

### ⚠️ 潜在隐患与异常排查
(仔细检查日志，是否有任何仪器异常、细胞污染风险、耗材短缺或违规操作。如果没有，请明确回复“未见异常”)

### 🛠️ 仪器维护追踪
(列出提到的具体仪器名称及其状态，方便后续跟进)

### 📊 其他技术注意事项
(仅保留与科研实验、技术服务进展相关的有价值信息，剔除行政与教学内容)

---
以下是收集到的原始日志内容：
{all_logs_text}
"""

    print("正在调用 Gemini API 进行深度智能分析...")
    
    # 显式传递从环境变量获取的真实 API Key
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 修正了模型名称，并去掉了不存在的 3.6 版本
    models_to_try = ['gemini-2.5-flash', 'gemini-1.5-pro', 'gemini-1.5-flash']
    ai_summary = None
    
    for model_name in models_to_try:
        try:
            print(f"正在尝试使用 {model_name} 模型...")
            
            # 👇 核心修复：使用了官方标准的 generate_content 接口，完美支持 API Key
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            ai_summary = response.text
            
            print(f"✅ 成功使用 {model_name} 完成分析！")
            break 
        except Exception as e:
            print(f"⚠️ 模型 {model_name} 报错，尝试下一个... (错误信息: {e})")

    if ai_summary:
        send_wxpusher_message(ai_summary, f"🤖 实验室智能简报 ({target_date})", [ADMIN_UID])
        print("智能简报已成功推送到您的微信！")
    else:
        error_msg = "所有可用模型均调用失败，请检查 API Key 权限或网络限制。"
        print(error_msg)
        send_wxpusher_message(f"## ❌ AI 分析失败\n\n{error_msg}", "AI 分析接口报错", [ADMIN_UID])

if __name__ == "__main__":
    main()
