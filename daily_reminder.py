import os
import requests
import json
from supabase import create_client
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 数据库与机器人基础配置
# ==========================================
# ⚠️ 请确保在运行环境中设置了这两个环境变量，或者直接在这里替换成您的真实 URL 和 KEY
SUPABASE_URL = os.environ.get("https://srzfkhiminxmbrbdipay.supabase.co", "请替换为您真实的_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNyemZraGltaW54bWJyYmRpcGF5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2OTgyOTcsImV4cCI6MjA4ODI3NDI5N30.jI9aum5Qe5eniH-oHBiRyIo41EpKUIDedkH-2vHiPnw", "请替换为您真实的_SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=239105cc-5427-444d-9c32-8ae624ed26fd"

# 系统全体员工名单[cite: 1]
EMPLOYEES = {
    "26001": "郑家颖", "26002": "刘伟华", "24001": "谢凌锋",
    "24002": "肖商华", "24003": "刘玥",   "25001": "汪孝亮",
    "25002": "施明鸿", "26003": "李春维", "26004": "卢镇",
    "12002": "刘佳",   "12001": "曲寿康", "24000": "彭宇涛",
    "26005": "杨贵平"
}
all_names = list(EMPLOYEES.values())

# ==========================================
# 2. 核心检测逻辑
# ==========================================
def check_and_remind():
    print("开始检测今日工作日志提交情况...")
    
    # 获取北京时间（东八区）的今天日期
    tz_utc_8 = timezone(timedelta(hours=8))
    today_str = str(datetime.now(tz_utc_8).date())
    
    try:
        # 从 Supabase 查询今天提交过日志的记录[cite: 1]
        response = supabase.table("work_logs").select("name").gte("submit_time", today_str).execute()
        
        # 提取已提交人的姓名（去重）
        submitted_names = list(set([record['name'] for record in response.data]))
        print(f"今日已提交人员: {submitted_names}")
        
    except Exception as e:
        print(f"❌ 数据库查询失败，请检查连接: {e}")
        return

    # 对比找出未提交的人员
    missing_names = [name for name in all_names if name not in submitted_names]
    
    if missing_names:
        print(f"检测到 {len(missing_names)} 人未提交，准备发送企业微信提醒...")
        send_wecom_message(missing_names)
    else:
        print("🎉 太棒了，所有人均已提交今日日志，无需发送提醒。")

# ==========================================
# 3. 企业微信消息发送逻辑
# ==========================================
def send_wecom_message(missing_names):
    missing_str = "、".join(missing_names)
    
    # 构造 Markdown 格式的消息体
    content = f"""<font color="warning">📢 晚间工作日志提交提醒</font>
    
截至目前，以下同事尚未提交今日的工作日志：
<font color="info">**{missing_str}**</font>
    
请大家抓紧时间登录系统提交，辛苦啦！💪
> 系统传送门：[点击这里登录研发协同管理系统](您的系统公网网址请填在这里)"""

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(payload))
        result = response.json()
        
        if result.get('errcode') == 0:
            print("✅ 企业微信提醒发送成功！群里应该已经收到了。")
        else:
            print(f"❌ 发送失败，企业微信返回错误：{result}")
            
    except Exception as e:
        print(f"❌ 网络请求异常: {e}")

if __name__ == "__main__":
    check_and_remind()
