import uvicorn


def main() -> None:
    uvicorn.run("finchart_api.main:create_app", factory=True, host="127.0.0.1", port=8000)
