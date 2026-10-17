import uvicorn

from .config import Settings
from .main import create_app

if __name__ == "__main__":
    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
