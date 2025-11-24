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

# ==================== 数据库连接配置 ====================

# SQLite数据库文件路径
# sqlite:/// 表示使用SQLite数据库
# ./test.db 表示数据库文件在当前目录下，文件名为test.db
DATABASE_URL = "sqlite:///./test.db"

# 创建数据库引擎
# echo=True: 打印所有SQL语句（用于调试，生产环境可以设为False）
engine = create_engine(DATABASE_URL, echo=True)


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
    from db.models import User, Work, ConsumptionRecord
    
    # 创建所有表
    # SQLModel.metadata.create_all(engine) 会：
    # 1. 检查metadata中注册的所有模型
    # 2. 如果表不存在，创建表
    # 3. 如果表已存在，不会修改（保持现有数据和结构）
    SQLModel.metadata.create_all(engine)
    print("数据库表初始化完成（已存在的表不会被修改）")
