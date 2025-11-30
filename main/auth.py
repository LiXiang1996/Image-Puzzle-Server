"""
JWT认证工具模块
这个文件提供了JWT（JSON Web Token）认证相关的功能

主要功能：
1. 生成JWT token（登录时使用）
2. 验证JWT token（保护需要登录的接口）
3. 从token中获取当前用户信息

JWT工作原理：
1. 用户登录成功后，服务器生成一个token
2. token中包含用户ID等信息（加密）
3. 前端保存token，每次请求时在请求头中携带
4. 服务器验证token，确认用户身份

@author: lixiang
@date: 2025-11-20
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from db.database import get_session
from db.models import User

# ==================== JWT配置 ====================

# JWT密钥（用于签名和验证token）
# 注意：生产环境必须修改为随机生成的强密钥！
# 如果密钥泄露，任何人都可以伪造token
SECRET_KEY = "your-secret-key-change-in-production"

# JWT算法（HS256是常用的对称加密算法）
ALGORITHM = "HS256"

# Token过期时间（分钟）
# 30 * 24 * 60 = 43200分钟 = 30天
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60

# HTTPBearer：用于从请求头中提取Bearer token
# Bearer是HTTP认证方案的一种，格式：Authorization: Bearer <token>
security = HTTPBearer()


# ==================== Token生成和验证 ====================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None)->str:
    """
    创建JWT访问令牌
    
    功能说明：
    根据用户数据生成JWT token
    
    参数：
    - data: 要编码到token中的数据（通常是用户ID）
    - expires_delta: 自定义过期时间（可选）
    
    返回：
    - JWT token字符串
    
    示例：
    token = create_access_token(data={"sub": 1})  # 为用户ID为1的用户生成token
    
    工作原理：
    1. 复制data字典
    2. 添加过期时间（exp字段）
    3. 使用密钥签名生成token
    """
    # 复制数据字典（避免修改原始数据）
    to_encode = data.copy()
    
    # 设置过期时间
    if expires_delta:
        # 如果提供了自定义过期时间，使用它
        expire = datetime.utcnow() + expires_delta
    else:
        # 否则使用默认的过期时间（30天）
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 添加过期时间到数据中
    # exp是JWT标准字段，表示过期时间（Unix时间戳）
    to_encode.update({"exp": expire})
    
    # 使用密钥和算法编码生成token
    # jwt.encode(): 将数据编码为JWT token字符串
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    验证JWT token
    
    功能说明：
    验证token是否有效（未过期、签名正确）
    
    参数：
    - token: JWT token字符串
    
    返回：
    - 如果token有效，返回解码后的数据（字典）
    - 如果token无效（过期、签名错误等），返回None
    
    示例：
    payload = verify_token("eyJhbGci...")
    if payload:
        user_id = payload.get("sub")  # 获取用户ID
    """
    try:
        # 解码并验证token
        # jwt.decode(): 
        # - 验证签名是否正确
        # - 验证是否过期
        # - 如果都通过，返回解码后的数据
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"Token验证成功: user_id={payload.get('sub')}")
        return payload
    except JWTError as e:
        # token无效（过期、签名错误等）
        # 返回None表示验证失败
        print(f"Token验证失败: {type(e).__name__}: {str(e)}")
        return None


# ==================== 用户认证依赖 ====================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
) -> User:
    """
    获取当前登录用户（依赖注入函数）
    
    功能说明：
    这是一个FastAPI依赖函数，用于保护需要登录的接口
    它会自动从请求头中提取token，验证token，并返回用户对象
    
    使用方式：
    在需要登录的接口函数中添加参数：
    def my_api(current_user: User = Depends(get_current_user)):
        # current_user就是当前登录的用户对象
        pass
    
    工作流程：
    1. 从请求头中提取Bearer token（security自动完成）
    2. 验证token是否有效（verify_token）
    3. 从token中获取用户ID
    4. 从数据库中查询用户
    5. 返回用户对象
    
    如果任何一步失败，抛出401未授权错误
    
    参数：
    - credentials: HTTP认证凭证（包含token），由security自动提取
    - session: 数据库会话，用于查询用户
    
    返回：
    - User对象（当前登录的用户）
    
    异常：
    - 如果token无效或用户不存在，抛出HTTPException(401)
    """
    try:
        # 从credentials中提取token字符串
        # credentials.credentials就是请求头中的token值
        token = credentials.credentials
        
        # 验证token
        payload = verify_token(token)
        
        # 如果token无效（过期、签名错误等）
        if payload is None:
            print(f"Token验证失败: token={token[:20]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,  # 401未授权
                detail="Invalid authentication credentials",  # 错误详情
                headers={"WWW-Authenticate": "Bearer"},  # 告诉客户端使用Bearer认证
            )
        
        # 从payload中获取用户ID
        # "sub"是JWT标准字段，表示subject（主题/用户ID）
        # 我们在create_access_token时设置的就是用户ID（字符串格式）
        user_id_str = payload.get("sub")
        
        # 如果payload中没有用户ID
        if user_id_str is None:
            print(f"Token中缺少用户ID: payload={payload}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 将字符串转换为整数（数据库中的ID是整数类型）
        try:
            user_id: int = int(user_id_str)
        except (ValueError, TypeError):
            print(f"无效的用户ID格式: {user_id_str}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 从数据库中查询用户
        # session.get(): 根据主键查询（User是模型类，user_id是主键值）
        user = session.get(User, user_id)
        
        # 如果用户不存在（可能用户已被删除或数据库被重置）
        if user is None:
            print(f"用户不存在: user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 返回用户对象
        return user
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 其他异常记录日志并返回401
        print(f"认证错误: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    session: Session = Depends(get_session)
) -> Optional[User]:
    """
    获取当前登录用户（可选版本）
    
    功能说明：
    与get_current_user类似，但如果用户未登录，返回None而不是抛出异常
    用于需要区分登录/未登录状态的接口
    
    使用方式：
    def my_api(current_user: Optional[User] = Depends(get_current_user_optional)):
        if current_user:
            # 用户已登录
        else:
            # 用户未登录
        pass
    
    参数：
    - credentials: HTTP认证凭证（可选），如果未提供则返回None
    - session: 数据库会话
    
    返回：
    - User对象（如果已登录）或None（如果未登录）
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        if payload is None:
            return None
        
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None
        
        try:
            user_id: int = int(user_id_str)
        except (ValueError, TypeError):
            return None
        
        user = session.get(User, user_id)
        return user
    except Exception:
        # 任何错误都返回None（静默失败）
        return None
