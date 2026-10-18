import os
import uvicorn

if __name__ == "__main__":
    os.environ["PUBLIC_DEMO"] = "1"
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, log_level="info")
