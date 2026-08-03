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

# 🌟 双保险机制：优先读取环境变量，如果失败则使用硬编码的 Token
WXPUSHER_APP_TOKEN = os.environ.get("WXPUSHER_APP_TOKEN", "AT_MfUfjZyQIwgpADpyCiWaU0opaJAt6Xdc")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("🚨 致命错误：缺少 SUPABASE_URL 或 SUPABASE_KEY，请检查 GitHub Secrets！")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🌟 渠道一配置：两个企业微信群的 Webhook 地址
WEBHOOK_URLS = [
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=2eef95c2-45af-4025-9cec-83778d2cc787", 
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=239105cc-5427-444d-9c32-8ae624ed26fd"  
]

# 🌟 渠道二配置：将名字与每个人的 WxPusher UID 对应起来 (用于发送普通微信)
EMPLOYEES_UIDS = {
    "彭宇涛": "UID_U5GlQEGcsb24mLT0M5wupOdDd6L0", # 兼容数据库可能存在不同字体的录入
    "卢镇": "UID_填入卢镇的UID",
    "杨贵平": "UID_填入杨贵平的UID",
    "郑家颖": "UID_填入郑家颖的UID",
    "刘伟华": "UID_填入刘伟华的UID",
    "刘玥": "UID_填入刘玥的UID",
    "汪孝亮": "UID_62rugIUleiKauKO3fMrFL5znJIWp",
    "谢凌锋": "UID_填入谢凌锋的UID",
    "肖商华": "UID_QMTnwObkgP03cPb2Rmv3ITiacrzQ",
    "施明鸿": "UID_填入施明鸿的UID",
    "李春维": "UID_填入李春维的UID"
}

# ==========================================
# 2. 智能获取目标查询日期 (解决零点跨日问题)
# ==========================================
tz_beijing = pytz.timezone('Asia/Shanghai')
now_bjt = datetime.now(tz_beijing)

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
    start_time = f"{target_date} 00:00:00+08:00"
    end_time = f"{target_date} 23:59:59+08:00"
    
    response = supabase.table('work_logs').select('name').gte('submit_time', start_time).lte('submit_time', end_time).execute()
    submitted_data = response.data
    
    print(f"🔍 已获取 {target_date} 的 {len(submitted_data)} 条记录。")
except Exception as e:
    print(f"🚨 数据库查询失败: {e}")
    exit(1)

submitted_names = list(set([record.get('name') for record in submitted_data if record.get('name')]))
missing_users = [name for name in EMPLOYEES_UIDS.keys() if name not in submitted_names]
missing_users = list(set(missing_users)) 
print(f"🧐 未交名单 ({len(missing_users)}人): {missing_users}")

# ==========================================
# 4. 多渠道发送提醒 (企微群 + 微信私信)
# ==========================================
ADMIN_NAMES = ["彭玉桃", "彭宇涛"]

def get_valid_uids(name_list):
    """辅助函数：获取指定名单中有效的 WxPusher UIDs"""
    uids = []
    for name in name_list:
        uid = EMPLOYEES_UIDS.get(name)
        if uid and str(uid).startswith("UID_") and "填入" not in str(uid):
            uids.append(uid)
    return list(set(uids))

if missing_users:
    missing_names_str = "、".join(missing_users)
    greeting = "夜深了，本日的日志统计即将结束啦！" if now_bjt.hour == 0 else f"现在是 {now_bjt.hour} 点，大家记得提交工作日志哦！"
    
    print("\n==========================================")
    print("🚀 准备启动双渠道推送...")
    
    # ----------------------------------------
    # 渠道一：发送到 2 个企业微信群 (公布全名单)
    # ----------------------------------------
    wecom_content = f"## 📢 仪器与细胞房日志未交提醒\n\n**针对日期：** {target_date}\n\n{greeting}\n\n截至目前，还有以下 **{len(missing_users)}** 位同事尚未提交：\n\n<font color=\"warning\">**{missing_names_str}**</font>\n\n请大家抓紧时间提交！☕️"
    wecom_msg = {
        "msgtype": "markdown",
        "markdown": {"content": wecom_content}
    }
    
    for idx, webhook in enumerate(WEBHOOK_URLS, 1):
        try:
            res = requests.post(webhook, json=wecom_msg)
            if res.status_code == 200:
                print(f"✅ [企微群 {idx}] 提醒发送成功!")
            else:
                print(f"⚠️ [企微群 {idx}] 提醒发送失败，状态码: {res.status_code}")
        except Exception as e:
            print(f"🚨 [企微群 {idx}] 请求发生异常: {e}")

    # ----------------------------------------
    # 渠道二：通过 WxPusher 发送个人微信 (分流处理)
    # ----------------------------------------
    if not WXPUSHER_APP_TOKEN:
        print("⚠️ 未配置 WXPUSHER_APP_TOKEN，已跳过个人微信推送。")
    else:
        # A. 给其他未交同事发送个人专属提醒 (排除管理员)
        regular_missing_names = [name for name in missing_users if name not in ADMIN_NAMES]
        regular_uids = get_valid_uids(regular_missing_names)
        
        if regular_uids:
            personal_content = f"## 📢 仪器与细胞房日志未交提醒\n\n**针对日期：** {target_date}\n\n{greeting}\n\n⚠️ **系统检测到您尚未提交本日的工作日志。**\n\n为了保障实验室日常记录的完整，请抓紧时间前往系统填写哦！☕️"
            
            try:
                res = requests.post("https://wxpusher.zjiecode.com/api/send/message", json={
                    "appToken": WXPUSHER_APP_TOKEN,
                    "content": personal_content,
                    "summary": f"⏰ {time_label}工作日志未交提醒",
                    "contentType": 3,
                    "uids": regular_uids
                })
                print(f"✅ [私人微信-普通同事] 成功推送 {len(regular_uids)} 人。")
            except Exception as e:
                print(f"🚨 [私人微信-普通同事] 推送异常: {e}")
                
        # B. 给管理员 (彭宇涛) 发送总体汇总名单
        admin_uids = get_valid_uids(ADMIN_NAMES)
        if admin_uids:
            try:
                res = requests.post("https://wxpusher.zjiecode.com/api/send/message", json={
                    "appToken": WXPUSHER_APP_TOKEN,
                    "content": wecom_content, # 直接使用带有所有人名字的企微文案
                    "summary": f"📊 {time_label}日志未交汇总 ({len(missing_users)}人)",
                    "contentType": 3,
                    "uids": admin_uids
                })
                print(f"✅ [私人微信-管理员] 成功向管理员推送总体汇总情况。")
            except Exception as e:
                print(f"🚨 [私人微信-管理员] 推送异常: {e}")
                
    print("==========================================\n")
else:
    print(f"🎉 太棒了！{target_date} 所有人都已经提交了工作日志，无需发送提醒。")
    
    # 彩蛋：如果所有人都交了，也给管理员发送一条确认消息
    if WXPUSHER_APP_TOKEN:
        admin_uids = get_valid_uids(["彭宇涛"])
        if admin_uids:
            success_content = f"## 🎉 仪器与细胞房日志提交完毕\n\n**针对日期：** {target_date}\n\n太棒了！所有同事均已完成本日的工作日志提交，各项管理记录完备。无需进行未交提醒。"
            try:
                requests.post("https://wxpusher.zjiecode.com/api/send/message", json={
                    "appToken": WXPUSHER_APP_TOKEN,
                    "content": success_content,
                    "summary": f"🎉 {time_label}全员已交日志",
                    "contentType": 3,
                    "uids": admin_uids
                })
                print(f"✅ [私人微信-管理员] 已向管理员发送全员提交完毕通知。")
            except Exception as e:
                print(f"🚨 [私人微信-管理员] 成功通知推送异常: {e}")
