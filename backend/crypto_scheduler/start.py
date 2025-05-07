import subprocess
import sys
import time
import os
from pathlib import Path

def run_command(command, name):
    try:
        # Set environment variables for Celery
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path(__file__).parent.parent)  # Add backend to Python path

        process = subprocess.Popen(
            command,
            shell=True,
            env=env
        )
        print(f"✅ {name} started with PID: {process.pid}")
        return process
    except Exception as e:
        print(f"❌ Error starting {name}: {e}")
        return None

def main():
    # Change to the backend directory
    backend_dir = Path(__file__).parent.parent
    os.chdir(backend_dir)

    print("🚀 Starting Crypto Trading Scheduler")
    print("-" * 50)

    # Start Celery worker with solo pool for Windows compatibility
    worker = run_command(
        "python -m celery -A crypto_scheduler.app:app worker --pool=solo --loglevel=info",
        "Celery Worker"
    )

    # Wait for worker to initialize
    time.sleep(2)

    # Start Celery beat
    beat = run_command(
        "python -m celery -A crypto_scheduler.app:app beat --loglevel=info",
        "Celery Beat"
    )

    # Start Flower monitoring
    flower = run_command(
        "python -m celery -A crypto_scheduler.app:app flower --port=5555",
        "Flower Monitor"
    )

    print("\n📋 Services:")
    print("- Worker: Processing tasks")
    print("- Beat: Scheduling tasks")
    print("- Flower: http://localhost:5555")
    print("\n⌛ Waiting for tasks to run...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
        for process in [worker, beat, flower]:
            if process:
                process.terminate()
                process.wait()
        print("✅ All services stopped")

if __name__ == "__main__":
    main()
