import time
import concurrent.futures
import pandas as pd
from unittest.mock import patch
from services.auth_service import authenticate_user
from services.data_service import load_filtered_main_data


def simulate_user(user_id):
    """Simulate a user logging in and loading data."""
    start_time = time.time()

    # Mock DB for authentication
    user_data = {
        "username": f"user_{user_id}",
        "password_hash": "mocked_hash",
        "role": "engineer",
        "is_active": 1,
        "must_change_password": 0
    }

    with patch("services.auth_service.db_read", return_value=pd.DataFrame([user_data])):
        with patch("services.auth_service.password_matches", return_value=True):
            success, _, _ = authenticate_user(f"user_{user_id}", "password")

    # Simulate loading main data
    mock_df = pd.DataFrame({"test": range(1000)})
    with patch("services.data_service.read_parquet_fast", return_value=mock_df):
        load_filtered_main_data()

    end_time = time.time()
    return end_time - start_time


def run_load_test(num_users=50):
    print(f"Starting load test with {num_users} concurrent users...")

    durations = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(simulate_user, i) for i in range(num_users)]
        for future in concurrent.futures.as_completed(futures):
            durations.append(future.result())

    avg_duration = sum(durations) / len(durations)
    max_duration = max(durations)
    min_duration = min(durations)

    print(f"Load test completed.")
    print(f"Average response time: {avg_duration:.4f}s")
    print(f"Max response time: {max_duration:.4f}s")
    print(f"Min response time: {min_duration:.4f}s")


if __name__ == "__main__":
    run_load_test()
