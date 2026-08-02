import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date, timedelta
import uuid

# --- 1. 页面基本配置 ---
st.set_page_config(page_title="中佳研发办公与值班管理系统", page_icon="🏢", layout="centered")

# --- 2. 数据库连接与全局数据获取 ---
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"].rstrip("/")
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

# 全局获取值班数据
try:
    response = supabase.table("registrations").select("*").order("target_date", desc=True).execute()
    records = response.data
except Exception as e:
    records = []
    st.error(f"⚠️ 无法连接到值班数据库：{e}")

df_records = pd.DataFrame(records) if records else pd.DataFrame(columns=["id", "name", "target_date", "submit_time"])
counts_dict = df_records['target_date'].value_counts().to_dict() if not df_records.empty else {}

# --- 3. 生成允许选择的周末日期 (2026-08-02 到 2026年底) ---
start_date = date(2026, 8, 2)
end_date = date(2026, 12, 31)
valid_weekend_dates = []
current = start_date
while current <= end_date:
    if current.weekday() >= 5: 
        valid_weekend_dates.append(current)
    current += timedelta(days=1)

date_options = {
    f"{str(d)} ({'周六' if d.weekday()==5 else '周日'})": str(d) 
    for d in valid_weekend_dates
}

# --- 4. 首页公告栏 ---
st.title("🏢 中佳研发协同管理系统")
st.info("""
### 📢 平台功能说明
* 🏢 **周末值班登记**：实行自愿报名制，支持 2026 年剩余周末预约，前台看板展示实时报名人数。
* 📁 **个人工作日志**：支持日常 Word 工作日志上传（限制 5MB 以内）。每位同事仅能查阅、下载及累加上传自己的历史日志，确保数据安全与隐私。
""", icon="💡")

# --- 5. 核心功能区 (三标签页设计) ---
tab1, tab2, tab3 = st.tabs(["📝 周末值班登记", "📁 个人工作日志", "🛡️ 管理员后台"])

# ---------------- 标签页 1：用户前台登记 ----------------
with tab1:
    st.subheader("📊 周末值班报名动态看板")
    
    dashboard_data = []
    for d_str, d_val in date_options.items():
        count = counts_dict.get(d_val, 0)
        status_text = "无人值班" if count == 0 else f"{count} 人已报名"
        dashboard_data.append({"值班日期": d_str, "报名状态": status_text, "人数": count})
    
    df_dashboard = pd.DataFrame(dashboard_data)
    st.dataframe(
        df_dashboard.style.map(
            lambda x: 'background-color: #e6f9ec; color: #000000;' if isinstance(x, int) and x > 0 else '', 
            subset=['人数']
        ),
        use_container_width=True, 
        hide_index=True,
        column_order=("值班日期", "报名状态")
    )
    
    st.divider()
    st.subheader("✍️ 新增值班登记")
    
    selected_date_label = st.selectbox("请选择值班日期", options=list(date_options.keys()), key="duty_select")
    selected_date_val = date_options[selected_date_label]
    
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
                    data = {"name": user_name.strip(), "target_date": selected_date_val}
                    supabase.table("registrations").insert(data).execute()
                    st.success(f"✅ {user_name}，您在 {selected_date_val} 的值班登记已成功提交！辛苦了！")
                    st.rerun() 
                except Exception as e:
                    st.error(f"❌ 提交失败，请联系管理员。报错信息：{e}")

# ---------------- 标签页 2：个人工作日志管理 ----------------
with tab2:
    st.subheader("📁 个人工作日志中心")
    st.markdown("请先输入您的姓名，系统将自动过滤并仅展示您个人历史上传的 Word 日志文件。")
    
    my_name = st.text_input("请输入您的姓名（用于查看和上传日志）", placeholder="例如：张三", key="log_name_input")
    
    if my_name.strip():
        st.divider()
        st.write(f"👋 你好，**{my_name.strip()}**。以下是您的日志管理区：")
        
        # 文件上传区域
        uploaded_doc = st.file_uploader(
            "上传新的工作日志 (仅支持 .docx 格式，大小限制 5MB 以内)", 
            type=["docx"], 
            key="work_log_uploader"
        )
        
        if uploaded_doc is not None:
            # 校验大小：5MB = 5 * 1024 * 1024 字节
            if uploaded_doc.size > 5 * 1024 * 1024:
                st.error("❌ 文件大小超过 5MB 限制，请压缩或精简内容后重新上传！")
            else:
                if st.button("🚀 确认上传该日志文件"):
                    try:
                        # 构造安全且唯一的云端存储路径 (使用 UUID 替代中文路径以防止 InvalidKey 报错)
                        file_extension = uploaded_doc.name.split('.')[-1]
                        safe_storage_name = f"{uuid.uuid4().hex}_{date.today()}.{file_extension}"
                        storage_path = f"logs/{safe_storage_name}"
                        
                        # 上传文件到 Supabase Storage 的 work_logs 桶
                        file_bytes = uploaded_doc.getvalue()
                        supabase.storage.from_("work_logs").upload(
                            path=storage_path,
                            file=file_bytes
                        )
                        
                        # 获取公开下载链接 (仅当 Bucket 设为 Public 时有效)
                        public_url_res = supabase.storage.from_("work_logs").get_public_url(storage_path)
                        
                        # 将元数据写入 work_logs 数据库表
                        log_data = {
                            "name": my_name.strip(),
                            "file_name": uploaded_doc.name,
                            "file_path": storage_path
                        }
                        supabase.table("work_logs").insert(log_data).execute()
                        
                        st.success(f"✅ 日志文件 【{uploaded_doc.name}】 上传成功！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 上传失败，错误信息：{e}")
                        
        st.divider()
        st.subheader("📜 您的历史日志列表（仅自己可见）")
        
        # 仅查询当前输入姓名的日志记录
        try:
            my_logs_res = supabase.table("work_logs").select("*").eq("name", my_name.strip()).order("submit_time", desc=True).execute()
            my_logs = my_logs_res.data
            
            if my_logs:
                for log in my_logs:
                    col_info, col_dl = st.columns([3, 1])
                    with col_info:
                        st.text(f"📄 文件名: {log['file_name']}\n⏱️ 上传时间: {log['submit_time'].replace('T', ' ').split('.')[0]}")
                    with col_dl:
                        # 生成下载链接
                        try:
                            dl_url = supabase.storage.from_("work_logs").get_public_url(log['file_path'])
                            st.markdown(f"[📥 点击下载]({dl_url})", unsafe_allow_html=True)
                        except:
                            st.write("链接生成失败")
                    st.markdown("---")
            else:
                st.info("📂 您当前还没有上传过任何工作日志。")
        except Exception as e:
            st.warning("⚠️ 暂无日志数据或表结构尚未创建。")
    else:
        st.warning("⚠️ 请先在上方输入您的真实姓名，方可进行日志上传与查看。")

# ---------------- 标签页 3：管理员后台 ----------------
with tab3:
    st.subheader("🛡️ 系统管理后台")
    admin_password = st.text_input("请输入管理员密码", type="password", key="admin_pwd_input")
    
    if admin_password == st.secrets["admin"]["password"]:
        st.success("✅ 身份验证通过")
        st.divider()
        
        admin_sub_tab1, admin_sub_tab2 = st.tabs(["📊 值班数据管理", "📁 全体员工日志管理"])
        
        # 子后台 1：值班管理
        with admin_sub_tab1:
            if not df_records.empty:
                display_df = df_records.rename(columns={
                    "id": "记录ID", 
                    "name": "值班人", 
                    "target_date": "值班日期", 
                    "submit_time": "系统提交时间"
                })
                st.write("📊 **当前所有周末值班登记记录：**")
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                csv_data = display_df.to_csv(index=False).encode('utf-8-sig') 
                st.download_button(
                    label="📥 导出所有值班记录为 Excel(CSV)",
                    data=csv_data,
                    file_name=f"周末值班记录导出_{date.today()}.csv",
                    mime="text/csv",
                    key="dl_duty_csv"
                )
                st.divider()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("➕ **后台代登记值班**")
                    with st.form("admin_add_form"):
                        add_name = st.text_input("姓名")
                        add_date_label = st.selectbox("值班日期", options=list(date_options.keys()), key="admin_add_date")
                        if st.form_submit_button("确认添加"):
                            if add_name.strip():
                                add_date_val = date_options[add_date_label]
                                supabase.table("registrations").insert({"name": add_name.strip(), "target_date": add_date_val}).execute()
                                st.success("✅ 后台代登记成功！")
                                st.rerun()
                            else:
                                st.warning("⚠️ 请输入姓名")
                                
                with col2:
                    st.write("🗑️ **删除无效值班记录**")
                    with st.form("admin_delete_form"):
                        delete_options = {f"ID:{row['id']} | {row['name']} ({row['target_date']})": row['id'] for index, row in df_records.iterrows()}
                        selected_str = st.selectbox("请选择要删除的记录", options=list(delete_options.keys()))
                        if st.form_submit_button("危 确认删除"):
                            delete_id = delete_options[selected_str]
                            supabase.table("registrations").delete().eq("id", delete_id).execute()
                            st.success(f"✅ 记录已成功删除！")
                            st.rerun()
            else:
                st.info("📂 当前数据库中没有任何值班记录。")
                
        # 子后台 2：全体日志管理
        with admin_sub_tab2:
            st.write("📊 **所有员工提交的工作日志一览：**")
            try:
                all_logs_res = supabase.table("work_logs").select("*").order("submit_time", desc=True).execute()
                all_logs = all_logs_res.data
                if all_logs:
                    df_all_logs = pd.DataFrame(all_logs)
                    display_logs_df = df_all_logs.rename(columns={
                        "id": "日志ID",
                        "name": "员工姓名",
                        "file_name": "文件名",
                        "file_path": "云端存储路径",
                        "submit_time": "提交时间"
                    })
                    st.dataframe(display_logs_df, use_container_width=True, hide_index=True)
                    
                    # 导出日志清单
                    csv_logs_data = display_logs_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 导出全体日志清单为 Excel(CSV)",
                        data=csv_logs_data,
                        file_name=f"全体工作日志清单_{date.today()}.csv",
                        mime="text/csv",
                        key="dl_logs_csv"
                    )
                else:
                    st.info("📂 暂无任何员工上传工作日志。")
            except Exception as e:
                st.warning(f"⚠️ 无法读取工作日志表，请确认是否已创建 `work_logs` 数据表：{e}")
                
    elif admin_password != "":
        st.error("❌ 密码错误，您没有访问权限。")
