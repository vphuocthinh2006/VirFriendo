from datetime import datetime, timedelta
from jose import jwt
import bcrypt
from services.core.config import settings
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl = "/auth/login")
_optional_bearer = HTTPBearer(auto_error=False)
# Hàm 1: Kiểm tra mật khẩu (So sánh pass user nhập vs pass đã băm trong DB)
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

# Hàm 2: Băm mật khẩu (Dùng khi user đăng ký)
def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

# Hàm 3: Tạo JWT Token
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """Giải mã JWT token và trả về user_id (str)"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token không hợp lệ")
        return user_id
    except Exception:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")


async def get_optional_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
) -> str | None:
    """Bearer JWT optional — returns user id or None."""
    if creds is None or not creds.credentials:
        return None
    try:
        payload = jwt.decode(creds.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub")
        return str(sub) if sub else None
    except Exception:
        return None
