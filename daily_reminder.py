import os
import requests
from datetime import datetime
import pytz
from supabase import create_client

# ==========================================
# 1. 基础配置与鉴权 (双重保险策略)
# ==========================================
# 注意：GitHub Actions 环境不支持 Streamlit 的 st.secrets 用法。
# 这里采用双重保险：优先读 Secrets，读不到则直接使用您提供的硬编码参数。
SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", 
    "https://srzfkhiminxmbrbdipay.supabase.co"
).strip()

SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY", 
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNyemZraGltaW54bWJyYmRpcGF5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2OTgyOTcsImV4cCI6MjA4ODI3NDI5N30.jI9aum5Qe5eniH-oHBiRyIo41EpKUIDedkH-2vHiPnw"
).strip()

# 您的企业微信机器人 Webhook 真实地址
WECOM_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=239105cc-5427-444d-9c32-8ae624ed26fd"

# 初始化 Supabase 客户端
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"🚨 数据库客户端初始化失败: {e}")
    exit(1)

# ==========================================
# 2. 时间与人员配置
# ==========================================
# 强制使用北京时间，精准锁定“今天”
tz = pytz.timezone('Asia/Shanghai')
today_date = datetime.now(tz).strftime('%Y-%m-%d')
print(f"📅 当前处理日期 (北京时间): {today_date}")

# 13人完整员工名单
EMPLOYEES = [
    "彭玉桃", "刘佳", "曲寿康", 
    "卢镇", "杨贵平", "郑家颖", "刘伟华", "刘玥", 
    "汪孝亮", "谢凌锋", "肖商华", "施明鸿", "李春维"
]

# ==========================================
# 3. 数据库查询与名单比对
# ==========================================
try:
    response = supabase.table('logs').select('name').eq('date', today_date).execute()
    submitted_data = response.data
    print(f"🔍 数据库查询成功，今日已有 {len(submitted_data)} 人提交日志。")
    print(f"📋 今日已交人员明细: {submitted_data}")
except Exception as e:
    print(f"🚨 数据库查询失败，错误信息: {e}")
    exit(1)

# 提取已交人员的姓名列表
submitted_names = [record.get('name') for record in submitted_data]

# 对比全名单，抓出未交人员
missing_users = [name for name in EMPLOYEES if name not in submitted_names]
print(f"🧐 最终比对出的未交名单 ({len(missing_users)}人): {missing_users}")

# ==========================================
# 4. 企业微信消息推送
# ==========================================
if not missing_users:
    print("🎉 太棒了！今天全员（13人）均已提交工作日志，无需发送催收提醒。")
else:
    print("🚀 准备向企业微信发送催交提醒...")
    missing_str = "、".join(missing_users)
    
    # 构建 Markdown 格式的企业微信消息
    msg_data = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"### ⚠️ 仪器与细胞房值班日志未交提醒\n\n日期：<font color='info'>{today_date}</font>\n\n**以下同事尚未提交今日日志**：\n<font color='warning'>{missing_str}</font>\n\n> 实验室规范运转离不开大家的协助，请以上同事尽快通过系统提交今日工作内容，辛苦啦！"
        }
    }

    try:
        res = requests.post(WECOM_WEBHOOK_URL, json=msg_data)
        print(f"📡 企业微信服务器响应状态码: {res.status_code}")
        print(f"📡 企业微信服务器响应内容: {res.text}")
        
        if res.status_code == 200 and res.json().get('errcode') == 0:
            print("✅ 提醒消息发送成功！您的企业微信群应该已经收到消息。")
        else:
            print("❌ 消息发送可能失败，请检查上方返回的报错内容。")
            
    except Exception as e:
        print(f"🚨 请求企业微信接口发生网络异常: {e}")
