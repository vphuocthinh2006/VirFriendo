from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import os
import re
import secrets
from pydantic import BaseModel, EmailStr

from services.core.database import get_db
from services.core.models import User
from services.core.security import get_password_hash, verify_password, create_access_token
from shared.schemas.auth import UserCreate, UserResponse, Token
from loguru import logger

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _google_client_id() -> str:
    return (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()


def _clean_username(text: str) -> str:
    raw = (text or "").strip().lower()
    cleaned = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
    return cleaned[:40] or "user"


async def _unique_username(db: AsyncSession, base: str) -> str:
    candidate = _clean_username(base)
    idx = 0
    while True:
        probe = candidate if idx == 0 else f"{candidate}_{idx}"
        q = select(User.id).where(User.username == probe).limit(1)
        exists = (await db.execute(q)).scalar_one_or_none()
        if exists is None:
            return probe
        idx += 1


async def _verify_google_id_token(id_token: str) -> dict:
    token = (id_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Missing Google id_token")
    url = "https://oauth2.googleapis.com/tokeninfo"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            resp = await client.get(url, params={"id_token": token})
    except Exception:
        raise HTTPException(status_code=502, detail="Could not verify Google token")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    data = resp.json() if isinstance(resp.json(), dict) else {}
    aud = str(data.get("aud") or "").strip()
    client_id = _google_client_id()
    if client_id and aud != client_id:
        raise HTTPException(status_code=401, detail="Google token client_id mismatch")
    email = str(data.get("email") or "").strip().lower()
    email_verified = str(data.get("email_verified") or "").strip().lower() in ("true", "1")
    sub = str(data.get("sub") or "").strip()
    if not email or not email_verified or not sub:
        raise HTTPException(status_code=401, detail="Google token missing required claims")
    return data

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: Request, user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    API Đăng ký người dùng mới.
    Nhận vào: username, email, password (mật khẩu gốc)
    Trả về: Thông tin user (đã ẩn password)
    """
    # BƯỚC 1: Kiểm tra username/email đã tồn tại chưa
    query = select(User).where((User.username == user_in.username) | (User.email == user_in.email))
    result = await db.execute(query)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username or email already exists")

    # BƯỚC 2: Băm mật khẩu
    hashed_pw = get_password_hash(user_in.password)

    # BƯỚC 3: Tạo object User mới để lưu vào DB
    new_user = User(username=user_in.username, email=user_in.email, password_hash=hashed_pw)

    # BƯỚC 4: Lưu vào DB
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info("auth.register ip={} user_id={} username={}", _client_ip(request), new_user.id, new_user.username)

    # BƯỚC 5: Trả về dữ liệu User (Pydantic tự chuyển đổi từ ORM object)
    return new_user


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    API Đăng nhập (OAuth2 chuẩn - tương thích với Swagger UI).
    Nhận vào: username, password (form data)
    Trả về: JWT Token
    """
    # BƯỚC 1: Tìm user trong DB theo username
    query = select(User).where(User.username == form_data.username)
    result = await db.execute(query)
    user = result.scalars().first()

    # BƯỚC 2: Nếu không tìm thấy hoặc verify_password(..) trả về False, báo lỗi 401
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không đúng",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # BƯỚC 3: Tạo JWT Token
    access_token = create_access_token(data={"sub": str(user.id)})

    # BƯỚC 4: Trả về Token
    return {"access_token": access_token, "token_type": "bearer"}


class GoogleAuthRequest(BaseModel):
    id_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


@router.post("/forgot-password")
async def forgot_password(_body: ForgotPasswordRequest):
    """
    Ghi nhận yêu cầu đặt lại mật khẩu. Gửi email thật có thể bổ sung sau;
    luôn trả cùng một thông báo để tránh lộ email có tồn tại hay không.
    """
    return {
        "message": "If that email is registered, you will receive reset instructions when outbound email is enabled.",
    }


@router.post("/google", response_model=Token)
async def google_auth(request: Request, payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """
    API đăng ký/đăng nhập bằng Google.
    - Nhận id_token từ Google OAuth ở frontend
    - Verify token với Google
    - Nếu email chưa có trong DB: tạo user mới
    - Trả JWT access token để dùng như login thường
    """
    info = await _verify_google_id_token(payload.id_token)
    email = str(info.get("email") or "").strip().lower()
    name = str(info.get("name") or "").strip()

    # Ưu tiên login theo email
    q = select(User).where(User.email == email).limit(1)
    user = (await db.execute(q)).scalars().first()

    if not user:
        base = name or email.split("@")[0] or "google_user"
        username = await _unique_username(db, base)
        # Google account không dùng mật khẩu local, lưu hash ngẫu nhiên để thỏa model nullable=False.
        random_password = secrets.token_urlsafe(24)
        user = User(
            username=username,
            email=email,
            password_hash=get_password_hash(random_password),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(data={"sub": str(user.id)})
    logger.info("auth.google ip={} user_id={} email={}", _client_ip(request), user.id, user.email)
    return {"access_token": access_token, "token_type": "bearer"}
