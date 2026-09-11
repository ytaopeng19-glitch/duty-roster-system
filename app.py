import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date, timedelta, datetime, timezone
import uuid

# --- 1. 页面基本配置 ---
st.set_page_config(page_title="中佳研发办公与值班管理系统", page_icon="🏢", layout="wide")

# --- 2. 员工基础数据与权限配置 ---
EMPLOYEES = {
    "26001": "郑家颖", "26002": "刘伟华", "24001": "谢凌锋",
    "24002": "肖商华", "24003": "刘玥",   "25001": "汪孝亮",
    "25002": "施明鸿", "26003": "李春维", "26004": "卢镇",
    "12002": "刘佳",   "12001": "曲寿康", "24000": "彭宇涛"
}
ADMIN_NAMES = ["刘佳", "曲寿康", "彭宇涛"]

# 设置北京时间时区用于时间解析转换
tz_utc_8 = timezone(timedelta(hours=8))

def get_local_date(time_str):
    """辅助函数：将 Supabase 数据库返回的时间戳字符串转换为本地（东八区）日期"""
    try:
        ts = time_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt.astimezone(tz_utc_8).date()
    except Exception:
        return None

# --- 3. 数据库连接与全局数据获取 ---
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"].rstrip("/")
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- 4. 用户登录与会话管理 ---
if "user" not in st.session_state:
    st.session_state.user = None

# 如果未登录，只显示登录界面并拦截后续渲染
if st.session_state.user is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🏢 中佳研发协同管理系统")
        st.subheader("🔐 员工身份认证")
        
        with st.container(border=True):
            display_options = [""] + [f"{k} - {v}" for k, v in EMPLOYEES.items()]
            selected_option = st.selectbox("请选择您的员工账号", options=display_options)
            
            if selected_option:
                login_emp_id = selected_option.split(" - ")[0]
                emp_name = EMPLOYEES[login_emp_id]
                st.info(f"👤 匹配姓名：**{emp_name}**")
                
                login_pwd = st.text_input("请输入 6 位数字密码", type="password", max_chars=6)
                st.caption("ℹ️ **提示**：首次登录时，您输入的 6 位数字将自动绑定为您账号的永久密码。")
                
                if st.button("🚀 登录 / 激活账号", use_container_width=True):
                    if len(login_pwd) != 6 or not login_pwd.isdigit():
                        st.error("❌ 密码格式错误：必须是 6 位纯数字！")
                    else:
                        try:
                            res = supabase.table("users").select("*").eq("emp_id", login_emp_id).execute()
                            if res.data:
                                if res.data[0]["password"] == login_pwd:
                                    st.session_state.user = {
                                        "emp_id": login_emp_id, 
                                        "name": emp_name, 
                                        "is_admin": emp_name in ADMIN_NAMES
                                    }
                                    st.rerun()
                                else:
                                    st.error("❌ 密码错误，请重新输入！")
                            else:
                                supabase.table("users").insert({
                                    "emp_id": login_emp_id, 
                                    "name": emp_name, 
                                    "password": login_pwd
                                }).execute()
                                st.session_state.user = {
                                    "emp_id": login_emp_id, 
                                    "name": emp_name, 
                                    "is_admin": emp_name in ADMIN_NAMES
                                }
                                st.success(f"✅ 密码设置成功！欢迎您，{emp_name}。")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ 数据库连接异常：{e}")
    st.stop() 

# ================= 下方为登录成功后的主界面 =================

current_user = st.session_state.user
is_admin = current_user["is_admin"]
my_name = current_user["name"]

col_title, col_logout = st.columns([10, 1])
with col_title:
    st.title("🏢 中佳研发协同管理系统")
with col_logout:
    st.write("") 
    if st.button("🚪 退出登录"):
        st.session_state.user = None
        st.rerun()

st.success(f"👋 欢迎回来，**{my_name}**！您的权限级别：{'管理员 🛡️' if is_admin else '普通员工 👤'}")

# 获取排班数据
try:
    response = supabase.table("registrations").select("*").order("target_date", desc=True).execute()
    records = response.data
except Exception as e:
    records = []
    st.error(f"⚠️ 无法连接到值班数据库：{e}")

df_records = pd.DataFrame(records) if records else pd.DataFrame(columns=["id", "name", "target_date", "submit_time"])
counts_dict = df_records['target_date'].value_counts().to_dict() if not df_records.empty else {}

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

if is_admin:
    tab1, tab2, tab3 = st.tabs(["📝 周末值班登记", "📁 个人工作日志", "🛡️ 管理员后台"])
else:
    tab1, tab2 = st.tabs(["📝 周末值班登记", "📁 个人工作日志"])

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
        st.warning(f"⚠️ **温馨提示：该日期已有 {current_selected_count} 位同事报名值班。**", icon="👀")
    elif current_selected_count > 0:
        st.success(f"✅ 该日期已有 {current_selected_count} 人报名，欢迎加入团队作战！", icon="🤝")
        
    if st.button("🚀 确认以我的名义提交登记"):
        is_duplicate = False
        if not df_records.empty:
            match = df_records[(df_records['name'] == my_name) & (df_records['target_date'] == selected_date_val)]
            if not match.empty:
                is_duplicate = True
                
        if is_duplicate:
            st.error(f"❌ 提交失败：您已经报名了 {selected_date_val} 的值班，请勿重复提交！")
        else:
            try:
                data = {"name": my_name, "target_date": selected_date_val}
                supabase.table("registrations").insert(data).execute()
                st.success(f"✅ {my_name}，您在 {selected_date_val} 的值班登记已成功提交！辛苦了！")
                st.rerun() 
            except Exception as e:
                st.error(f"❌ 提交失败，报错信息：{e}")

# ---------------- 标签页 2：个人工作日志管理 ----------------
with tab2:
    st.subheader("📁 个人工作日志中心")
    st.markdown("💡 **规定说明：** 您仅能查看和下载过去 **1 个星期内** 提交的日志。若当天上传的文件有误，您可以使用右侧的“撤回”按钮删除重传。")
    
    uploaded_doc = st.file_uploader(
        "上传新的工作日志 (仅支持 .docx 格式，大小限制 5MB 以内)", 
        type=["docx"], 
        key="work_log_uploader"
    )
    
    if uploaded_doc is not None:
        if uploaded_doc.size > 5 * 1024 * 1024:
            st.error("❌ 文件大小超过 5MB 限制，请压缩或精简内容后重新上传！")
        else:
            if st.button("🚀 确认上传该日志文件"):
                try:
                    file_extension = uploaded_doc.name.split('.')[-1]
                    safe_storage_name = f"{uuid.uuid4().hex}_{date.today()}.{file_extension}"
                    storage_path = f"logs/{safe_storage_name}"
                    
                    file_bytes = uploaded_doc.getvalue()
                    supabase.storage.from_("work_logs").upload(
                        path=storage_path,
                        file=file_bytes
                    )
                    
                    log_data = {
                        "name": my_name,
                        "file_name": uploaded_doc.name,
                        "file_path": storage_path
                    }
                    supabase.table("work_logs").insert(log_data).execute()
                    
                    st.success(f"✅ 日志文件 【{uploaded_doc.name}】 上传成功！")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 上传失败，错误信息：{e}")
                    
    st.divider()
    st.subheader("📜 您近期的日志列表")
    
    try:
        seven_days_ago = str(date.today() - timedelta(days=7))
        my_logs_res = supabase.table("work_logs").select("*").eq("name", my_name).gte("submit_time", seven_days_ago).order("submit_time", desc=True).execute()
        my_logs = my_logs_res.data
        
        if my_logs:
            for log in my_logs:
                col_info, col_dl, col_del = st.columns([3, 1, 1])
                with col_info:
                    st.text(f"📄 文件名: {log['file_name']}\n⏱️ 上传时间: {log['submit_time'].replace('T', ' ').split('.')[0]}")
                with col_dl:
                    try:
                        dl_url = supabase.storage.from_("work_logs").get_public_url(log['file_path'])
                        st.markdown(f"[📥 点击下载]({dl_url})", unsafe_allow_html=True)
                    except:
                        st.write("链接生成失败")
                with col_del:
                    if get_local_date(log['submit_time']) == date.today():
                        if st.button("🗑️ 撤回", key=f"del_user_{log['id']}"):
                            try:
                                supabase.storage.from_("work_logs").remove([log['file_path']])
                                supabase.table("work_logs").delete().eq("id", log["id"]).execute()
                                st.success("✅ 日志已成功撤回。")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ 删除失败：{e}")
                st.markdown("---")
        else:
            st.info("📂 您在过去 1 个星期内没有上传过任何工作日志。")
    except Exception as e:
        st.warning("⚠️ 暂无日志数据或表结构尚未创建。")

# ---------------- 标签页 3：管理员后台 (仅管理员可见) ----------------
if is_admin:
    with tab3:
        st.subheader("🛡️ 系统管理后台")
        st.caption("作为管理员，您拥有查看全局数据和强制干预删除的权限。")
        
        admin_sub_tab1, admin_sub_tab2, admin_sub_tab3 = st.tabs(["📊 全体人员排班", "📁 全体员工日志调阅", "📅 每日日志考勤矩阵"])
        
        # --- 子标签页 1：全体排班 ---
        with admin_sub_tab1:
            if not df_records.empty:
                display_df = df_records.rename(columns={
                    "id": "记录ID", 
                    "name": "值班人", 
                    "target_date": "值班日期", 
                    "submit_time": "系统提交时间"
                })
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                csv_data = display_df.to_csv(index=False).encode('utf-8-sig') 
                st.download_button(
                    label="📥 导出所有值班记录 (CSV)",
                    data=csv_data,
                    file_name=f"周末值班记录导出_{date.today()}.csv",
                    mime="text/csv",
                    key="dl_duty_csv"
                )
                
                st.divider()
                st.write("🗑️ **删除无效记录**")
                with st.form("admin_delete_form"):
                    delete_options = {f"ID:{row['id']} | {row['name']} ({row['target_date']})": row['id'] for index, row in df_records.iterrows()}
                    selected_str = st.selectbox("选择要删除的记录", options=list(delete_options.keys()))
                    if st.form_submit_button("危 确认删除"):
                        delete_id = delete_options[selected_str]
                        supabase.table("registrations").delete().eq("id", delete_id).execute()
                        st.success(f"✅ 记录删除成功！")
                        st.rerun()
            else:
                st.info("📂 当前无任何排班记录。")
                
        # --- 子标签页 2：日志调阅 (包含批量空间管理) ---
        with admin_sub_tab2:
            st.write("📊 **公司全体人员日志云端库：**")
            
            all_emp_names = list(EMPLOYEES.values())
            filter_emp = st.selectbox("请选择要调阅的员工日志", options=["查看所有人"] + all_emp_names)
            
            # 还原您截图中新增的“批量空间管理”模块
            st.divider()
            st.subheader("🛠️ 批量空间管理")
            col_batch1, col_batch2 = st.columns(2)
            with col_batch1:
                if st.button("📦 1. 预备打包当前列表中的日志", use_container_width=True):
                    st.info("💡 提示：请将您本地的批量打包下载逻辑整合至此处。")
            with col_batch2:
                if st.button("🚨 一键清空当前列表所有日志 (危险操作)", use_container_width=True):
                    st.warning("💡 提示：请将您本地的批量清空代码整合至此处。")
            
            st.divider()
            st.subheader("📄 日志明细列表")
            
            try:
                if filter_emp == "查看所有人":
                    all_logs_res = supabase.table("work_logs").select("*").order("submit_time", desc=True).execute()
                else:
                    all_logs_res = supabase.table("work_logs").select("*").eq("name", filter_emp).order("submit_time", desc=True).execute()
                
                all_logs = all_logs_res.data
                
                if all_logs:
                    for log in all_logs:
                        col_info, col_dl, col_del = st.columns([3, 1, 1])
                        with col_info:
                            st.text(f"👤 提交人: {log['name']} | 📄 文件名: {log['file_name']}\n⏱️ 上传时间: {log['submit_time'].replace('T', ' ').split('.')[0]}")
                        with col_dl:
                            try:
                                dl_url = supabase.storage.from_("work_logs").get_public_url(log['file_path'])
                                st.markdown(f"[📥 点击下载]({dl_url})", unsafe_allow_html=True)
                            except:
                                st.write("获取链接失败")
                        with col_del:
                            if st.button("危 强制删除", key=f"del_admin_{log['id']}"):
                                try:
                                    supabase.storage.from_("work_logs").remove([log['file_path']])
                                    supabase.table("work_logs").delete().eq("id", log["id"]).execute()
                                    st.success("✅ 该员工日志已从系统彻底清除。")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ 删除失败：{e}")
                        st.markdown("---")
                else:
                    st.info("📂 暂无符合条件的工作日志上传记录。")
            except Exception as e:
                st.warning(f"⚠️ 无法读取工作日志数据：{e}")
                
        # --- 子标签页 3：全新版考勤矩阵 ---
        with admin_sub_tab3:
            st.write("📊 **自动拉取时间段内每个人的提交情况，红十字标红工作日缺交人员：**")
            
            col1, col2 = st.columns(2)
            with col1:
                check_start = st.date_input("选择起始日期", value=date.today() - timedelta(days=7))
            with col2:
                check_end = st.date_input("选择结束日期", value=date.today())
                
            if st.button("🔍 生成考勤分析矩阵", type="primary", use_container_width=True):
                if check_start > check_end:
                    st.error("❌ 开始日期不能晚于结束日期！")
                else:
                    with st.spinner("正在分析全体人员打卡数据..."):
                        try:
                            start_time_str = f"{check_start} 00:00:00+08:00"
                            end_time_str = f"{check_end} 23:59:59+08:00"
                            response = supabase.table('work_logs').select('name, submit_time').gte('submit_time', start_time_str).lte('submit_time', end_time_str).execute()
                            logs_data = response.data
                            
                            emp_submissions = {name: set() for name in EMPLOYEES.values()}
                            if logs_data:
                                for log in logs_data:
                                    emp_name = log.get('name')
                                    submit_time = log.get('submit_time')
                                    if emp_name in emp_submissions and submit_time:
                                        log_date = get_local_date(submit_time)
                                        if log_date:
                                            emp_submissions[emp_name].add(log_date)
                            
                            delta = check_end - check_start
                            date_list = [check_start + timedelta(days=i) for i in range(delta.days + 1)]
                            
                            matrix_data = []
                            for emp in EMPLOYEES.values():
                                row = {"员工姓名": emp}
                                missed_workdays = 0
                                
                                for d in date_list:
                                    is_workday = d.weekday() < 5 
                                    has_submitted = d in emp_submissions[emp]
                                    date_str = d.strftime("%m-%d")
                                    
                                    if has_submitted:
                                        row[date_str] = "✅ 已交"
                                    else:
                                        if is_workday:
                                            row[date_str] = "❌ 缺交"
                                            missed_workdays += 1
                                        else:
                                            row[date_str] = "➖ 周末"
                                
                                row["🔴 工作日缺交汇总"] = missed_workdays
                                matrix_data.append(row)
                                
                            df_matrix = pd.DataFrame(matrix_data)
                            df_matrix = df_matrix.sort_values(by="🔴 工作日缺交汇总", ascending=False)
                            
                            def highlight_matrix(val):
                                if val == "❌ 缺交":
                                    return 'color: #D32F2F; font-weight: bold; background-color: #ffebee;'
                                elif val == "✅ 已交":
                                    return 'color: #388E3C;'
                                elif val == "➖ 周末":
                                    return 'color: #9E9E9E;'
                                elif isinstance(val, int):
                                    if val > 0:
                                        return 'color: #D32F2F; font-weight: bold;'
                                    else:
                                        return 'color: #388E3C; font-weight: bold;'
                                return ''
                            
                            st.divider()
                            st.subheader(f"📅 考勤矩阵：{check_start} 至 {check_end}")
                            st.caption("注：按『工作日缺交汇总』次数由高到低排序。周末不强制提交，计为灰底。")
                            
                            st.dataframe(
                                df_matrix.style.map(highlight_matrix),
                                use_container_width=True, 
                                hide_index=True
                            )
                            
                        except Exception as e:
                            st.error(f"🚨 考勤数据分析失败: {e}")
