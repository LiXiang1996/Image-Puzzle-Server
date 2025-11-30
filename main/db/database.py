"""
数据库配置和连接管理
这个文件负责：
1. 创建数据库连接引擎
2. 管理数据库会话（Session）
3. 初始化数据库表结构

@author: lixiang
@date: 2025-11-20
"""
from sqlmodel import SQLModel, create_engine, Session
import os

# ==================== 环境判断 ====================
vercel_env = os.getenv("VERCEL_ENV", "development")
print(f"🌍 数据库环境: {vercel_env}")

# ==================== 数据库连接配置 ====================
# 
# 数据库类型选择：
# 1. PostgreSQL（生产环境推荐）：使用 Vercel Postgres 或其他云数据库
# 2. SQLite（本地开发）：使用文件数据库
# 
# 环境变量说明：
# - POSTGRES_URL: PostgreSQL 连接字符串（Vercel Postgres 会自动提供）
# - DATABASE_URL: 通用数据库连接字符串（如果设置了，优先使用）
# - VERCEL: Vercel 环境标识（如果设置了，优先使用 PostgreSQL）

# 优先检查是否有 PostgreSQL 连接字符串
postgres_url = os.getenv("POSTGRES_URL") or os.getenv("POSTGRES_PRISMA_URL") or os.getenv("DATABASE_URL")

if postgres_url and ("postgres://" in postgres_url or "postgresql://" in postgres_url):
    # 使用 PostgreSQL（Vercel Postgres 或其他云数据库）
    # 确保连接字符串格式正确（psycopg2 需要 postgresql:// 格式）
    if postgres_url.startswith("postgres://"):
        # Vercel Postgres 可能使用 postgres://，需要转换为 postgresql://
        postgres_url = postgres_url.replace("postgres://", "postgresql://", 1)
    DATABASE_URL = postgres_url
    if vercel_env == "production":
        print("✅ 使用 PostgreSQL 数据库（正式环境）")
    elif vercel_env == "preview":
        print("✅ 使用 PostgreSQL 数据库（测试环境）")
    else:
        print("✅ 使用 PostgreSQL 数据库")
elif os.getenv("VERCEL"):
    # Vercel 环境但没有配置 PostgreSQL：使用内存数据库（临时方案）
    DATABASE_URL = "sqlite:///:memory:"
    print("⚠️  检测到 Vercel 环境，但未配置 PostgreSQL")
    print("⚠️  使用内存数据库（数据不会持久化）")
    print("⚠️  请在 Vercel 项目设置中添加 Vercel Postgres 数据库")
else:
    # 本地开发环境：使用 SQLite 文件数据库
    DATABASE_URL = "sqlite:///./test.db"
    print("✅ 使用 SQLite 数据库（本地开发环境）")

# 创建数据库引擎
# echo=True: 打印所有SQL语句（用于调试，生产环境可以设为False）
# pool_pre_ping=True: 在每次使用连接前检查连接是否有效，如果无效则重新连接
#   这对于无服务器环境（如 Vercel）很重要，因为连接可能会被关闭
# pool_recycle=300: 连接回收时间（秒），300秒后重新创建连接
#   防止长时间连接导致的 SSL 连接关闭问题
# connect_args: 数据库连接参数
connect_args = {}
if DATABASE_URL.startswith("postgresql://"):
    # PostgreSQL 连接参数
    # 确保 SSL 连接配置正确
    connect_args = {
        "sslmode": "require",
        "connect_timeout": "10",  # 连接超时时间（秒）
    }

engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,  # 使用前检查连接有效性
    pool_recycle=300,    # 300秒后回收连接
    connect_args=connect_args
)


# ==================== 数据库会话管理 ====================

def get_session():
    """
    获取数据库会话（Session）
    
    功能说明：
    这是一个依赖注入函数，FastAPI会自动调用它来创建数据库会话
    使用yield确保会话在使用完后自动关闭
    
    使用方式：
    在API接口函数中通过 Depends(get_session) 自动注入
    
    示例：
    def my_api(session: Session = Depends(get_session)):
        # 使用session进行数据库操作
        pass
    
    工作原理：
    1. 创建Session对象
    2. yield返回Session（函数暂停，等待使用）
    3. API函数执行完毕后，继续执行finally块
    4. 关闭Session，释放数据库连接
    """
    # 创建数据库会话
    session = Session(engine)
    try:
        # yield返回会话，函数暂停
        # FastAPI会使用这个会话执行API函数
        yield session
    finally:
        # 无论成功还是失败，都会执行这里
        # 关闭会话，释放数据库连接
        session.close()


# ==================== 数据库初始化 ====================

def init_db():
    """
    初始化数据库
    
    功能说明：
    1. 导入所有模型类（确保它们被注册到SQLModel.metadata中）
    2. 创建所有数据库表（如果表不存在）
    
    调用时机：
    在应用启动时调用（main.py中）
    
    注意：
    - 不会删除现有数据！
    - 只创建不存在的表，已存在的表不会被修改
    - 如果需要修改表结构，应该使用数据库迁移工具（如Alembic）
    """
    # 导入所有模型类
    # 这一步很重要：确保所有模型类被注册到SQLModel.metadata中
    # 如果不导入，SQLModel不知道要创建哪些表
    from db.models import User, Note, Like, Favorite, Comment
    
    # 创建所有表
    # SQLModel.metadata.create_all(engine) 会：
    # 1. 检查metadata中注册的所有模型
    # 2. 如果表不存在，创建表
    # 3. 如果表已存在，不会修改（保持现有数据和结构）
    SQLModel.metadata.create_all(engine)
    print("数据库表初始化完成（已存在的表不会被修改）")
