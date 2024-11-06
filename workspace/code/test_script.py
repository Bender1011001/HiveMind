# Test script to verify code execution
import os
from datetime import datetime

def main():
    # Basic calculations
    numbers = [1, 2, 3, 4, 5]
    sum_result = sum(numbers)
    avg_result = sum_result / len(numbers)
    
    # Get current time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create output
    output = f"""
Code Execution Test Results:
---------------------------
Time of execution: {current_time}
Test calculations:
- Sum of numbers {numbers}: {sum_result}
- Average: {avg_result}
- Python version: {os.sys.version}
"""
    print(output)

if __name__ == "__main__":
    main()
