import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- 页面设置 (必须放在最前面) ---
st.set_page_config(page_title="中佳研发部周末值班报名系统", page_icon="📝", layout="centered")

# --- 初始化 Supabase 客户端 ---
# 这里使用变量名读取，真实的网址和密钥放在 .streamlit/secrets.toml 中
@st.cache_resource
def init_connection():
    url = st.secrets["https://srzfkhiminxmbrbdipay.supabase.co/rest/v1/"]
    key = st.secrets["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNyemZraGltaW54bWJyYmRpcGF5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI2OTgyOTcsImV4cCI6MjA4ODI3NDI5N30.jI9aum5Qe5eniH-oHBiRyIo41EpKUIDedkH-2vHiPnw"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("数据库连接失败，请检查 Streamlit Secrets 配置。")
    st.stop()

# --- 数据库操作函数 ---
def add_registration(name, target_date):
    # 插入数据到 supabase
    data = {"name": name, "target_date": str(target_date)}
    supabase.table("registrations").insert(data).execute()

def get_registration_count():
    # 查询当前总人数
    response = supabase.table("registrations").select("*", count="exact").execute()
    return response.count

def get_all_registrations():
    # 获取所有报名数据
    response = supabase.table("registrations").select("*").execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        # 重命名列以便于展示
        df = df.rename(columns={
            "id": "序号", 
            "name": "姓名", 
            "target_date": "意向日期", 
            "submit_time": "提交时间"
        })
        # 转换时间格式，去掉 Supabase 默认的时区尾巴，看起来更干净
        df['提交时间'] = pd.to_datetime(df['提交时间']).dt.strftime('%Y-%m-%d %H:%M:%S')
    return df

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
            st.rerun()

# --- 侧边栏（后台：仅管理员可见） ---
st.sidebar.title("🔒 后台管理")
st.sidebar.write("仅限管理员查看具体报名名单")

# 从 Secrets 读取后台密码，更安全
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "zj123456")

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
            
            # 提供下载为 CSV 的功能
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
