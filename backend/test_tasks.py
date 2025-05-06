from celery.scheduler.tasks import sample_hourly_task, sample_daily_task, sample_minute_task

if __name__ == "__main__":
    print("Running hourly task manually...")
    result = sample_hourly_task.delay()
    print(f"Hourly task started with ID: {result.id}")

    print("\nRunning daily task manually...")
    result = sample_daily_task.delay()
    print(f"Daily task started with ID: {result.id}")

    print("\nRunning minute task manually...")
    result = sample_minute_task.delay()
    print(f"Minute task started with ID: {result.id}")

    print("\nCheck Flower dashboard at http://localhost:5555 to see the tasks running")
