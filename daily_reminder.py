import os
import requests
from datetime import datetime
import pytz
from supabase import create_client, Client

# ==========================================
# 1. 配置参数与环境初始化
# ==========================================
# 从 GitHub Secrets 中读取 Supabase 配置
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("🚨 未找到 SUPABASE_URL 或 SUPABASE_KEY，请检查 GitHub Secrets 配置！")
    exit(1)

# 初始化 Supabase 客户端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 团队全员名单 (13人)
EMPLOYEES = [
    "彭玉桃", "刘佳", "曲寿康", "卢镇", "杨贵平", "郑家颖", 
    "刘伟华", "刘玥", "汪孝亮", "谢凌锋", "肖商华", "施明鸿", "李春维"
]

# 企业微信 Webhook 地址
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=239105cc-5427-444d-9c32-8ae624ed26fd"

# ==========================================
# 2. 获取北京时间今日日期
# ==========================================
tz_beijing = pytz.timezone('Asia/Shanghai')
# 获取北京时间的“今天”日期格式：YYYY-MM-DD
today_date = datetime.now(tz_beijing).strftime('%Y-%m-%d')
print(f"📅 当前处理日期（北京时间）: {today_date}")

# ==========================================
# 3. 数据库查询与名单比对
# ==========================================
try:
    # 构建北京时间今天的起止时间范围，精确匹配 timestamptz 格式 (+08:00)
    start_time = f"{today_date} 00:00:00+08:00"
    end_time = f"{today_date} 23:59:59+08:00"
    
    # 查询 work_logs 表，筛选 submit_time 在今天范围内的数据
    response = supabase.table('work_logs').select('name').gte('submit_time', start_time).lte('submit_time', end_time).execute()
    submitted_data = response.data
    
    print(f"🔍 数据库查询成功，今日已获取 {len(submitted_data)} 条提交记录。")
except Exception as e:
    print(f"🚨 数据库查询失败，错误信息: {e}")
    exit(1)

# 提取已交人员的姓名列表（使用 set 去重，防止同一人手抖提交多次）
submitted_names = list(set([record.get('name') for record in submitted_data if record.get('name')]))

# 对比全名单，抓出未交人员
missing_users = [name for name in EMPLOYEES if name not in submitted_names]
print(f"🧐 最终比对出的未交名单 ({len(missing_users)}人): {missing_users}")

# ==========================================
# 4. 发送企业微信提醒
# ==========================================
if missing_users:
    # 将名单拼接成字符串，用顿号隔开
    missing_names_str = "、".join(missing_users)
    
    # 构建发送内容 (Markdown 格式让展现更美观)
    message_data = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"## 📢 工作日志提交提醒\n\n**日期：** {today_date}\n\n截至目前，还有以下 **{len(missing_users)}** 位同事尚未提交今日的工作日志：\n\n<font color=\"warning\">**{missing_names_str}**</font>\n\n请大家抓紧时间提交哦！辛苦了！☕️"
        }
    }
    
    try:
        # 发送 POST 请求到企微 Webhook
        res = requests.post(WEBHOOK_URL, json=message_data)
        if res.status_code == 200:
            print(f"✅ 企业微信提醒发送成功: {res.json()}")
        else:
            print(f"⚠️ 企业微信提醒发送失败，状态码: {res.status_code}, 返回: {res.text}")
    except Exception as e:
        print(f"🚨 请求企业微信接口时发生错误: {e}")
else:
    print("🎉 太棒了！今天所有人都已经提交了工作日志，无需发送提醒。")
