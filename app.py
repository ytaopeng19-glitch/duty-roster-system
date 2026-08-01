import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# 1. 数据库初始化函数
def init_db():
    conn = sqlite3.connect('duty_roster.db')
    c = conn.cursor()
    # 创建报名表，包含：id、姓名、意向日期、提交时间
    c.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target_date TEXT NOT NULL,
            submit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# 2. 数据库操作函数
def add_registration(name, target_date):
    conn = sqlite3.connect('duty_roster.db')
    c = conn.cursor()
    c.execute("INSERT INTO registrations (name, target_date) VALUES (?, ?)", 
              (name, str(target_date)))
    conn.commit()
    conn.close()

def get_registration_count():
    conn = sqlite3.connect('duty_roster.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM registrations")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_all_registrations():
    conn = sqlite3.connect('duty_roster.db')
    df = pd.read_sql_query("SELECT id as 序号, name as 姓名, target_date as 意向日期, submit_time as 提交时间 FROM registrations", conn)
    conn.close()
    return df

# 初始化数据库
init_db()

# --- 页面设置 ---
st.set_page_config(page_title="中佳研发部周末值班报名系统", page_icon="📝", layout="centered")

# --- 主界面（前端：所有人可见） ---
st.title("📝 中佳研发部周末值班报名系统")

# 获取并显示当前报名人数
current_count = get_registration_count()
if current_count > 0:
    st.info(f"📣 提示：当前已有 **{current_count}** 人成功报名本周末值班。")
else:
    st.info("📣 提示：当前暂无人员报名，快来抢占第一个名额吧！")

st.write("---")

# 报名表单
st.subheader("提交报名")
with st.form("registration_form", clear_on_submit=True):
    user_name = st.text_input("请输入您的姓名（必填）", max_chars=20)
    target_date = st.date_input("请选择意向值班日期")
    
    submitted = st.form_submit_button("🚀 确认报名")
    
    if submitted:
        if not user_name.strip():
            st.error("姓名不能为空，请重新输入！")
        else:
            add_registration(user_name, target_date)
            st.success(f"🎉 感谢报名，{user_name}！您的值班申请已提交成功。")
            # 刷新页面以更新报名人数
            st.rerun()


# --- 侧边栏（后台：仅管理员可见） ---
st.sidebar.title("🔒 后台管理")
st.sidebar.write("仅限管理员查看具体报名名单")

# 设置管理员密码（你可以自行修改这里的 "zj123456"）
ADMIN_PASSWORD = "zj123456" 

admin_pwd = st.sidebar.text_input("请输入管理员密码", type="password")

if admin_pwd:
    if admin_pwd == ADMIN_PASSWORD:
        st.sidebar.success("✅ 登录成功")
        
        st.markdown("---")
        st.subheader("📊 后台数据：已报名名单")
        
        # 获取所有数据并展示
        df = get_all_registrations()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            
            # 提供下载为 Excel/CSV 的功能
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 导出名单为 CSV",
                data=csv,
                file_name=f"周末值班报名名单_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.write("目前还没有人报名。")
    else:
        st.sidebar.error("❌ 密码错误，请重试")