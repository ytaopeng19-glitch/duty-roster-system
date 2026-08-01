import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from supabase import create_client, Client

# --- 页面设置 (必须放在最前面) ---
st.set_page_config(page_title="中佳研发部周末值班报名系统", page_icon="📝", layout="centered")

# --- 初始化 Supabase 客户端 ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error(f"数据库连接失败！具体错误原因：{e}")
    st.stop()

# --- 日期计算函数：获取 2026 年剩余的所有周末 ---
def get_remaining_weekends_2026():
    today = datetime.now().date()
    # 设定截止日期为2026年底
    end_of_year = date(2026, 12, 31)
    
    # 确保起始日期是今天（如果当前已经超过2026年，这里会自动处理为空）
    current = today if today.year == 2026 else date(2026, 1, 1)
    
    weekends = []
    while current <= end_of_year:
        # weekday() 返回 5 是周六，6 是周日
        if current.weekday() in [5, 6]:
            weekends.append(current)
        current += timedelta(days=1)
    return weekends

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
    st.info(f"📣 提示：当前已有 **{current_count}** 人成功报名值班。")
else:
    st.info("📣 提示：当前暂无人员报名，快来抢占第一个名额吧！")

st.write("---")

# 获取 2026 剩余周末数据
remaining_weekends = get_remaining_weekends_2026()
weekday_cn = {5: "周六", 6: "周日"}
# 格式化日期列表，例如 "2026-08-02 (周日)"
weekend_options = [f"{d.strftime('%Y-%m-%d')} ({weekday_cn[d.weekday()]})" for d in remaining_weekends]

# 增加一个折叠面板，展示 2026 年剩余的所有周末
with st.expander("📅 点击查看 2026 年剩余的所有周末一览表", expanded=False):
    if not weekend_options:
        st.write("2026年已无剩余周末。")
    else:
        # 将日期分成 3 列展示，更加美观紧凑
        cols = st.columns(3)
        for i, opt in enumerate(weekend_options):
            cols[i % 3].write(f"• {opt}")

# 报名表单
st.subheader("提交报名")
with st.form("registration_form", clear_on_submit=True):
    user_name = st.text_input("请输入您的姓名（必填）", max_chars=20)
    
    # 核心改动：用下拉菜单代替日历输入框，彻底锁定只能选周末
    if weekend_options:
        target_date_str = st.selectbox("请选择意向值班日期（仅限 2026 年周末）", weekend_options)
    else:
        st.warning("⚠️ 2026 年已无有效周末可选。")
        target_date_str = None
    
    submitted = st.form_submit_button("🚀 确认报名")
    
    if submitted:
        if not user_name.strip():
            st.error("姓名不能为空，请重新输入！")
        elif not target_date_str:
            st.error("当前无有效日期可报名！")
        else:
            # 通过 split 提取纯日期部分存入数据库，例如提取 "2026-08-02"
            pure_date = target_date_str.split(" ")[0]
            add_registration(user_name, pure_date)
            st.success(f"🎉 感谢报名，{user_name}！您的值班申请（{pure_date}）已提交成功。")
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
