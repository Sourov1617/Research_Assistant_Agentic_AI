"""Run the FastAPI app locally with Uvicorn.

Usage: python api.py
"""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("src.api.fastapi_app:app", host="0.0.0.0", port=8000, reload=True)
