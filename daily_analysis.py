import os
import requests
from datetime import datetime, timedelta
import pytz
from supabase import create_client, Client
import google.generativeai as genai
import io
from docx import Document

# ==========================================
# 1. 环境变量与初始化
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
WXPUSHER_APP_TOKEN = os.environ.get("WXPUSHER_APP_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY, WXPUSHER_APP_TOKEN, GEMINI_API_KEY]):
    print("🚨 环境变量缺失，请检查 GitHub Secrets (需包含 GEMINI_API_KEY)。")
    exit(1)

# 初始化 Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# 您的 Supabase 存储桶名称（请根据实际情况修改，可能是 logs 或 work_logs）
STORAGE_BUCKET_NAME = "logs" 

# 初始化 Gemini
genai.configure(api_key=GEMINI_API_KEY)
# 推荐使用 gemini-1.5-flash，速度快且适合文本总结
model = genai.GenerativeModel('gemini-1.5-flash')

# 管理员 WxPusher UID (仅发给您自己)
ADMIN_UID = "UID_填入您的真实UID" 

# ==========================================
# 2. 获取昨天的所有日志记录
# ==========================================
tz_beijing = pytz.timezone('Asia/Shanghai')
# 分析任务通常在凌晨运行，所以统计的是“昨天”的日志
yesterday_date = (datetime.now(tz_beijing) - timedelta(days=1)).strftime('%Y-%m-%d')

start_time = f"{yesterday_date} 00:00:00+08:00"
end_time = f"{yesterday_date} 23:59:59+08:00"

try:
    response = supabase.table('work_logs').select('name, file_path').gte('submit_time', start_time).lte('submit_time', end_time).execute()
    logs_data = response.data
    print(f"🔍 查找到 {yesterday_date} 共 {len(logs_data)} 份工作日志文件。")
except Exception as e:
    print(f"🚨 数据库查询失败: {e}")
    exit(1)

if not logs_data:
    print("今日无日志可分析，任务结束。")
    exit(0)

# ==========================================
# 3. 下载并提取 Word 文档文字
# ==========================================
all_logs_text = ""
for log in logs_data:
    name = log.get('name')
    file_path = log.get('file_path')
    
    if not file_path:
        continue
        
    try:
        # 如果数据库中的 file_path 包含了桶名(如 logs/xxx.docx)，需要切片提取纯路径
        # 若存储的本就是纯路径，直接使用即可
        actual_path = file_path.replace(f"{STORAGE_BUCKET_NAME}/", "") if file_path.startswith(f"{STORAGE_BUCKET_NAME}/") else file_path
        
        # 从 Supabase 下载文件二进制流
        file_bytes = supabase.storage.from_(STORAGE_BUCKET_NAME).download(actual_path)
        
        # 使用 python-docx 读取内存中的 docx 文件
        doc = Document(io.BytesIO(file_bytes))
        extracted_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        
        all_logs_text += f"\n\n【汇报人：{name}】\n{extracted_text}"
        print(f"✅ 成功读取 {name} 的日志。")
    except Exception as e:
        print(f"⚠️ 读取 {name} 的文件 ({file_path}) 失败: {e}")
        all_logs_text += f"\n\n【汇报人：{name}】\n(文件读取失败，未获取到内容)"

# ==========================================
# 4. 调用 Gemini API 进行智能分析
# ==========================================
# 定制化 Prompt，紧扣您的核心管理职责
prompt = f"""
你是一个专业的生物与农业实验室管理 AI 助手。以下是团队成员于 {yesterday_date} 提交的工作日志汇总。
实验室的核心管理职责严格聚焦于：仪器管理、仪器设备维护、以及细胞房的规范运作，不涉及任何行政领导或教学任务。

请你阅读所有日志，并输出一份结构清晰的《实验室运行智能简报》。简报必须包含以下三个模块：
1. 🔬 总体运行概况：一句话总结今日仪器与细胞房的运转是否平稳。
2. ⚠️ 异常与隐患排查：详细列出日志中提及的仪器故障、参数异常、耗材短缺或细胞污染等问题，并指出对应的汇报人。若无，请写“未发现明显异常”。
3. 📊 工作量与记录质量：指出哪些成员完成了实质性的仪器/细胞维护工作；同时客观指出是否有人日志内容过于空泛、缺乏具体操作细节。

以下是今日的日志内容：
{all_logs_text}
"""

print("🚀 正在呼叫 Gemini 分析日志内容...")
try:
    ai_response = model.generate_content(prompt)
    analysis_result = ai_response.text
    print("✅ Gemini 分析完成！")
except Exception as e:
    print(f"🚨 Gemini API 调用失败: {e}")
    exit(1)

# ==========================================
# 5. 通过 WxPusher 发送给管理员
# ==========================================
wxpusher_payload = {
    "appToken": WXPUSHER_APP_TOKEN,
    "content": f"## 📊 {yesterday_date} 实验室智能简报\n\n{analysis_result}",
    "summary": f"📊 {yesterday_date} 实验室运行简报",
    "contentType": 3, # 3 代表 Markdown 格式
    "uids": [ADMIN_UID]
}

try:
    res = requests.post("https://wxpusher.zjiecode.com/api/send/message", json=wxpusher_payload)
    if res.status_code == 200 and res.json().get('code') == 1000:
        print("✅ 智能简报已成功推送到管理员微信！")
    else:
        print(f"⚠️ 简报推送可能失败，返回: {res.json()}")
except Exception as e:
    print(f"🚨 WxPusher 推送异常: {e}")
