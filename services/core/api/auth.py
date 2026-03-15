from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.core.database import get_db
from services.core.models import User
from services.core.security import get_password_hash, verify_password, create_access_token
from shared.schemas.auth import UserCreate, UserResponse, Token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    API Đăng ký người dùng mới.
    Nhận vào: username, email, password (mật khẩu gốc)
    Trả về: Thông tin user (đã ẩn password)
    """
    # BƯỚC 1: Kiểm tra username/email đã tồn tại chưa
    query = select(User).where((User.username == user_in.username) | (User.email == user_in.email))
    result = await db.execute(query)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username hoặc Email đã tồn tại")

    # BƯỚC 2: Băm mật khẩu
    hashed_pw = get_password_hash(user_in.password)

    # BƯỚC 3: Tạo object User mới để lưu vào DB
    new_user = User(username=user_in.username, email=user_in.email, password_hash=hashed_pw)

    # BƯỚC 4: Lưu vào DB
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # BƯỚC 5: Trả về dữ liệu User (Pydantic tự chuyển đổi từ ORM object)
    return new_user


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
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
