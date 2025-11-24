# 图片积木后端API

## 项目说明
这是图片积木项目的后端服务，使用 FastAPI 框架开发。

## 环境要求
- Python 3.8+
- pip

## 安装步骤

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动服务
```bash
python main.py
```

或者使用 uvicorn 直接启动：
```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### 3. 访问API文档
启动后访问：http://localhost:8080/docs

## API接口说明

### 认证相关
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/user` - 获取当前用户信息
- `POST /api/auth/logout` - 退出登录

### 作品相关
- `GET /api/works` - 获取作品列表
- `GET /api/works/{id}` - 获取作品详情
- `POST /api/works` - 创建作品
- `PUT /api/works/{id}` - 更新作品
- `DELETE /api/works/{id}` - 删除作品

### 消费相关
- `GET /api/consumption/history` - 获取消费历史
- `GET /api/consumption/stats` - 获取消费统计

## 数据库
使用 SQLite 数据库，数据文件为 `test.db`

## 注意事项
1. 生产环境请修改 `auth.py` 中的 `SECRET_KEY`
2. 密码目前是明文存储，生产环境请使用密码加密（如 bcrypt）
3. CORS 已配置允许 `http://localhost:3000` 访问

