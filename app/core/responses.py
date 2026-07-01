from typing import Any


def success_response(data: Any = None, message: str = "Success") -> dict[str, Any]:
    return {
        "data": data,
        "message": message,
    }
