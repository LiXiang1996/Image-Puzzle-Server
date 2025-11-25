"""
FastAPI 主应用文件
这是整个后端服务的入口文件，定义了所有的API接口

主要功能：
1. 创建FastAPI应用实例
2. 配置CORS跨域支持
3. 初始化数据库
4. 定义所有API接口（认证、作品、消费等）

@author: lixiang
@date: 2025-11-20
"""
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from db.database import init_db, get_session
from db.models import User, Work, ConsumptionRecord
from auth import create_access_token, get_current_user
import uvicorn
import os
import shutil
from pathlib import Path

# ==================== FastAPI应用初始化 ====================

# 创建FastAPI应用实例
# title: API文档中显示的标题
# version: API版本号
app = FastAPI(title="图片积木后端API", version="1.0.0")

# ==================== CORS跨域配置 ====================
# 配置CORS（跨域资源共享），允许前端访问后端API
# 
# 配置说明：
# - 开发环境：允许 localhost:3000（本地开发）
# - 生产环境：通过环境变量 ALLOWED_ORIGINS 配置允许的前端域名
#   例如：ALLOWED_ORIGINS=https://your-frontend-domain.com,https://www.your-frontend-domain.com
# 
# 为什么需要 CORS？
# - 浏览器的同源策略会阻止跨域请求
# - 前端和后端可能部署在不同的域名/端口上
# - CORS 允许后端明确指定哪些前端可以访问API
import os
# 从环境变量读取允许的来源，如果没有设置则默认允许 localhost:3000（开发环境）
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    # 生产环境：从环境变量读取允许的域名列表
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
else:
    # 开发环境：默认允许 localhost:3000
    allowed_origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # 允许的前端地址列表
    allow_credentials=True,  # 允许携带认证信息（如cookie、token）
    allow_methods=["*"],  # 允许所有HTTP方法（GET、POST、PUT、DELETE等）
    allow_headers=["*"],  # 允许所有请求头
)

# 初始化数据库
# 在应用启动时创建数据库表结构
init_db()

# 配置静态文件服务（用于访问上传的图片）
# Vercel 环境处理：
# - Vercel 是无服务器环境，文件系统是只读的，无法创建目录和写入文件
# - 在 Vercel 环境下跳过静态文件目录的创建和挂载
# - 文件上传功能需要使用云存储（如 AWS S3、Cloudinary 等）
if not os.getenv("VERCEL"):
    # 本地开发环境：创建uploads目录并挂载静态文件服务
    os.makedirs("uploads/avatars", exist_ok=True)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    print("✅ 静态文件服务已启用（本地开发环境）")
else:
    # Vercel 环境：跳过静态文件目录创建
    print("⚠️  检测到 Vercel 环境，跳过静态文件目录创建")
    print("⚠️  文件上传功能需要使用云存储（如 AWS S3、Cloudinary 等）")


# ==================== 请求/响应数据模型定义 ====================
# 这些类定义了API接口的请求和响应数据结构
# 使用Pydantic进行数据验证和序列化

class RegisterRequest(BaseModel):
    """用户注册请求模型"""
    username: str  # 用户名（必填）
    password: str  # 密码（必填）
    email: Optional[str] = None  # 邮箱（可选）


class LoginRequest(BaseModel):
    """用户登录请求模型"""
    username: str  # 用户名
    password: str  # 密码


class LoginResponse(BaseModel):
    """登录响应模型"""
    code: int = 200  # 状态码，200表示成功
    message: str = "success"  # 响应消息
    data: dict  # 响应数据（包含token和用户信息）


class UserInfoResponse(BaseModel):
    """用户信息响应模型"""
    id: str
    username: str
    email: Optional[str] = None
    avatar: Optional[str] = None


class WorkCreate(BaseModel):
    """创建作品请求模型"""
    title: str  # 作品标题
    description: Optional[str] = None  # 作品描述（可选）
    image_url: str  # 图片URL
    prompt: str  # AI生成提示词
    negative_prompt: Optional[str] = None  # 负面提示词（可选）
    model: Optional[str] = None  # 使用的AI模型（可选）
    parameters: Optional[dict] = None  # 其他参数（可选）


class WorkUpdate(BaseModel):
    """更新作品请求模型"""
    # 所有字段都是可选的，只更新提供的字段
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    model: Optional[str] = None
    parameters: Optional[dict] = None
    status: Optional[str] = None  # 作品状态：pending, processing, completed, failed


class ConsumptionHistoryParams(BaseModel):
    """消费历史查询参数模型"""
    page: Optional[int] = 1  # 页码，默认第1页
    page_size: Optional[int] = 10  # 每页记录数，默认10条
    start_date: Optional[str] = None  # 开始日期（可选）
    end_date: Optional[str] = None  # 结束日期（可选）


class UserUpdateRequest(BaseModel):
    """更新用户信息请求模型"""
    email: Optional[str] = None  # 邮箱（可选）
    nickname: Optional[str] = None  # 昵称（可选）
    phone: Optional[str] = None  # 手机号（可选）
    bio: Optional[str] = None  # 个人简介（可选）
    location: Optional[str] = None  # 所在地（可选）
    website: Optional[str] = None  # 个人网站（可选）


# ==================== 认证相关接口 ====================

@app.post("/api/auth/register", response_model=dict)
def register(data: RegisterRequest, session: Session = Depends(get_session)):
    """
    用户注册接口
    
    功能说明：
    1. 检查用户名是否已存在
    2. 如果不存在，创建新用户
    3. 返回注册结果
    
    参数：
    - data: 注册请求数据（用户名、密码、邮箱）
    - session: 数据库会话（自动注入）
    
    返回：
    - 成功：返回用户ID
    - 失败：返回错误信息（用户名已存在或服务器错误）
    """
    try:
        # 查询数据库中是否已存在该用户名
        # select(User): 选择User表
        # .where(): 添加查询条件
        # .first(): 获取第一条结果，如果没有则返回None
        user = session.exec(select(User).where(User.username == data.username)).first()
        
        # 如果用户已存在，返回400错误
        if user:
            raise HTTPException(status_code=400, detail="用户名已存在")
        
        # 创建新用户对象
        # User是数据库模型类，对应数据库中的user表
        new_user = User(
            username=data.username,
            password=data.password,  # 注意：实际项目中应该使用密码加密（如bcrypt）
            email=data.email
        )
        
        # 将新用户添加到数据库会话
        session.add(new_user)
        # 提交事务，将数据保存到数据库
        session.commit()
        # 刷新对象，获取数据库自动生成的ID等字段
        session.refresh(new_user)
        
        # 返回成功响应
        return {
            "code": 200,
            "message": "注册成功",
            "data": {"user_id": new_user.id}
        }
    except HTTPException:
        # HTTP异常直接重新抛出（如用户名已存在）
        raise
    except Exception as e:
        # 其他异常记录日志并返回500错误
        print(f"注册错误: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()  # 打印完整的错误堆栈
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@app.post("/api/auth/login", response_model=LoginResponse)
def login(data: LoginRequest, session: Session = Depends(get_session)):
    """
    用户登录接口
    
    功能说明：
    1. 验证用户名和密码
    2. 如果验证通过，生成JWT token
    3. 返回token和用户信息
    
    参数：
    - data: 登录请求数据（用户名、密码）
    - session: 数据库会话
    
    返回：
    - 成功：返回token和用户信息
    - 失败：返回401错误（用户名或密码错误）
    """
    # 查询用户：用户名和密码都匹配
    user = session.exec(
        select(User).where(
            User.username == data.username,
            User.password == data.password
        )
    ).first()
    
    # 如果用户不存在或密码错误
    if not user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    
    # 生成JWT token
    # data={"sub": str(user.id)}: token中存储用户ID（必须是字符串）
    # sub是JWT标准字段，表示subject（主题/用户ID）
    # 注意：JWT标准要求sub字段必须是字符串类型
    access_token = create_access_token(data={"sub": str(user.id)})
    
    # 返回登录成功响应
    return LoginResponse(
        code=200,
        message="登录成功",
        data={
            "token": access_token,  # JWT token，前端需要保存这个token
            "userInfo": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email or "",  # 如果email为None，返回空字符串
                "avatar": user.avatar
            }
        }
    )


@app.get("/api/auth/user", response_model=dict)
def get_user_info(current_user: User = Depends(get_current_user)):
    """
    获取当前登录用户信息
    
    功能说明：
    从JWT token中解析用户ID，然后查询数据库获取用户详细信息
    
    参数：
    - current_user: 当前登录用户（通过get_current_user自动获取）
    
    返回：
    - 用户详细信息
    
    注意：
    - 这个接口需要认证（需要token）
    - get_current_user会自动验证token并获取用户信息
    """
    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": str(current_user.id),
            "username": current_user.username,
            "email": current_user.email or "",
            "avatar": current_user.avatar,
            "nickname": current_user.nickname,
            "phone": current_user.phone,
            # 将datetime对象转换为ISO格式字符串
            "createdAt": current_user.created_at.isoformat() if current_user.created_at else "",
            "updatedAt": current_user.updated_at.isoformat() if current_user.updated_at else ""
        }
    }


@app.put("/api/auth/user", response_model=dict)
def update_user_info(
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    更新用户信息接口
    
    功能说明：
    更新当前登录用户的信息（昵称、邮箱等）
    
    参数：
    - data: 要更新的用户信息（所有字段都是可选的）
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 更新后的用户信息
    
    注意：
    - 只更新提供的字段，未提供的字段保持不变
    - 更新时会自动更新updated_at时间戳
    """
    try:
        # 更新字段（只更新提供的字段）
        if data.email is not None:
            current_user.email = data.email
        if data.nickname is not None:
            current_user.nickname = data.nickname
        if data.phone is not None:
            current_user.phone = data.phone
        if data.bio is not None:
            current_user.bio = data.bio
        if data.location is not None:
            current_user.location = data.location
        if data.website is not None:
            current_user.website = data.website
        
        # 更新修改时间
        current_user.updated_at = datetime.now()
        
        # 保存更改
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
        
        # 返回更新后的用户信息
        return {
            "code": 200,
            "message": "更新成功",
            "data": {
                "id": str(current_user.id),
                "username": current_user.username,
                "email": current_user.email or "",
                "avatar": current_user.avatar,
                "nickname": current_user.nickname,
                "phone": current_user.phone,
                "bio": current_user.bio,
                "location": current_user.location,
                "website": current_user.website,
                "createdAt": current_user.created_at.isoformat() if current_user.created_at else "",
                "updatedAt": current_user.updated_at.isoformat() if current_user.updated_at else ""
            }
        }
    except Exception as e:
        print(f"更新用户信息错误: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@app.post("/api/auth/upload-avatar", response_model=dict)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    上传用户头像接口
    
    功能说明：
    上传用户头像图片，保存到服务器并返回图片URL
    
    参数：
    - file: 上传的图片文件
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 图片URL
    
    注意：
    - 只支持图片格式（jpg, jpeg, png, gif）
    - 文件大小限制为5MB
    - 图片保存在uploads/avatars目录下
    """
    try:
        # 检查文件类型
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="只支持图片格式：jpg, jpeg, png, gif")
        
        # 检查文件大小（5MB限制）
        file_content = await file.read()
        if len(file_content) > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(status_code=400, detail="文件大小不能超过5MB")
        
        # 创建上传目录
        upload_dir = Path("uploads/avatars")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名（使用用户ID和时间戳）
        file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        filename = f"{current_user.id}_{int(datetime.now().timestamp())}.{file_extension}"
        file_path = upload_dir / filename
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        
        # 生成访问URL（相对路径，前端需要配置静态文件服务）
        avatar_url = f"/uploads/avatars/{filename}"
        
        # 更新用户头像URL
        current_user.avatar = avatar_url
        current_user.updated_at = datetime.now()
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
        
        return {
            "code": 200,
            "message": "上传成功",
            "data": {
                "avatar": avatar_url,
                "url": avatar_url  # 兼容性字段
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"上传头像错误: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@app.post("/api/auth/logout", response_model=dict)
def logout():
    """
    退出登录接口
    
    功能说明：
    实际上JWT是无状态的，服务端不需要做任何操作
    前端只需要删除本地存储的token即可
    
    返回：
    - 成功消息
    
    注意：
    - 真正的退出登录是前端删除token
    - 这个接口主要是为了API设计的完整性
    """
    return {
        "code": 200,
        "message": "退出成功",
        "data": {}
    }


# ==================== 作品相关接口 ====================

@app.get("/api/works", response_model=dict)
def get_works(
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    获取作品列表接口
    
    功能说明：
    1. 获取当前登录用户的所有作品
    2. 支持分页查询
    3. 只返回当前用户的作品（不能查看其他用户的作品）
    
    参数：
    - page: 页码，从1开始
    - page_size: 每页记录数
    - current_user: 当前登录用户（自动注入）
    - session: 数据库会话（自动注入）
    
    返回：
    - 作品列表（数组）
    
    注意：
    - 需要登录认证（需要token）
    - 只返回当前用户的作品
    """
    # 计算偏移量：跳过前面的记录
    # 例如：第2页，每页10条，offset = (2-1) * 10 = 10（跳过前10条）
    offset = (page - 1) * page_size
    
    # 构建查询语句：查询当前用户的所有作品
    statement = select(Work).where(Work.user_id == current_user.id)
    # 用于统计总数的查询（不分页）
    total_statement = select(Work).where(Work.user_id == current_user.id)
    
    # 执行分页查询
    # .offset(offset): 跳过前面的记录
    # .limit(page_size): 限制返回的记录数
    # .all(): 获取所有结果
    works = session.exec(statement.offset(offset).limit(page_size)).all()
    # 统计总数（用于前端分页显示）
    total = len(session.exec(total_statement).all())
    
    # 将数据库对象转换为字典格式（便于JSON序列化）
    works_list = []
    for work in works:
        works_list.append({
            "id": str(work.id),
            "title": work.title,
            "description": work.description,
            "imageUrl": work.image_url,  # 注意：前端使用驼峰命名，后端使用下划线
            "prompt": work.prompt,
            "negativePrompt": work.negative_prompt,
            "model": work.model,
            "parameters": work.get_parameters(),  # 调用模型方法将JSON字符串转换为字典
            "status": work.status,
            "createdAt": work.created_at.isoformat() if work.created_at else "",
            "updatedAt": work.updated_at.isoformat() if work.updated_at else ""
        })
    
    return {
        "code": 200,
        "message": "success",
        "data": works_list
    }


@app.get("/api/works/{work_id}", response_model=dict)
def get_work_by_id(
    work_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    获取单个作品详情接口
    
    功能说明：
    根据作品ID获取作品详情，但只能获取当前用户自己的作品
    
    参数：
    - work_id: 作品ID（路径参数）
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 作品详情
    
    注意：
    - 如果作品不存在或不属于当前用户，返回404错误
    """
    # 根据ID查询作品
    work = session.get(Work, work_id)
    
    # 检查作品是否存在且属于当前用户
    if not work or work.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="作品不存在")
    
    # 返回作品详情
    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": str(work.id),
            "title": work.title,
            "description": work.description,
            "imageUrl": work.image_url,
            "prompt": work.prompt,
            "negativePrompt": work.negative_prompt,
            "model": work.model,
            "parameters": work.get_parameters(),
            "status": work.status,
            "createdAt": work.created_at.isoformat() if work.created_at else "",
            "updatedAt": work.updated_at.isoformat() if work.updated_at else ""
        }
    }


@app.post("/api/works", response_model=dict)
def create_work(
    data: WorkCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    创建新作品接口
    
    功能说明：
    为当前登录用户创建一个新作品
    
    参数：
    - data: 作品数据
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 创建的作品信息
    
    注意：
    - 新作品默认状态为"pending"（待处理）
    """
    # 创建作品对象
    new_work = Work(
        user_id=current_user.id,  # 关联到当前用户
        title=data.title,
        description=data.description,
        image_url=data.image_url,
        prompt=data.prompt,
        negative_prompt=data.negative_prompt,
        model=data.model,
        status="pending"  # 默认状态：待处理
    )
    # 设置参数字典（会转换为JSON字符串存储）
    new_work.set_parameters(data.parameters)
    
    # 保存到数据库
    session.add(new_work)
    session.commit()
    session.refresh(new_work)
    
    # 返回创建的作品
    return {
        "code": 200,
        "message": "创建成功",
        "data": {
            "id": str(new_work.id),
            "title": new_work.title,
            "description": new_work.description,
            "imageUrl": new_work.image_url,
            "prompt": new_work.prompt,
            "negativePrompt": new_work.negative_prompt,
            "model": new_work.model,
            "parameters": new_work.get_parameters(),
            "status": new_work.status,
            "createdAt": new_work.created_at.isoformat() if new_work.created_at else "",
            "updatedAt": new_work.updated_at.isoformat() if new_work.updated_at else ""
        }
    }


@app.put("/api/works/{work_id}", response_model=dict)
def update_work(
    work_id: int,
    data: WorkUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    更新作品接口
    
    功能说明：
    更新作品信息，只能更新当前用户自己的作品
    
    参数：
    - work_id: 作品ID（路径参数）
    - data: 要更新的数据（所有字段都是可选的）
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 更新后的作品信息
    
    注意：
    - 只更新提供的字段，未提供的字段保持不变
    - 更新时会自动更新updated_at时间戳
    """
    # 查询作品
    work = session.get(Work, work_id)
    
    # 检查作品是否存在且属于当前用户
    if not work or work.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="作品不存在")
    
    # 更新字段（只更新提供的字段）
    # 使用 is not None 判断，因为有些字段可能为None（需要设置为None）
    if data.title is not None:
        work.title = data.title
    if data.description is not None:
        work.description = data.description
    if data.image_url is not None:
        work.image_url = data.image_url
    if data.prompt is not None:
        work.prompt = data.prompt
    if data.negative_prompt is not None:
        work.negative_prompt = data.negative_prompt
    if data.model is not None:
        work.model = data.model
    if data.parameters is not None:
        work.set_parameters(data.parameters)
    if data.status is not None:
        work.status = data.status
    
    # 更新修改时间
    work.updated_at = datetime.now()
    
    # 保存更改
    session.add(work)
    session.commit()
    session.refresh(work)
    
    # 返回更新后的作品
    return {
        "code": 200,
        "message": "更新成功",
        "data": {
            "id": str(work.id),
            "title": work.title,
            "description": work.description,
            "imageUrl": work.image_url,
            "prompt": work.prompt,
            "negativePrompt": work.negative_prompt,
            "model": work.model,
            "parameters": work.get_parameters(),
            "status": work.status,
            "createdAt": work.created_at.isoformat() if work.created_at else "",
            "updatedAt": work.updated_at.isoformat() if work.updated_at else ""
        }
    }


@app.delete("/api/works/{work_id}", response_model=dict)
def delete_work(
    work_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    删除作品接口
    
    功能说明：
    删除指定的作品，只能删除当前用户自己的作品
    
    参数：
    - work_id: 作品ID（路径参数）
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 删除成功消息
    
    注意：
    - 删除操作不可恢复，请谨慎操作
    """
    # 查询作品
    work = session.get(Work, work_id)
    
    # 检查作品是否存在且属于当前用户
    if not work or work.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="作品不存在")
    
    # 删除作品
    session.delete(work)
    session.commit()
    
    return {
        "code": 200,
        "message": "删除成功",
        "data": {}
    }


# ==================== 消费相关接口 ====================

@app.get("/api/consumption/history", response_model=dict)
def get_consumption_history(
    page: int = 1,
    page_size: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    获取消费历史记录接口
    
    功能说明：
    1. 获取当前用户的消费记录
    2. 支持分页查询
    3. 支持按日期范围筛选
    
    参数：
    - page: 页码
    - page_size: 每页记录数
    - start_date: 开始日期（可选，ISO格式字符串）
    - end_date: 结束日期（可选，ISO格式字符串）
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 消费记录列表和分页信息
    """
    # 计算偏移量
    offset = (page - 1) * page_size
    
    # 构建基础查询：查询当前用户的所有消费记录
    statement = select(ConsumptionRecord).where(ConsumptionRecord.user_id == current_user.id)
    total_statement = select(ConsumptionRecord).where(ConsumptionRecord.user_id == current_user.id)
    
    # 日期范围过滤（如果提供了日期参数）
    if start_date:
        # 将ISO格式字符串转换为datetime对象
        # replace('Z', '+00:00'): 处理时区格式
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        # 添加日期条件：创建时间 >= 开始日期
        statement = statement.where(ConsumptionRecord.created_at >= start_dt)
        total_statement = total_statement.where(ConsumptionRecord.created_at >= start_dt)
    
    if end_date:
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        # 添加日期条件：创建时间 <= 结束日期
        statement = statement.where(ConsumptionRecord.created_at <= end_dt)
        total_statement = total_statement.where(ConsumptionRecord.created_at <= end_dt)
    
    # 执行分页查询
    records = session.exec(statement.offset(offset).limit(page_size)).all()
    # 统计总数（用于分页）
    total = len(session.exec(total_statement).all())
    
    # 转换为字典格式
    records_list = []
    for record in records:
        records_list.append({
            "id": str(record.id),
            "type": record.type,  # 消费类型：image_generation, premium_feature, subscription
            "amount": record.amount,  # 消费金额
            "description": record.description,  # 描述
            "status": record.status,  # 状态：success, failed, refunded
            "createdAt": record.created_at.isoformat() if record.created_at else ""
        })
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "list": records_list,  # 记录列表
            "total": total,  # 总记录数
            "page": page,  # 当前页码
            "pageSize": page_size  # 每页记录数
        }
    }


@app.get("/api/consumption/stats", response_model=dict)
def get_consumption_stats(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    获取消费统计信息接口
    
    功能说明：
    统计当前用户的总消费金额和总消费次数
    
    参数：
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 总消费金额和总消费次数
    """
    # 查询当前用户的所有消费记录
    records = session.exec(
        select(ConsumptionRecord).where(ConsumptionRecord.user_id == current_user.id)
    ).all()
    
    # 计算总消费金额（只统计成功的记录）
    # sum(): 求和函数
    # r.amount for r in records if r.status == "success": 列表推导式，筛选成功的记录并提取金额
    total_amount = sum(r.amount for r in records if r.status == "success")
    # 总记录数
    total_count = len(records)
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "totalAmount": total_amount,  # 总消费金额
            "totalCount": total_count  # 总消费次数
        }
    }


# ==================== 启动配置 ====================

if __name__ == "__main__":
    """
    应用启动入口
    
    当直接运行此文件时（python main.py），会启动FastAPI服务器
    
    参数说明：
    - app: FastAPI应用实例
    - host: 监听的主机地址，"0.0.0.0"表示监听所有网络接口
    - port: 监听端口，8080
    """
    uvicorn.run(app, host="0.0.0.0", port=8080)
