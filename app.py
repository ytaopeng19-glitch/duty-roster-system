import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date, timedelta

# --- 1. 页面基本配置 ---
st.set_page_config(page_title="中佳研发周末值班登记系统", page_icon="🏢", layout="centered")

# --- 2. 数据库连接与全局数据获取 ---
@st.cache_resource
def init_connection():
    # 终极修复：使用 rstrip("/") 自动清除配置中不小心带入的结尾斜杠
    url = st.secrets["supabase"]["url"].rstrip("/")
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

# 全局获取最新数据，供前台看版和后台管理共同使用
# 注意：这里按你的数据库字段改成了 target_date 进行排序
try:
    response = supabase.table("registrations").select("*").order("target_date", desc=True).execute()
    records = response.data
except Exception as e:
    records = []
    st.error(f"⚠️ 无法连接到数据库，请稍后再试或检查配置：{e}")

# 注意：这里按你的数据库字段改成了 target_date 和 submit_time
df_records = pd.DataFrame(records) if records else pd.DataFrame(columns=["id", "name", "target_date", "submit_time"])

# 统计每个日期的报名人数 (使用 target_date)
counts_dict = df_records['target_date'].value_counts().to_dict() if not df_records.empty else {}

# --- 3. 生成允许选择的周末日期 (2026-08-02 到 2026年底) ---
start_date = date(2026, 8, 2)
end_date = date(2026, 12, 31)
valid_weekend_dates = []
current = start_date
while current <= end_date:
    if current.weekday() >= 5: # 5代表周六，6代表周日
        valid_weekend_dates.append(current)
    current += timedelta(days=1)

# 构建供下拉菜单使用的字典格式：{"2026-08-02 (周日)": "2026-08-02"}
date_options = {
    f"{str(d)} ({'周六' if d.weekday()==5 else '周日'})": str(d) 
    for d in valid_weekend_dates
}

# --- 4. 首页公告栏 ---
st.title("🏢 中佳研发周末值班登记")
st.info("""
### 📢 研发值班制度升级通知
为进一步优化团队工作模式，提升工作灵活性，**原周末轮值制度现已全面升级为“自愿报名制度”**。
* 🌟 **绩效激励**：周末值班不仅是推动项目进度的关键，更是团队责任心的体现。**值班记录将作为年末综合绩效评价、评优评先的核心参考指标**。
* 🕰️ **值班时间**：早上 `9:00 - 12:00`，下午 `2:00 - 4:00`。
* 👥 **名额说明**：每天值班人数不限，鼓励大家积极参与。仅限预约 2026 年剩余的周末哦！
""", icon="💡")

# --- 5. 核心功能区 (双标签页设计) ---
tab1, tab2 = st.tabs(["📝 我要登记", "🛡️ 管理员后台"])

# ---------------- 标签页 1：用户前台登记 ----------------
with tab1:
    st.subheader("📊 周末值班报名动态看板")
    
    # 动态生成前台脱敏看板数据
    dashboard_data = []
    for d_str, d_val in date_options.items():
        count = counts_dict.get(d_val, 0)
        status_text = "无人值班" if count == 0 else f"{count} 人已报名"
        dashboard_data.append({"值班日期": d_str, "报名状态": status_text, "人数": count})
    
    df_dashboard = pd.DataFrame(dashboard_data)
    
    # 使用 dataframe 并进行简单的颜色高亮（有人报名的行变色）
    st.dataframe(
        df_dashboard.style.map(
            lambda x: 'background-color: #e6f9ec; color: #000000;' if isinstance(x, int) and x > 0 else '', 
            subset=['人数']
        ),
        use_container_width=True, 
        hide_index=True,
        column_order=("值班日期", "报名状态") # 隐藏人数纯数字列，只展示状态实现匿名
    )
    
    st.divider()
    st.subheader("✍️ 新增值班登记")
    
    selected_date_label = st.selectbox("请选择值班日期", options=list(date_options.keys()))
    selected_date_val = date_options[selected_date_label]
    
    # 智能提示判定：若所选日期已有>=2人
    current_selected_count = counts_dict.get(selected_date_val, 0)
    if current_selected_count >= 2:
        st.warning(f"⚠️ **温馨提示：该日期已有 {current_selected_count} 位同事报名值班。**\n\n您是否继续选择今天？还是需要考虑选择其他暂无人值守的周末？", icon="👀")
    elif current_selected_count > 0:
        st.success(f"✅ 该日期已有 {current_selected_count} 人报名，欢迎加入团队作战！", icon="🤝")
        
    with st.form("registration_form"):
        user_name = st.text_input("您的姓名", placeholder="请输入您的真实姓名")
        st.text(f"当前选择的日期确认: {selected_date_label}") 
        
        submit_button = st.form_submit_button("🚀 确认提交登记")
        
        if submit_button:
            if user_name.strip() == "":
                st.warning("⚠️ 姓名不能为空，请重新输入！")
            else:
                try:
                    # 注意：插入数据时，字段名改为 target_date
                    data = {"name": user_name, "target_date": selected_date_val}
                    supabase.table("registrations").insert(data).execute()
                    st.success(f"✅ {user_name}，您在 {selected_date_val} 的值班登记已成功提交！辛苦了！")
                    st.rerun() 
                except Exception as e:
                    st.error(f"❌ 提交失败，请联系管理员。报错信息：{e}")

# ---------------- 标签页 2：管理员后台 (增删查与导出) ----------------
with tab2:
    st.subheader("后台数据管理")
    admin_password = st.text_input("请输入管理员密码", type="password")
    
    if admin_password == st.secrets["admin"]["password"]:
        st.success("✅ 身份验证通过")
        st.divider()
        
        if not df_records.empty:
            # 注意：重命名展示列时，匹配你的 target_date 和 submit_time
            display_df = df_records.rename(columns={
                "id": "记录ID", 
                "name": "值班人", 
                "target_date": "值班日期", 
                "submit_time": "系统提交时间"
            })
            
            st.write("📊 **当前所有登记记录（含具体人员名单）：**")
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # --- 导出为 Excel(CSV) ---
            csv_data = display_df.to_csv(index=False).encode('utf-8-sig') 
            st.download_button(
                label="📥 导出所有值班记录为 Excel(CSV)",
                data=csv_data,
                file_name=f"周末值班记录导出_{date.today()}.csv",
                mime="text/csv",
            )
            st.divider()
            
            col1, col2 = st.columns(2)
            # --- 功能 A：后台代登记 ---
            with col1:
                st.write("➕ **后台代登记**")
                with st.form("admin_add_form"):
                    add_name = st.text_input("姓名")
                    add_date_label = st.selectbox("值班日期", options=list(date_options.keys()))
                    
                    if st.form_submit_button("确认添加"):
                        if add_name.strip():
                            add_date_val = date_options[add_date_label]
                            # 注意：后台添加时字段名也改为了 target_date
                            supabase.table("registrations").insert({"name": add_name, "target_date": add_date_val}).execute()
                            st.success("✅ 后台代登记成功！")
                            st.rerun()
                        else:
                            st.warning("⚠️ 请输入姓名")
                            
            # --- 功能 B：删除错误记录 ---
            with col2:
                st.write("🗑️ **删除无效记录**")
                with st.form("admin_delete_form"):
                    # 注意：删除下拉框里的显示字段改为 target_date
                    delete_options = {f"ID:{row['id']} | {row['name']} ({row['target_date']})": row['id'] for index, row in df_records.iterrows()}
                    selected_str = st.selectbox("请选择要删除的记录", options=list(delete_options.keys()))
                    
                    if st.form_submit_button("危 确认删除"):
                        delete_id = delete_options[selected_str]
                        supabase.table("registrations").delete().eq("id", delete_id).execute()
                        st.success(f"✅ 记录已成功删除！")
                        st.rerun()
        else:
            st.info("📂 当前数据库中没有任何值班记录。")
            
    elif admin_password != "":
        st.error("❌ 密码错误，您没有访问权限。")
