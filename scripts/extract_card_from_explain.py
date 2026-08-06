import re
import sys

def process_data(data):
    # Split data by double newlines
    sections = data.split('\n\n')

    # Regex to match [number] Rows pattern
    pattern = re.compile(r'([\d]+) Rows')

    results = []

    for section in sections:
        # Find the first matching pattern in each section
        match = pattern.search(section)
        if match:
            results.append(match.group(1))

    return results

def main():
    # Check if a filename was provided as argument
    if len(sys.argv) != 2:
        print("Usage: python script.py <filename>")
        sys.exit(1)

    filename = sys.argv[1]

    try:
        # Read data from file
        with open(filename, 'r', encoding='utf-8') as file:
            data = file.read()

        # Process data
        extracted_rows = process_data(data)

        # Output results
        for row in extracted_rows:
            print(row)
    
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()