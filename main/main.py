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
from db.models import User, Note, Like, Favorite, Comment
from auth import create_access_token, get_current_user, get_current_user_optional
import uvicorn
import os
import shutil
import re
from pathlib import Path
import cloudinary
import cloudinary.uploader

# ==================== FastAPI应用初始化 ====================

# 创建FastAPI应用实例
# title: API文档中显示的标题
# version: API版本号
app = FastAPI(title="家书后端API", version="1.0.0")

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
import re

# ==================== 环境判断 ====================
# Vercel 会自动设置 VERCEL_ENV 环境变量：
# - production: 正式环境（main 分支）
# - preview: 测试环境（其他分支或 PR）
# - development: 开发环境（本地运行）
vercel_env = os.getenv("VERCEL_ENV", "development")
print(f"🌍 当前环境: {vercel_env}")

# 从环境变量读取允许的来源
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    # 从环境变量读取允许的域名列表
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
    print(f"✅ CORS 配置：允许的来源 = {allowed_origins}")
else:
    # 根据环境自动设置默认值
    if vercel_env == "production":
        # 正式环境：需要手动配置 ALLOWED_ORIGINS
        allowed_origins = []
        print("⚠️  正式环境：请设置 ALLOWED_ORIGINS 环境变量")
    elif vercel_env == "preview":
        # 测试环境：自动允许所有 Vercel 预览域名
        allowed_origins = []
        print("✅ 测试环境：将自动允许所有 Vercel 预览域名")
    else:
        # 开发环境：默认允许 localhost:3000
        allowed_origins = ["http://localhost:3000"]
        print(f"✅ 开发环境：默认允许 localhost:3000")

# 自定义 CORS 中间件，支持通配符匹配
@app.middleware("http")
async def add_cors_headers(request, call_next):
    origin = request.headers.get("origin")
    method = request.method
    path = request.url.path
    
    # 记录所有请求（包括 OPTIONS）
    print(f"🌐 收到请求: {method} {path}, Origin: {origin}, 环境: {vercel_env}")
    
    # 检查是否允许该来源
    is_allowed = False
    if origin:
        # 检查是否在允许列表中
        for allowed_origin in allowed_origins:
            if allowed_origin == origin:
                is_allowed = True
                print(f"✅ 来源匹配允许列表: {origin}")
                break
            # 支持通配符匹配：*.vercel.app
            elif "*" in allowed_origin:
                pattern = allowed_origin.replace(".", r"\.").replace("*", r".*")
                if re.match(pattern, origin):
                    is_allowed = True
                    print(f"✅ 来源匹配通配符: {allowed_origin} -> {origin}")
                    break
        
        # 自动允许所有 Vercel 域名（包括预览和正式环境）
        if not is_allowed and origin.endswith(".vercel.app"):
            is_allowed = True
            print(f"✅ 自动允许 Vercel 域名: {origin} (环境: {vercel_env})")
    
    # 处理 OPTIONS 预检请求
    if request.method == "OPTIONS":
        from fastapi.responses import Response
        # 对于 OPTIONS 请求，如果来源是 Vercel 域名，总是允许
        if origin and origin.endswith(".vercel.app"):
            is_allowed = True
            print(f"✅ [OPTIONS] 自动允许 Vercel 域名: {origin}")
        
        # 返回 CORS 预检响应（必须返回具体的 origin，不能是 "*"）
        cors_origin = origin if origin else "*"
        print(f"📤 [OPTIONS] 返回 CORS 响应: Origin={cors_origin}, Path={path}")
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": cors_origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )
    
    # 处理实际请求
    print(f"➡️  处理实际请求: {method} {path}, Origin: {origin}, Allowed: {is_allowed}")
    response = await call_next(request)
    
    # 如果允许该来源，添加 CORS 头
    if origin:
        # 再次检查（确保 Vercel 域名被允许）
        if not is_allowed and origin.endswith(".vercel.app"):
            is_allowed = True
            print(f"✅ 实际请求时自动允许 Vercel 域名: {origin}")
        
        if is_allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
            print(f"✅ 已添加 CORS 头: Origin={origin}")
        else:
            print(f"⚠️  来源未允许，未添加 CORS 头: {origin}")
    
    return response

# 使用 FastAPI 的 CORS 中间件
# 注意：自定义中间件已经处理了 CORS，这里作为备用
# 如果 allowed_origins 为空，FastAPI 中间件可能不会正确处理，所以主要依赖自定义中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],  # 如果为空，允许所有来源（由自定义中间件控制）
    allow_credentials=True,  # 允许携带认证信息（如cookie、token）
    allow_methods=["*"],  # 允许所有HTTP方法（GET、POST、PUT、DELETE等）
    allow_headers=["*"],  # 允许所有请求头
)

# 初始化数据库
# 在应用启动时创建数据库表结构
init_db()

# ==================== Cloudinary 云存储配置 ====================
# Cloudinary 是一个云存储服务，用于在 Vercel 等无服务器环境中存储文件
# 
# 配置说明：
# - 开发环境：如果没有配置 Cloudinary，则使用本地文件系统
# - 生产环境：通过环境变量配置 Cloudinary 凭证
# 
# 环境变量：
# - CLOUDINARY_CLOUD_NAME: Cloudinary 云名称
# - CLOUDINARY_API_KEY: Cloudinary API 密钥
# - CLOUDINARY_API_SECRET: Cloudinary API 密钥（保密）
# 
# 注册 Cloudinary：
# 1. 访问 https://cloudinary.com/users/register/free
# 2. 注册免费账号（25GB 存储，25GB 流量/月）
# 3. 在 Dashboard 中获取 Cloud Name、API Key、API Secret
# 4. 在 Vercel 项目设置中添加环境变量

cloudinary_cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
cloudinary_api_key = os.getenv("CLOUDINARY_API_KEY")
cloudinary_api_secret = os.getenv("CLOUDINARY_API_SECRET")

# 如果配置了 Cloudinary，则初始化
if cloudinary_cloud_name and cloudinary_api_key and cloudinary_api_secret:
    cloudinary.config(
        cloud_name=cloudinary_cloud_name,
        api_key=cloudinary_api_key,
        api_secret=cloudinary_api_secret,
        secure=True  # 使用 HTTPS
    )
    print("✅ Cloudinary 云存储已配置")
else:
    print("⚠️  未配置 Cloudinary，将使用本地文件系统（仅限本地开发环境）")

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


class NoteCreate(BaseModel):
    """创建笔记请求模型"""
    title: str  # 笔记标题（必填）
    content: str  # 笔记内容（Markdown格式）
    status: Optional[str] = "private"  # 状态：private/public/draft，默认private


class NoteUpdate(BaseModel):
    """更新笔记请求模型"""
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None  # 状态：private/public/draft


class NoteAutoSave(BaseModel):
    """自动保存请求模型"""
    content: str  # 笔记内容（只更新内容，不改变状态）


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
    try:
        print(f"🔐 登录请求：用户名 = {data.username}")
        # 查询用户：用户名和密码都匹配
        user = session.exec(
            select(User).where(
                User.username == data.username,
                User.password == data.password
            )
        ).first()
        
        # 如果用户不存在或密码错误
        if not user:
            print(f"❌ 登录失败：用户名或密码错误（用户名 = {data.username}）")
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        print(f"✅ 登录成功：用户ID = {user.id}, 用户名 = {user.username}")
        
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
    except HTTPException:
        # HTTP异常直接重新抛出（如用户名或密码错误）
        raise
    except Exception as e:
        # 其他异常记录日志并返回500错误
        print(f"❌ 登录错误: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()  # 打印完整的错误堆栈
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


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


@app.get("/api/users/{user_id}", response_model=dict)
def get_user_public_info(
    user_id: int,
    session: Session = Depends(get_session)
):
    """
    获取用户公开信息接口
    
    功能说明：
    获取用户的公开信息（昵称、头像、简介等），用于用户公开主页
    
    参数：
    - user_id: 用户ID
    - session: 数据库会话
    
    返回：
    - 用户公开信息
    """
    user = session.get(User, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 统计用户的公开文章数
    public_notes_count = len(session.exec(
        select(Note).where(Note.user_id == user_id).where(Note.status == "public")
    ).all())
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": str(user.id),
            "username": user.username,
            "nickname": user.nickname,
            "avatar": user.avatar,
            "bio": user.bio,
            "public_notes_count": public_notes_count,
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
    上传用户头像图片，保存到云存储或本地文件系统并返回图片URL
    
    参数：
    - file: 上传的图片文件
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 图片URL
    
    注意：
    - 只支持图片格式（jpg, jpeg, png, gif）
    - 文件大小限制为5MB
    - 优先使用 Cloudinary 云存储（生产环境）
    - 如果没有配置 Cloudinary，则使用本地文件系统（仅限本地开发环境）
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
        
        # 生成文件名（使用用户ID和时间戳）
        file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        filename = f"avatar_{current_user.id}_{int(datetime.now().timestamp())}.{file_extension}"
        
        # 检查是否配置了 Cloudinary（优先使用云存储）
        cloudinary_cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
        cloudinary_api_key = os.getenv("CLOUDINARY_API_KEY")
        cloudinary_api_secret = os.getenv("CLOUDINARY_API_SECRET")
        
        if cloudinary_cloud_name and cloudinary_api_key and cloudinary_api_secret:
            # ========== 使用 Cloudinary 云存储 ==========
            try:
                # 上传到 Cloudinary
                # folder: 指定文件夹路径，便于管理
                # public_id: 文件的唯一标识（不包含扩展名）
                # resource_type: 资源类型，image 表示图片
                upload_result = cloudinary.uploader.upload(
                    file_content,
                    folder="avatars",  # 存储在 avatars 文件夹下
                    public_id=f"user_{current_user.id}_{int(datetime.now().timestamp())}",  # 唯一标识
                    resource_type="image",
                    overwrite=True,  # 如果文件已存在则覆盖
                    transformation=[
                        {"width": 400, "height": 400, "crop": "fill", "gravity": "face"}  # 自动裁剪为400x400，智能识别人脸
                    ]
                )
                
                # Cloudinary 返回的 URL 是完整的 HTTPS URL
                avatar_url = upload_result.get("secure_url") or upload_result.get("url")
                
                print(f"✅ 头像已上传到 Cloudinary: {avatar_url}")
                
            except Exception as cloudinary_error:
                print(f"❌ Cloudinary 上传失败: {type(cloudinary_error).__name__}: {str(cloudinary_error)}")
                import traceback
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail=f"云存储上传失败: {str(cloudinary_error)}"
                )
        
        elif os.getenv("VERCEL"):
            # ========== Vercel 环境但没有配置 Cloudinary ==========
            raise HTTPException(
                status_code=503,
                detail="Vercel 环境需要配置 Cloudinary 云存储。请在 Vercel 项目设置中添加 CLOUDINARY_CLOUD_NAME、CLOUDINARY_API_KEY、CLOUDINARY_API_SECRET 环境变量"
            )
        
        else:
            # ========== 本地开发环境：使用本地文件系统 ==========
            # 创建上传目录
            upload_dir = Path("uploads/avatars")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = upload_dir / filename
            
            # 保存文件
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
            
            # 生成访问URL（相对路径，前端需要配置静态文件服务）
            avatar_url = f"/uploads/avatars/{filename}"
            
            print(f"✅ 头像已保存到本地: {avatar_url}")
        
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


# ==================== 笔记相关接口 ====================

@app.get("/api/notes", response_model=dict)
def get_notes(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    获取我的笔记列表接口
    
    功能说明：
    1. 获取当前登录用户的所有笔记
    2. 支持分页查询
    3. 支持按标题搜索
    4. 支持按状态筛选（private/public/draft）
    
    参数：
    - page: 页码，从1开始
    - page_size: 每页记录数
    - search: 搜索关键词（标题模糊搜索）
    - status: 状态筛选（private/public/draft）
    - current_user: 当前登录用户（自动注入）
    - session: 数据库会话（自动注入）
    
    返回：
    - 笔记列表和分页信息
    """
    offset = (page - 1) * page_size
    
    # 构建查询语句：查询当前用户的所有笔记
    statement = select(Note).where(Note.user_id == current_user.id)
    total_statement = select(Note).where(Note.user_id == current_user.id)
    
    # 状态筛选
    if status and status in ["private", "public", "draft"]:
        statement = statement.where(Note.status == status)
        total_statement = total_statement.where(Note.status == status)
    
    # 标题搜索（模糊匹配）
    if search and search.strip():
        search_term = f"%{search.strip()}%"
        statement = statement.where(Note.title.like(search_term))
        total_statement = total_statement.where(Note.title.like(search_term))
    
    # 执行分页查询
    notes = session.exec(statement.order_by(Note.updated_at.desc()).offset(offset).limit(page_size)).all()
    # 统计总数
    total_notes = session.exec(total_statement).all()
    total = len(total_notes)
    
    # 转换为字典格式
    notes_list = []
    for note in notes:
        # 提取内容预览（前50字符，去除HTML标签）
        content_preview = note.content[:50] if note.content else ""
        # 简单去除HTML标签
        content_preview = re.sub(r'<[^>]+>', '', content_preview)
        
        notes_list.append({
            "id": str(note.id),
            "title": note.title,
            "content_preview": content_preview,
            "status": note.status,
            "updated_at": note.updated_at.isoformat() if note.updated_at else "",
            "created_at": note.created_at.isoformat() if note.created_at else "",
        })
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "list": notes_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


@app.get("/api/notes/{note_id}", response_model=dict)
def get_note_by_id(
    note_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    获取笔记详情接口
    
    功能说明：
    根据笔记ID获取笔记详情，只能获取当前用户自己的笔记
    
    参数：
    - note_id: 笔记ID（路径参数）
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 笔记详情
    
    注意：
    - 如果笔记不存在或不属于当前用户，返回404错误
    """
    note = session.get(Note, note_id)
    
    # 检查笔记是否存在且属于当前用户
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": str(note.id),
            "user_id": str(note.user_id),
            "title": note.title,
            "content": note.content,
            "status": note.status,
            "published_at": note.published_at.isoformat() if note.published_at else None,
            "created_at": note.created_at.isoformat() if note.created_at else "",
            "updated_at": note.updated_at.isoformat() if note.updated_at else ""
        }
    }


@app.post("/api/notes", response_model=dict)
def create_note(
    data: NoteCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    创建新笔记接口
    
    功能说明：
    为当前登录用户创建一个新笔记
    
    参数：
    - data: 笔记数据
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 创建的笔记信息
    
    注意：
    - 新笔记默认状态为"private"（私密）
    - 如果状态为"public"，会自动设置published_at
    """
    # 创建笔记对象
    new_note = Note(
        user_id=current_user.id,
        title=data.title,
        content=data.content,
        status=data.status or "private"
    )
    
    # 如果状态为公开，设置发布时间
    if new_note.status == "public":
        new_note.published_at = datetime.now()
    
    # 保存到数据库
    session.add(new_note)
    session.commit()
    session.refresh(new_note)
    
    return {
        "code": 200,
        "message": "创建成功",
        "data": {
            "id": str(new_note.id),
            "user_id": str(new_note.user_id),
            "title": new_note.title,
            "content": new_note.content,
            "status": new_note.status,
            "published_at": new_note.published_at.isoformat() if new_note.published_at else None,
            "created_at": new_note.created_at.isoformat() if new_note.created_at else "",
            "updated_at": new_note.updated_at.isoformat() if new_note.updated_at else ""
        }
    }


@app.put("/api/notes/{note_id}", response_model=dict)
def update_note(
    note_id: int,
    data: NoteUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    更新笔记接口
    
    功能说明：
    更新笔记信息，只能更新当前用户自己的笔记
    
    参数：
    - note_id: 笔记ID（路径参数）
    - data: 要更新的数据（所有字段都是可选的）
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 更新后的笔记信息
    
    注意：
    - 只更新提供的字段，未提供的字段保持不变
    - 更新时会自动更新updated_at时间戳
    - 如果状态改为public，会自动设置published_at
    """
    note = session.get(Note, note_id)
    
    # 检查笔记是否存在且属于当前用户
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    # 更新字段
    if data.title is not None:
        note.title = data.title
    if data.content is not None:
        note.content = data.content
    if data.status is not None:
        note.status = data.status
        # 如果状态改为公开，设置发布时间
        if data.status == "public" and not note.published_at:
            note.published_at = datetime.now()
        # 如果状态改为私密或草稿，清除发布时间
        elif data.status in ["private", "draft"]:
            note.published_at = None
    
    # 更新修改时间
    note.updated_at = datetime.now()
    
    # 保存更改
    session.add(note)
    session.commit()
    session.refresh(note)
    
    return {
        "code": 200,
        "message": "更新成功",
        "data": {
            "id": str(note.id),
            "user_id": str(note.user_id),
            "title": note.title,
            "content": note.content,
            "status": note.status,
            "published_at": note.published_at.isoformat() if note.published_at else None,
            "created_at": note.created_at.isoformat() if note.created_at else "",
            "updated_at": note.updated_at.isoformat() if note.updated_at else ""
        }
    }


@app.delete("/api/notes/{note_id}", response_model=dict)
def delete_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    删除笔记接口
    
    功能说明：
    删除指定的笔记，只能删除当前用户自己的笔记
    
    参数：
    - note_id: 笔记ID（路径参数）
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 删除成功消息
    """
    note = session.get(Note, note_id)
    
    # 检查笔记是否存在且属于当前用户
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    # 删除笔记
    session.delete(note)
    session.commit()
    
    return {
        "code": 200,
        "message": "删除成功",
        "data": {}
    }


@app.put("/api/notes/{note_id}/publish", response_model=dict)
def publish_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    发布笔记接口（私密→公开）
    
    功能说明：
    将笔记状态从私密改为公开，并设置发布时间
    
    参数：
    - note_id: 笔记ID
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 更新后的笔记信息
    """
    note = session.get(Note, note_id)
    
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    note.status = "public"
    note.published_at = datetime.now()
    note.updated_at = datetime.now()
    
    session.add(note)
    session.commit()
    session.refresh(note)
    
    return {
        "code": 200,
        "message": "发布成功",
        "data": {
            "id": str(note.id),
            "user_id": str(note.user_id),
            "title": note.title,
            "content": note.content,
            "status": note.status,
            "published_at": note.published_at.isoformat() if note.published_at else None,
            "created_at": note.created_at.isoformat() if note.created_at else "",
            "updated_at": note.updated_at.isoformat() if note.updated_at else ""
        }
    }


@app.put("/api/notes/{note_id}/draft", response_model=dict)
def save_note_as_draft(
    note_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    存为草稿接口（公开→私密）
    
    功能说明：
    将笔记状态从公开改为私密（草稿），并清除发布时间
    
    参数：
    - note_id: 笔记ID
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 更新后的笔记信息
    """
    note = session.get(Note, note_id)
    
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    note.status = "draft"
    note.published_at = None
    note.updated_at = datetime.now()
    
    session.add(note)
    session.commit()
    session.refresh(note)
    
    return {
        "code": 200,
        "message": "已存为草稿",
        "data": {
            "id": str(note.id),
            "user_id": str(note.user_id),
            "title": note.title,
            "content": note.content,
            "status": note.status,
            "published_at": note.published_at.isoformat() if note.published_at else None,
            "created_at": note.created_at.isoformat() if note.created_at else "",
            "updated_at": note.updated_at.isoformat() if note.updated_at else ""
        }
    }


@app.put("/api/notes/{note_id}/autosave", response_model=dict)
def autosave_note(
    note_id: int,
    data: NoteAutoSave,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    自动保存笔记接口
    
    功能说明：
    只更新笔记内容，不改变状态（用于前端自动保存功能）
    
    参数：
    - note_id: 笔记ID
    - data: 笔记内容
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 更新后的笔记信息
    """
    note = session.get(Note, note_id)
    
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    note.content = data.content
    note.updated_at = datetime.now()
    
    session.add(note)
    session.commit()
    session.refresh(note)
    
    return {
        "code": 200,
        "message": "保存成功",
        "data": {
            "id": str(note.id),
            "user_id": str(note.user_id),
            "title": note.title,
            "content": note.content,
            "status": note.status,
            "published_at": note.published_at.isoformat() if note.published_at else None,
            "created_at": note.created_at.isoformat() if note.created_at else "",
            "updated_at": note.updated_at.isoformat() if note.updated_at else ""
        }
    }


# ==================== 发现广场相关接口 ====================

@app.get("/api/discover", response_model=dict)
def get_discover_notes(
    page: int = 1,
    page_size: int = 20,
    session: Session = Depends(get_session)
):
    """
    获取发现广场列表接口（公开文章）
    
    功能说明：
    获取所有公开的笔记，按发布时间倒序排列
    
    参数：
    - page: 页码
    - page_size: 每页记录数
    - session: 数据库会话
    
    返回：
    - 公开笔记列表和分页信息
    """
    offset = (page - 1) * page_size
    
    # 查询所有公开的笔记，按发布时间倒序
    statement = select(Note).where(Note.status == "public").where(Note.published_at.isnot(None))
    total_statement = select(Note).where(Note.status == "public").where(Note.published_at.isnot(None))
    
    # 执行分页查询
    notes = session.exec(
        statement.order_by(Note.published_at.desc()).offset(offset).limit(page_size)
    ).all()
    total_notes = session.exec(total_statement).all()
    total = len(total_notes)
    
    # 转换为字典格式
    notes_list = []
    for note in notes:
        # 获取作者信息
        author = session.get(User, note.user_id)
        
        # 提取内容预览（前50字符）
        content_preview = note.content[:50] if note.content else ""
        content_preview = re.sub(r'<[^>]+>', '', content_preview)
        
        # 获取统计数据（喜爱数、收藏数、评论数）
        like_count = len(session.exec(select(Like).where(Like.note_id == note.id)).all())
        favorite_count = len(session.exec(select(Favorite).where(Favorite.note_id == note.id)).all())
        comment_count = len(session.exec(select(Comment).where(Comment.note_id == note.id)).all())
        
        notes_list.append({
            "id": str(note.id),
            "title": note.title,
            "content_preview": content_preview,
            "author": {
                "id": str(author.id) if author else "",
                "nickname": author.nickname if author and author.nickname else (author.username if author else ""),
                "avatar": author.avatar if author else None,
            },
            "published_at": note.published_at.isoformat() if note.published_at else "",
            "created_at": note.created_at.isoformat() if note.created_at else "",
            "like_count": like_count,
            "favorite_count": favorite_count,
            "comment_count": comment_count,
        })
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "list": notes_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


@app.get("/api/discover/{note_id}", response_model=dict)
def get_public_note_by_id(
    note_id: int,
    session: Session = Depends(get_session)
):
    """
    获取公开笔记详情接口（只读）
    
    功能说明：
    根据笔记ID获取公开笔记详情，任何人都可以访问
    
    参数：
    - note_id: 笔记ID
    - session: 数据库会话
    
    返回：
    - 笔记详情
    
    注意：
    - 只能获取状态为"public"的笔记
    """
    note = session.get(Note, note_id)
    
    if not note or note.status != "public":
        raise HTTPException(status_code=404, detail="笔记不存在或未公开")
    
    # 获取作者信息
    author = session.get(User, note.user_id)
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": str(note.id),
            "user_id": str(note.user_id),
            "title": note.title,
            "content": note.content,
            "status": note.status,
            "published_at": note.published_at.isoformat() if note.published_at else None,
            "created_at": note.created_at.isoformat() if note.created_at else "",
            "updated_at": note.updated_at.isoformat() if note.updated_at else "",
            "author": {
                "id": str(author.id) if author else "",
                "nickname": author.nickname if author and author.nickname else (author.username if author else ""),
                "avatar": author.avatar if author else None,
            } if author else None
        }
    }


@app.get("/api/users/{user_id}/notes", response_model=dict)
def get_user_public_notes(
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    session: Session = Depends(get_session)
):
    """
    获取用户公开文章列表接口
    
    功能说明：
    获取指定用户的所有公开文章
    
    参数：
    - user_id: 用户ID
    - page: 页码
    - page_size: 每页记录数
    - session: 数据库会话
    
    返回：
    - 公开文章列表和分页信息
    """
    offset = (page - 1) * page_size
    
    # 查询指定用户的公开笔记
    statement = select(Note).where(Note.user_id == user_id).where(Note.status == "public")
    total_statement = select(Note).where(Note.user_id == user_id).where(Note.status == "public")
    
    # 执行分页查询
    notes = session.exec(
        statement.order_by(Note.published_at.desc()).offset(offset).limit(page_size)
    ).all()
    total_notes = session.exec(total_statement).all()
    total = len(total_notes)
    
    # 转换为字典格式
    notes_list = []
    for note in notes:
        # 获取作者信息
        author = session.get(User, note.user_id)
        
        # 提取内容预览
        content_preview = note.content[:50] if note.content else ""
        import re
        content_preview = re.sub(r'<[^>]+>', '', content_preview)
        
        notes_list.append({
            "id": str(note.id),
            "title": note.title,
            "content_preview": content_preview,
            "author": {
                "id": str(author.id) if author else "",
                "nickname": author.nickname if author and author.nickname else (author.username if author else ""),
                "avatar": author.avatar if author else None,
            },
            "published_at": note.published_at.isoformat() if note.published_at else "",
            "created_at": note.created_at.isoformat() if note.created_at else "",
        })
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "list": notes_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


# ==================== 喜爱（点赞）相关接口 ====================

@app.post("/api/notes/{note_id}/like", response_model=dict)
def toggle_like(
    note_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    点赞/取消点赞接口
    
    功能说明：
    如果用户已点赞，则取消点赞；如果未点赞，则点赞
    
    参数：
    - note_id: 笔记ID
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 操作结果和当前点赞状态
    """
    # 检查笔记是否存在
    note = session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    # 检查是否已点赞
    existing_like = session.exec(
        select(Like).where(Like.user_id == current_user.id).where(Like.note_id == note_id)
    ).first()
    
    if existing_like:
        # 已点赞，取消点赞
        session.delete(existing_like)
        session.commit()
        is_liked = False
        action = "取消点赞"
    else:
        # 未点赞，添加点赞
        new_like = Like(user_id=current_user.id, note_id=note_id)
        session.add(new_like)
        session.commit()
        is_liked = True
        action = "点赞成功"
    
    # 获取点赞总数
    like_count = session.exec(
        select(Like).where(Like.note_id == note_id)
    ).all()
    like_count = len(like_count)
    
    return {
        "code": 200,
        "message": action,
        "data": {
            "is_liked": is_liked,
            "like_count": like_count
        }
    }


@app.get("/api/notes/{note_id}/likes", response_model=dict)
def get_like_count(
    note_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: Session = Depends(get_session)
):
    """
    获取笔记点赞数和当前用户点赞状态
    
    参数：
    - note_id: 笔记ID
    - current_user: 当前用户（可选，未登录时返回False）
    - session: 数据库会话
    
    返回：
    - 点赞数和当前用户是否已点赞
    """
    # 检查笔记是否存在
    note = session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    # 获取点赞总数
    likes = session.exec(
        select(Like).where(Like.note_id == note_id)
    ).all()
    like_count = len(likes)
    
    # 检查当前用户是否已点赞
    is_liked = False
    if current_user:
        existing_like = session.exec(
            select(Like).where(Like.user_id == current_user.id).where(Like.note_id == note_id)
        ).first()
        is_liked = existing_like is not None
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "like_count": like_count,
            "is_liked": is_liked
        }
    }


# ==================== 收藏相关接口 ====================

@app.post("/api/notes/{note_id}/favorite", response_model=dict)
def toggle_favorite(
    note_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    收藏/取消收藏接口
    
    功能说明：
    如果用户已收藏，则取消收藏；如果未收藏，则收藏
    
    参数：
    - note_id: 笔记ID
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 操作结果和当前收藏状态
    """
    # 检查笔记是否存在
    note = session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    # 检查是否已收藏
    existing_favorite = session.exec(
        select(Favorite).where(Favorite.user_id == current_user.id).where(Favorite.note_id == note_id)
    ).first()
    
    if existing_favorite:
        # 已收藏，取消收藏
        session.delete(existing_favorite)
        session.commit()
        is_favorited = False
        action = "取消收藏"
    else:
        # 未收藏，添加收藏
        new_favorite = Favorite(user_id=current_user.id, note_id=note_id)
        session.add(new_favorite)
        session.commit()
        is_favorited = True
        action = "收藏成功"
    
    # 获取收藏总数
    favorites = session.exec(
        select(Favorite).where(Favorite.note_id == note_id)
    ).all()
    favorite_count = len(favorites)
    
    return {
        "code": 200,
        "message": action,
        "data": {
            "is_favorited": is_favorited,
            "favorite_count": favorite_count
        }
    }


@app.get("/api/notes/{note_id}/favorites", response_model=dict)
def get_favorite_count(
    note_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: Session = Depends(get_session)
):
    """
    获取笔记收藏数和当前用户收藏状态
    
    参数：
    - note_id: 笔记ID
    - current_user: 当前用户（可选，未登录时返回False）
    - session: 数据库会话
    
    返回：
    - 收藏数和当前用户是否已收藏
    """
    # 检查笔记是否存在
    note = session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    # 获取收藏总数
    favorites = session.exec(
        select(Favorite).where(Favorite.note_id == note_id)
    ).all()
    favorite_count = len(favorites)
    
    # 检查当前用户是否已收藏
    is_favorited = False
    if current_user:
        existing_favorite = session.exec(
            select(Favorite).where(Favorite.user_id == current_user.id).where(Favorite.note_id == note_id)
        ).first()
        is_favorited = existing_favorite is not None
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "favorite_count": favorite_count,
            "is_favorited": is_favorited
        }
    }


@app.get("/api/user/favorites", response_model=dict)
def get_user_favorites(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    获取当前用户的收藏列表
    
    参数：
    - page: 页码
    - page_size: 每页记录数
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 收藏的笔记列表和分页信息
    """
    offset = (page - 1) * page_size
    
    # 查询当前用户的收藏
    statement = select(Favorite).where(Favorite.user_id == current_user.id)
    total_statement = select(Favorite).where(Favorite.user_id == current_user.id)
    
    # 执行分页查询，按收藏时间倒序
    favorites = session.exec(
        statement.order_by(Favorite.created_at.desc()).offset(offset).limit(page_size)
    ).all()
    total_favorites = session.exec(total_statement).all()
    total = len(total_favorites)
    
    # 转换为字典格式
    favorites_list = []
    for favorite in favorites:
        # 获取笔记信息
        note = session.get(Note, favorite.note_id)
        if not note:
            continue
        
        # 获取作者信息
        author = session.get(User, note.user_id)
        
        # 提取内容预览
        content_preview = note.content[:50] if note.content else ""
        content_preview = re.sub(r'<[^>]+>', '', content_preview)
        
        favorites_list.append({
            "id": str(note.id),
            "title": note.title,
            "content_preview": content_preview,
            "author": {
                "id": str(author.id) if author else "",
                "nickname": author.nickname if author and author.nickname else (author.username if author else ""),
                "avatar": author.avatar if author else None,
            },
            "published_at": note.published_at.isoformat() if note.published_at else "",
            "created_at": note.created_at.isoformat() if note.created_at else "",
            "favorited_at": favorite.created_at.isoformat() if favorite.created_at else "",
        })
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "list": favorites_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


# ==================== 评论相关接口 ====================

class CommentCreate(BaseModel):
    """创建评论请求模型"""
    content: str
    parent_id: Optional[int] = None  # 父评论ID，用于回复


@app.post("/api/notes/{note_id}/comments", response_model=dict)
def create_comment(
    note_id: int,
    data: CommentCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    创建评论接口
    
    功能说明：
    创建一条新评论，如果是回复则指定parent_id
    
    参数：
    - note_id: 笔记ID
    - data: 评论内容（content）和父评论ID（parent_id，可选）
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 创建的评论信息
    """
    # 检查笔记是否存在
    note = session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    # 如果指定了parent_id，检查父评论是否存在
    if data.parent_id:
        parent_comment = session.get(Comment, data.parent_id)
        if not parent_comment or parent_comment.note_id != note_id:
            raise HTTPException(status_code=400, detail="父评论不存在或不属于该笔记")
    
    # 创建评论
    new_comment = Comment(
        user_id=current_user.id,
        note_id=note_id,
        parent_id=data.parent_id,
        content=data.content
    )
    session.add(new_comment)
    session.commit()
    session.refresh(new_comment)
    
    # 获取作者信息
    author = session.get(User, current_user.id)
    
    return {
        "code": 200,
        "message": "评论成功",
        "data": {
            "id": str(new_comment.id),
            "user_id": str(new_comment.user_id),
            "note_id": str(new_comment.note_id),
            "parent_id": str(new_comment.parent_id) if new_comment.parent_id else None,
            "content": new_comment.content,
            "created_at": new_comment.created_at.isoformat() if new_comment.created_at else "",
            "author": {
                "id": str(author.id) if author else "",
                "nickname": author.nickname if author and author.nickname else (author.username if author else ""),
                "avatar": author.avatar if author else None,
            } if author else None
        }
    }


@app.get("/api/notes/{note_id}/comments", response_model=dict)
def get_comments(
    note_id: int,
    session: Session = Depends(get_session)
):
    """
    获取笔记评论列表接口
    
    功能说明：
    获取某笔记的所有评论，返回树形结构（顶级评论及其回复）
    
    参数：
    - note_id: 笔记ID
    - session: 数据库会话
    
    返回：
    - 评论列表（树形结构）
    """
    # 检查笔记是否存在
    note = session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    # 获取所有评论
    all_comments = session.exec(
        select(Comment).where(Comment.note_id == note_id).order_by(Comment.created_at.asc())
    ).all()
    
    # 构建评论树
    comments_dict = {}
    root_comments = []
    
    # 第一遍：创建所有评论的字典
    for comment in all_comments:
        author = session.get(User, comment.user_id)
        comment_data = {
            "id": str(comment.id),
            "user_id": str(comment.user_id),
            "note_id": str(comment.note_id),
            "parent_id": str(comment.parent_id) if comment.parent_id else None,
            "content": comment.content,
            "created_at": comment.created_at.isoformat() if comment.created_at else "",
            "author": {
                "id": str(author.id) if author else "",
                "nickname": author.nickname if author and author.nickname else (author.username if author else ""),
                "avatar": author.avatar if author else None,
            } if author else None,
            "replies": []  # 子评论列表
        }
        comments_dict[comment.id] = comment_data
    
    # 第二遍：构建树形结构
    for comment in all_comments:
        comment_data = comments_dict[comment.id]
        if comment.parent_id is None:
            # 顶级评论
            root_comments.append(comment_data)
        else:
            # 回复评论，添加到父评论的replies中
            if comment.parent_id in comments_dict:
                comments_dict[comment.parent_id]["replies"].append(comment_data)
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "list": root_comments,
            "total": len(all_comments)
        }
    }


@app.delete("/api/comments/{comment_id}", response_model=dict)
def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    删除评论接口
    
    功能说明：
    删除指定的评论（只能删除自己的评论）
    
    参数：
    - comment_id: 评论ID
    - current_user: 当前登录用户
    - session: 数据库会话
    
    返回：
    - 删除结果
    """
    # 获取评论
    comment = session.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    
    # 检查权限：只能删除自己的评论
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此评论")
    
    # 删除评论（注意：如果有子评论，可能需要级联删除或禁止删除）
    # 这里简单处理：只删除当前评论，子评论保留（parent_id会变成None）
    session.delete(comment)
    session.commit()
    
    return {
        "code": 200,
        "message": "删除成功",
        "data": {}
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
