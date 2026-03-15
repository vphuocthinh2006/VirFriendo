from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from uuid import UUID

# 1. Base Schema (Chứa các trường dùng chung)
class UserBase(BaseModel):
    username: str
    email: EmailStr

# 2. Schema nhận Data khi User Đăng ký
class UserCreate(UserBase):
    password: str

# 3. Schema nhận Data khi User Đăng nhập
class UserLogin(BaseModel):
    username: str
    password: str

# 4. Schema trả Data ra cho Client (Phải giấu password đi!)
class UserResponse(UserBase):
    id: UUID
    relationship_level: int
    
    # Giúp Pydantic có thể đọc dữ liệu trực tiếp từ SQLAlchemy Model
    model_config = ConfigDict(from_attributes=True)

# 5. Schema cho JWT Token
class Token(BaseModel):
    access_token: str
    token_type: str
