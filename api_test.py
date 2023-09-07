import requests
import time
import numpy as np
import argparse
from tqdm import tqdm


def measure_api_performance(api_url, num_requests=100, interval=0.1):
    # List to store response times
    response_times = []

    # List to accumulate error messages
    errors = []

    # Using tqdm to display a progress bar
    for _ in tqdm(range(num_requests), desc="Testing API", position=0, leave=True):
        # Record start time
        start_time = time.time()

        # Make the request
        response = requests.get(api_url)
        if response.status_code != 200:
            errors.append(f"Request #{_ + 1} failed with status code {response.status_code}")
            continue

        # Record end time
        end_time = time.time()

        # Calculate response time and add to list
        response_times.append(end_time - start_time)

        # Sleep for the interval (if set)
        if interval:
            time.sleep(interval)

    # Print accumulated error messages after progress bar is complete
    for error in errors:
        print(error)

    # Calculate statistics
    min_time = min(response_times)
    max_time = max(response_times)
    avg_time = np.mean(response_times)
    std_dev = np.std(response_times)

    return min_time, max_time, avg_time, std_dev


def main():
    parser = argparse.ArgumentParser(description="Measure API performance")
    parser.add_argument("api_url", type=str, help="API URL to be tested")
    parser.add_argument("--num_requests", type=int, default=100, help="Number of requests to make. Default is 100.")
    parser.add_argument(
        "--interval", type=float, default=0.1, help="Interval between requests in seconds. Default is 0.1 seconds."
    )

    args = parser.parse_args()

    min_time, max_time, avg_time, std_dev = measure_api_performance(args.api_url, args.num_requests, args.interval)
    print(f"\nMinimum Time: {min_time}")
    print(f"Maximum Time: {max_time}")
    print(f"Average Time: {avg_time}")
    print(f"Standard Deviation: {std_dev}")


if __name__ == "__main__":
    main()
