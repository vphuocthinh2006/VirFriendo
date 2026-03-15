from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from services.core.config import settings

# 1. Khởi tạo Engine: Đây là "bộ máy" quản lý kết nối tới DB.
# Chúng ta dùng create_async_engine để chạy async.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG, # Log các câu lệnh SQL ra console nếu đang ở mode DEBUG
    future=True
)

# 2. Tạo Session Factory: Đây là "nhà máy" sản xuất ra các Session.
# Mỗi khi có request, chúng ta sẽ xin 1 Session từ đây.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 3. Base Class: Các Model (bảng) sau này sẽ kế thừa từ class này.
class Base(DeclarativeBase):
    pass

# 4. Dependency: Hàm này sẽ được FastAPI dùng để inject DB session vào các endpoint.
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
