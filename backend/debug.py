import uvicorn
import debugpy
import os

# Prevent duplicate debugger binding in reload subprocesses
if os.environ.get("RUN_MAIN") == "true" or not os.environ.get("RUN_MAIN"):
    try:
        debugpy.listen(("0.0.0.0", 5678))
        print("🟢 Debugger is listening on port 5678")
    except RuntimeError:
        print("⚠️ Debugger already attached or port is in use")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_delay=0.25,
        log_level="debug"
    )
