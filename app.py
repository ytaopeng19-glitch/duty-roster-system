import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date, timedelta

# --- 1. 页面基本配置 ---
st.set_page_config(page_title="中佳研发周末值班登记系统", page_icon="🏢", layout="centered")

# --- 2. 数据库连接 ---
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- 3. 获取全局数据 (用于前台看板和后台管理) ---
@st.cache_data(ttl=5) # 缓存5秒，避免频繁刷新导致数据库压力过大
def fetch_all_data():
    response = supabase.table("registrations").select("*").order("duty_date", desc=True).execute()
    return response.data

records = fetch_all_data()
# 将数据转为 DataFrame，方便后续统计和展示
df_records = pd.DataFrame(records) if records else pd.DataFrame(columns=["id", "name", "duty_date", "created_at"])

# --- 4. 日期逻辑：仅限2026年剩余的周末 (从8月2日起) ---
start_date = max(date.today(), date(2026, 8, 2))
end_date = date(2026, 12, 31)

future_weekends = []
current_date = start_date
while current_date <= end_date:
    if current_date.isoweekday() in [6, 7]: # 6是周六，7是周日
        future_weekends.append(current_date)
    current_date += timedelta(days=1)

# 统计每个日期的报名人数
date_counts = {}
if not df_records.empty:
    counts = df_records['duty_date'].value_counts().to_dict()
    for d_str, count in counts.items():
        date_counts[d_str] = count

# --- 5. 首页公告栏 ---
st.title("🏢 中嘉研发周末值班登记")

st.info("""
### 📢 研发值班制度升级通知
为进一步优化团队工作模式，提升工作灵活性，**原周末轮值制度现已全面升级为“自愿报名制度”**。

* 🌟 **绩效激励**：**值班记录将作为年末综合绩效评价、评优评先心参考指标**。
* 🕰️ **值班时间**：早上 `9:00 - 12:00`，下午 `2:00 - 4:00`。
* 👥 **名额说明**：每天值班**人数不限**，鼓励大家根据项目实际需求积极参与。
* 📝 **灵活登记**：支持临时决定来加班的同事进行**补充登记**。
""", icon="💡")

# --- 6. 核心功能区 (双标签页设计) ---
tab1, tab2 = st.tabs(["📝 我要登记", "🛡️ 管理员后台"])

# ---------------- 标签页 1：用户前台登记 ----------------
with tab1:
    st.subheader("📊 2026周末值班报名看板")
    st.caption("在此查看各周末报名热度 (保护隐私，仅显示人数)")
    
    # 构建前台看板数据
    dashboard_data = []
    for w in future_weekends:
        w_str = str(w)
        count = date_counts.get(w_str, 0)
        weekday_str = "周六" if w.isoweekday() == 6 else "周日"
        
        if count == 0:
            status = "🟢 虚位以待"
        elif count == 1:
            status = "🟡 已有 1 人"
        else:
            status = f"🔥 已有 {count} 人"
            
        dashboard_data.append({
            "📅 日期": f"{w_str} ({weekday_str})",
            "👥 已报名人数": count,
            "💡 当前状态": status
        })
    
    # 展示前台看板
    if dashboard_data:
        st.dataframe(pd.DataFrame(dashboard_data), use_container_width=True, hide_index=True)
    else:
        st.warning("2026年已无剩余周末。")

    st.divider()
    
    st.subheader("新增值班登记")
    
    # 日期选择放在表单外部，以实现实时预警
    weekend_options = [f"{str(w)} ({'周六' if w.isoweekday() == 6 else '周日'})" for w in future_weekends]
    
    if weekend_options:
        selected_date_str = st.selectbox("📅 选择值班日期 (仅限2026年剩余周末)", options=weekend_options)
        selected_actual_date = selected_date_str.split(" ")[0] # 提取出纯日期字符串，如 '2026-08-02'
        
        # --- 动态容量预警 ---
        current_count = date_counts.get(selected_actual_date, 0)
        if current_count >= 2:
            st.warning(f"⚠️ **{selected_actual_date} 已有两位（或以上）同事值班！** \n\n您是否继续选择今天，还是考虑选择其他日期？")
        elif current_count == 1:
            st.info(f"ℹ️ {selected_actual_date} 已有 1 位同事报名，继续报名即可。")
        else:
            st.success(f"✅ {selected_actual_date} 目前尚无人报名，期待您的加入！")
            
        # --- 提交表单 ---
        with st.form("registration_form"):
            user_name = st.text_input("您的姓名", placeholder="请输入您的真实姓名")
            submit_button = st.form_submit_button("🚀 提交登记")
            
            if submit_button:
                if user_name.strip() == "":
                    st.warning("⚠️ 姓名不能为空，请重新输入！")
                else:
                    try:
                        # 插入数据
                        data = {"name": user_name, "duty_date": selected_actual_date}
                        supabase.table("registrations").insert(data).execute()
                        st.success(f"✅ {user_name}，您在 {selected_actual_date} 的值班登记已成功提交！辛苦了！")
                        # 清除缓存并刷新页面以更新看板
                        fetch_all_data.clear()
                        st.rerun() 
                    except Exception as e:
                        st.error(f"❌ 提交失败，请联系管理员。报错信息：{e}")
    else:
        st.error("当前不在可选的排班日期范围内。")


# ---------------- 标签页 2：管理员后台 (增删查 + 导出) ----------------
with tab2:
    st.subheader("后台数据管理")
    admin_password = st.text_input("请输入管理员密码", type="password")
    
    if admin_password == st.secrets["admin"]["password"]:
        st.success("✅ 身份验证通过")
        st.divider()
        
        if not df_records.empty:
            # 美化列名展示
            display_df = df_records.rename(columns={
                "id": "记录ID", 
                "name": "值班人", 
                "duty_date": "值班日期", 
                "created_at": "系统提交时间"
            })
            
            col_title, col_download = st.columns([2, 1])
            with col_title:
                st.write("📊 **当前所有实名登记记录：**")
            with col_download:
                # --- 新增功能：导出为 CSV (支持 Excel 打开) ---
                csv = display_df.to_csv(index=False).encode('utf-8-sig') # 使用 utf-8-sig 防止 Excel 乱码
                st.download_button(
                    label="📥 导出值班表格",
                    data=csv,
                    file_name=f"周末值班明细_{date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            st.divider()
            col1, col2 = st.columns(2)
            
            # --- 功能 A：管理员直接增加记录 ---
            with col1:
                st.write("➕ **后台代登记**")
                with st.form("admin_add_form"):
                    add_name = st.text_input("姓名")
                    # 后台不受日期限制，方便补录历史
                    add_date = st.date_input("值班日期", value=date.today())
                    if st.form_submit_button("确认添加"):
                        if add_name.strip():
                            supabase.table("registrations").insert({"name": add_name, "duty_date": str(add_date)}).execute()
                            st.success("✅ 后台代登记成功！")
                            fetch_all_data.clear()
                            st.rerun() 
                        else:
                            st.warning("⚠️ 请输入姓名")
            
            # --- 功能 B：管理员删除错误记录 ---
            with col2:
                st.write("🗑️ **删除无效记录**")
                with st.form("admin_delete_form"):
                    delete_options = {f"ID:{row['id']} | {row['name']} ({row['duty_date']})": row['id'] for index, row in df_records.iterrows()}
                    selected_str = st.selectbox("请选择要删除的记录", options=list(delete_options.keys()))
                    
                    if st.form_submit_button("确认删除"):
                        delete_id = delete_options[selected_str]
                        supabase.table("registrations").delete().eq("id", delete_id).execute()
                        st.success(f"✅ 记录已成功删除！")
                        fetch_all_data.clear()
                        st.rerun() 
                        
        else:
            st.info("📂 当前数据库中没有任何值班记录。")
            
    elif admin_password != "":
        st.error("❌ 密码错误，您没有访问权限。")
