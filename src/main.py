import uvicorn

from src.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("src.api.app:app", host=settings.API_HOST, port=settings.API_PORT, reload=False)


if __name__ == "__main__":
    main()
