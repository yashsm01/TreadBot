from crypto_scheduler.app import app
from crypto_scheduler.scheduler.tasks import market_check, portfolio_update, strategy_update
import time
from datetime import datetime

def wait_for_task(result, task_name, timeout=30):
    """Wait for task result with timeout"""
    start_time = time.time()
    while not result.ready():
        if time.time() - start_time > timeout:
            print(f"⚠️ {task_name} task timed out after {timeout} seconds")
            return None
        print(f"Waiting for {task_name} result...")
        time.sleep(1)
    return result.get()

def run_all_tasks():
    print("🚀 Starting tasks manually...")
    print("-" * 50)

    # Run market check
    print("\n📊 Running market check task...")
    result = market_check.delay()
    print(f"Task ID: {result.id}")
    market_result = wait_for_task(result, "market check")
    if market_result is not None:
        print(f"Market check result: {market_result}")

    # Run portfolio update
    print("\n💼 Running portfolio update task...")
    result = portfolio_update.delay()
    print(f"Task ID: {result.id}")
    portfolio_result = wait_for_task(result, "portfolio update")
    if portfolio_result is not None:
        print(f"Portfolio update result: {portfolio_result}")

    # Run strategy update
    print("\n⚙️ Running strategy update task...")
    result = strategy_update.delay()
    print(f"Task ID: {result.id}")
    strategy_result = wait_for_task(result, "strategy update")
    if strategy_result is not None:
        print(f"Strategy update result: {strategy_result}")

def run_specific_task(task_name):
    tasks = {
        'market': market_check,
        'portfolio': portfolio_update,
        'strategy': strategy_update
    }

    if task_name not in tasks:
        print(f"❌ Unknown task: {task_name}")
        print(f"Available tasks: {', '.join(tasks.keys())}")
        return

    task = tasks[task_name]
    print(f"\n🚀 Running {task_name} task...")
    result = task.delay()
    print(f"Task ID: {result.id}")
    task_result = wait_for_task(result, task_name)
    if task_result is not None:
        print(f"Result: {task_result}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Run specific task
        task_name = sys.argv[1].lower()
        run_specific_task(task_name)
    else:
        # Run all tasks
        run_all_tasks()

    print("\n✅ Tasks execution completed!")
