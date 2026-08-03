import os
import requests
from datetime import datetime, timedelta
import pytz
from supabase import create_client, Client

# ==========================================
# 1. 配置参数与环境初始化
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("🚨 未找到 SUPABASE_URL 或 SUPABASE_KEY，请检查 GitHub Secrets 配置！")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 团队全员名单 (13人)
EMPLOYEES = [
    "卢镇", "杨贵平", "郑家颖", 
    "刘伟华", "刘玥", "汪孝亮", "谢凌锋", "肖商华", "施明鸿", "李春维"
]

# 企业微信 Webhook 地址
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=239105cc-5427-444d-9c32-8ae624ed26fd"

# ==========================================
# 2. 智能获取目标查询日期 (解决零点跨日问题)
# ==========================================
tz_beijing = pytz.timezone('Asia/Shanghai')
now_bjt = datetime.now(tz_beijing)

# 如果当前时间是凌晨 0 点到 4 点之间（涵盖 24:00 的检查），说明需要统计的是“昨天”的日志
if now_bjt.hour < 4:
    target_date_obj = now_bjt - timedelta(days=1)
    target_date = target_date_obj.strftime('%Y-%m-%d')
    time_label = "昨晚"
else:
    target_date = now_bjt.strftime('%Y-%m-%d')
    time_label = "今日"

print(f"⏰ 当前执行时间: {now_bjt.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📅 目标查询日期: {target_date} ({time_label})")

# ==========================================
# 3. 数据库查询与名单比对
# ==========================================
try:
    # 锁定目标日期的 00:00:00 到 23:59:59 (北京时间 +08:00)
    start_time = f"{target_date} 00:00:00+08:00"
    end_time = f"{target_date} 23:59:59+08:00"
    
    response = supabase.table('work_logs').select('name').gte('submit_time', start_time).lte('submit_time', end_time).execute()
    submitted_data = response.data
    
    print(f"🔍 数据库查询成功，已获取 {target_date} 的 {len(submitted_data)} 条记录。")
except Exception as e:
    print(f"🚨 数据库查询失败，错误信息: {e}")
    exit(1)

submitted_names = list(set([record.get('name') for record in submitted_data if record.get('name')]))
missing_users = [name for name in EMPLOYEES if name not in submitted_names]
print(f"🧐 最终未交名单 ({len(missing_users)}人): {missing_users}")

# ==========================================
# 4. 发送企业微信提醒
# ==========================================
if missing_users:
    missing_names_str = "、".join(missing_users)
    
    # 针对不同时间段稍微调整文案
    if now_bjt.hour == 0:
        greeting = "夜深了，本日的日志统计即将结束啦！"
    else:
        greeting = f"现在是 {now_bjt.hour} 点，大家记得提交工作日志哦！"
        
    message_data = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"## 📢 工作日志提交提醒\n\n**针对日期：** {target_date}\n\n{greeting}\n\n截至目前，还有以下 **{len(missing_users)}** 位同事尚未提交：\n\n<font color=\"warning\">**{missing_names_str}**</font>\n\n请大家抓紧时间提交！☕️"
        }
    }
    
    try:
        res = requests.post(WEBHOOK_URL, json=message_data)
        if res.status_code == 200:
            print(f"✅ 企业微信提醒发送成功: {res.json()}")
        else:
            print(f"⚠️ 企业微信提醒发送失败，状态码: {res.status_code}, 返回: {res.text}")
    except Exception as e:
        print(f"🚨 请求企业微信接口时发生错误: {e}")
else:
    print(f"🎉 太棒了！{target_date} 所有人都已经提交了工作日志，无需发送提醒。")
