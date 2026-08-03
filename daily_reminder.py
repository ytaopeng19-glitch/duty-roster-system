import os
import requests
from supabase import create_client
from datetime import date, datetime, timedelta, timezone

# 1. 配置 Supabase 连接 (替换为您真实的 URL 和 KEY)
SUPABASE_URL = "您的_SUPABASE_URL"
SUPABASE_KEY = "您的_SUPABASE_KEY"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. 从系统中同步员工名单
EMPLOYEES = {
    "26001": "郑家颖", "26002": "刘伟华", "24001": "谢凌锋",
    "24002": "肖商华", "24003": "刘玥",   "25001": "汪孝亮",
    "25002": "施明鸿", "26003": "李春维", "26004": "卢镇",
    "12002": "刘佳",   "12001": "曲寿康", "24000": "彭宇涛",
    "26005": "杨贵平"
}
all_names = list(EMPLOYEES.values())

def check_and_remind():
    # 获取东八区今天的日期
    tz_utc_8 = timezone(timedelta(hours=8))
    today_str = str(datetime.now(tz_utc_8).date())
    
    # 3. 从数据库查询今天已提交日志的人员
    try:
        response = supabase.table("work_logs").select("name").gte("submit_time", today_str).execute()
        submitted_names = [record['name'] for record in response.data]
    except Exception as e:
        print(f"数据库查询失败: {e}")
        return

    # 4. 对比找出未提交的人员
    missing_names = [name for name in all_names if name not in submitted_names]
    
    # 5. 如果有人没交，则触发群机器人发送消息
    if missing_names:
        missing_str = "、".join(missing_names)
        message = f"📢 晚间温馨提示：\n截至目前，以下同事尚未提交今日的工作日志：\n**{missing_str}**\n请大家抓紧时间登录系统提交哦！"
        send_group_message(message)
    else:
        print("所有人均已提交，无需提醒。")

def send_group_message(text):
    # ==========================================
    # 这里以【企业微信群机器人】为例
    # 您需要在企业微信群设置里添加一个机器人，并获取它的 Webhook 地址
    # ==========================================
    webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=您的机器人KEY"
    
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": text
        }
    }
    
    try:
        requests.post(webhook_url, json=payload)
        print("提醒消息发送成功！")
    except Exception as e:
        print(f"消息发送失败: {e}")

if __name__ == "__main__":
    check_and_remind()