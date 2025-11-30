"""
数据库模型定义
这个文件定义了所有数据库表的结构（模型）

主要概念：
- SQLModel: 结合了SQLAlchemy和Pydantic的ORM模型
- table=True: 表示这是一个数据库表（不是普通的Pydantic模型）
- Field: 定义字段的约束（主键、索引、默认值等）

@author: lixiang
@date: 2025-11-20
"""
from sqlmodel import SQLModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import json
from sqlalchemy import UniqueConstraint


class User(SQLModel, table=True):
    """
    用户模型（对应数据库中的user表）
    
    字段说明：
    - id: 用户ID，主键，自动递增
    - username: 用户名，唯一索引（不能重复）
    - password: 密码（注意：实际项目中应该加密存储）
    - email: 邮箱（可选）
    - avatar: 头像URL（可选）
    - nickname: 昵称（可选）
    - phone: 手机号（可选）
    - bio: 个人简介（可选）
    - location: 所在地（可选）
    - website: 个人网站（可选）
    - created_at: 创建时间，自动设置为当前时间
    - updated_at: 更新时间，自动设置为当前时间
    """
    id: Optional[int] = Field(default=None, primary_key=True)  # 主键，自动递增
    username: str = Field(index=True, unique=True)  # 用户名，建立索引且唯一
    password: str  # 密码字段
    email: Optional[str] = None  # 邮箱，可选字段
    avatar: Optional[str] = None  # 头像URL
    nickname: Optional[str] = None  # 昵称
    phone: Optional[str] = None  # 手机号
    bio: Optional[str] = None  # 个人简介
    location: Optional[str] = None  # 所在地
    website: Optional[str] = None  # 个人网站
    # 创建时间，使用default_factory在创建对象时自动设置当前时间
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    # 更新时间，使用default_factory在创建对象时自动设置当前时间
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)


class Note(SQLModel, table=True):
    """
    笔记模型（对应数据库中的note表）
    
    字段说明：
    - id: 笔记ID，主键
    - user_id: 用户ID，外键关联到user表
    - title: 笔记标题（必填），建立索引支持搜索
    - content: 笔记内容，Markdown格式存储
    - status: 笔记状态（private私密, public公开, draft草稿）
    - published_at: 发布时间（公开时设置），用于"发现广场"排序
    - created_at: 创建时间
    - updated_at: 最后编辑时间
    
    状态说明：
    - private: 私密笔记（默认）
    - public: 公开笔记（已发布，会出现在"发现广场"）
    - draft: 草稿（私密的子状态，仅用于用户自我管理）
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)  # 外键，关联到user表
    title: str = Field(index=True)  # 标题，建立索引支持搜索
    content: str  # 内容，Markdown格式存储
    status: str = Field(default="private")  # 状态：private/public/draft
    published_at: Optional[datetime] = None  # 发布时间（公开时设置）
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)


class Like(SQLModel, table=True):
    """
    喜爱（点赞）模型
    
    字段说明：
    - id: 主键
    - user_id: 用户ID，外键关联到user表
    - note_id: 笔记ID，外键关联到note表
    - created_at: 点赞时间
    
    索引：
    - (user_id, note_id) 唯一索引，防止重复点赞
    """
    __table_args__ = (UniqueConstraint("user_id", "note_id", name="unique_user_note_like"),)
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    note_id: int = Field(foreign_key="note.id", index=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)


class Favorite(SQLModel, table=True):
    """
    收藏模型
    
    字段说明：
    - id: 主键
    - user_id: 用户ID，外键关联到user表
    - note_id: 笔记ID，外键关联到note表
    - created_at: 收藏时间
    
    索引：
    - (user_id, note_id) 唯一索引，防止重复收藏
    """
    __table_args__ = (UniqueConstraint("user_id", "note_id", name="unique_user_note_favorite"),)
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    note_id: int = Field(foreign_key="note.id", index=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)


class Comment(SQLModel, table=True):
    """
    评论模型
    
    字段说明：
    - id: 主键
    - user_id: 用户ID，外键关联到user表
    - note_id: 笔记ID，外键关联到note表
    - parent_id: 父评论ID（用于回复，如果是顶级评论则为None）
    - content: 评论内容
    - created_at: 评论时间
    
    索引：
    - note_id: 索引，用于快速查询某笔记的所有评论
    - parent_id: 索引，用于快速查询某评论的所有回复
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    note_id: int = Field(foreign_key="note.id", index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="comment.id", index=True)  # 父评论ID，用于嵌套回复
    content: str  # 评论内容
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
