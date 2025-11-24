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


class Work(SQLModel, table=True):
    """
    作品模型（对应数据库中的work表）
    
    字段说明：
    - id: 作品ID，主键
    - user_id: 用户ID，外键关联到user表
    - title: 作品标题
    - description: 作品描述（可选）
    - image_url: 作品图片URL
    - prompt: AI生成提示词
    - negative_prompt: 负面提示词（可选）
    - model: 使用的AI模型（可选）
    - parameters: 其他参数，以JSON字符串形式存储
    - status: 作品状态（pending待处理, processing处理中, completed已完成, failed失败）
    - created_at: 创建时间
    - updated_at: 更新时间
    
    注意：
    - parameters字段存储为JSON字符串，需要使用get_parameters()和set_parameters()方法转换
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)  # 外键，关联到user表的id字段
    title: str  # 作品标题
    description: Optional[str] = None  # 作品描述
    image_url: str  # 图片URL
    prompt: str  # AI生成提示词
    negative_prompt: Optional[str] = None  # 负面提示词
    model: Optional[str] = None  # AI模型名称
    # 参数字段：存储为JSON字符串
    # 因为SQLite不支持JSON类型，所以用字符串存储
    parameters: Optional[str] = None
    # 作品状态：pending(待处理), processing(处理中), completed(已完成), failed(失败)
    status: str = Field(default="pending")
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)

    def get_parameters(self) -> Optional[Dict[str, Any]]:
        """
        获取参数字典
        
        功能说明：
        将存储的JSON字符串转换为Python字典
        
        返回：
        - 参数字典，如果parameters为None则返回None
        
        示例：
        work.parameters = '{"width": 512, "height": 512}'
        params = work.get_parameters()  # 返回 {"width": 512, "height": 512}
        """
        if self.parameters:
            # json.loads(): 将JSON字符串解析为Python字典
            return json.loads(self.parameters)
        return None

    def set_parameters(self, params: Optional[Dict[str, Any]]):
        """
        设置参数字典
        
        功能说明：
        将Python字典转换为JSON字符串存储
        
        参数：
        - params: 参数字典，如果为None则设置为None
        
        示例：
        work.set_parameters({"width": 512, "height": 512})
        # work.parameters 现在是 '{"width": 512, "height": 512}'
        """
        if params:
            # json.dumps(): 将Python字典转换为JSON字符串
            self.parameters = json.dumps(params)
        else:
            self.parameters = None


class ConsumptionRecord(SQLModel, table=True):
    """
    消费记录模型（对应数据库中的consumptionrecord表）
    
    字段说明：
    - id: 记录ID，主键
    - user_id: 用户ID，外键关联到user表
    - type: 消费类型（image_generation图片生成, premium_feature高级功能, subscription订阅）
    - amount: 消费金额
    - description: 消费描述
    - status: 消费状态（success成功, failed失败, refunded已退款）
    - created_at: 创建时间（消费时间）
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)  # 外键，关联到user表
    # 消费类型：image_generation(图片生成), premium_feature(高级功能), subscription(订阅)
    type: str
    amount: float  # 消费金额（浮点数）
    description: str  # 消费描述
    # 消费状态：success(成功), failed(失败), refunded(已退款)
    status: str = Field(default="success")
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
