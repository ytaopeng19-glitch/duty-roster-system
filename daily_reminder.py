import os
from supabase import create_client

# ==========================================
# 1. 数据库配置 (适配 GitHub Actions)
# ==========================================
# 使用 os.environ 获取 GitHub Secrets，而不是 st.secrets
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

# 安全校验拦截
if not SUPABASE_URL or not SUPABASE_URL.startswith("http"):
    print("🚨 致命错误：未能正确读取到 SUPABASE_URL！")
    exit(1)

# 创建客户端
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 后续的业务代码从这里开始...
# ==========================================
