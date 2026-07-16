import sys
import numpy as np
import matplotlib.pyplot as plt
from math import log10, floor

def read_valid_lines(file_names):
    """
    Read valid lines from multiple files
    :param file_names: List of file names
    :return: List of valid line data, each file corresponds to a sublist
    """
    data = [[] for _ in file_names]  # Initialize data storage lists

    # Open all files
    files = [open(file_name, 'r') for file_name in file_names]

    # Read line by line
    for lines in zip(*files):
        try:
            # Try to convert true value to float
            true_value = float(lines[0].strip())
        except ValueError:
            print(f"Warning: Invalid line in true value file '{lines[0].strip()}', skipping")
            continue

        # If true value is valid, process data from other files
        for i, line in enumerate(lines):
            try:
                data[i].append(float(line.strip()))
            except ValueError:
                print(f"Warning: Invalid line in file '{file_names[i]}' '{line.strip()}', skipping")
                continue

    # Close all files
    for file in files:
        file.close()

    return data

def calculate_relative_errors(true_values, data_values):
    """
    Calculate relative errors
    :param true_values: List of true values
    :param data_values: List of data from other files
    :return: List of relative errors
    """
    relative_errors = []
    for true, data in zip(true_values, data_values):
        if true == 0:
            print("Warning: True value is 0, cannot compute relative error, skipping")
            continue
        relative_errors.append(data / true)
    return relative_errors

def generate_bins(relative_errors):
    """
    Automatically generate bin boundaries
    :param relative_errors: List of relative errors
    :return: List of bin boundaries
    """
    if not relative_errors:
        return [0.1, 1, 10, 100]  # Default bins

    # Find the log values of min and max relative errors
    min_error = min(relative_errors)
    max_error = max(relative_errors)

    # Calculate min and max order of magnitude
    min_magnitude = floor(log10(min_error)) if min_error > 0 else -1
    max_magnitude = floor(log10(max_error)) if max_error > 0 else 1

    # Generate bin boundaries
    bins = [10 ** i for i in range(min_magnitude, max_magnitude + 2)]
    return bins

def plot_histogram(relative_errors, file_name):
    print('plotting')
    """
    Plot histogram
    :param relative_errors: List of relative errors
    :param file_name: Output filename for saving the image
    """
    # Automatically generate bin boundaries
    bins = generate_bins(relative_errors)
    print('plotting2')

    # Plot histogram
    counts, bin_edges, _ = plt.hist(relative_errors, bins=bins, edgecolor='black', alpha=0.7)

    # Generate bin labels (exponential notation)
    bin_labels = [f'$10^{{{int(log10(bin_edges[i]))}}}$ to $10^{{{int(log10(bin_edges[i+1]))}}}$'
                  for i in range(len(bin_edges) - 1)]

    # Add legend
    plt.legend(handles=[plt.Rectangle((0, 0), 1, 1, fc='blue', alpha=0.7)],
               labels=[f'{label}: {count}' for label, count in zip(bin_labels, counts)],
               loc='upper right')

    # Set x-axis to log scale
    plt.xscale('log')
    plt.xlabel('Relative Error Magnitude')
    plt.ylabel('Count')
    plt.title(f'Relative Error Histogram ({file_name})')
    plt.grid(True, which="both", ls="--", linewidth=0.5)

    # Save image
    plt.savefig(f'{file_name}_histogram.png')
    plt.close()

def main(file_names):
    """
    Main function
    :param file_names: List of input file names
    """
    # Read valid lines from all files
    data = read_valid_lines(file_names)
    true_values = data[0]  # The first file contains true values

    # Process other files
    for i, file_name in enumerate(file_names[1:]):
        data_values = data[i + 1]

        # Calculate relative errors
        relative_errors = calculate_relative_errors(true_values, data_values)

        # Plot and save histogram
        plot_histogram(relative_errors, file_name)
        print(f"Histogram saved as {file_name}_histogram.png")

if __name__ == "__main__":
    # Check input arguments
    if len(sys.argv) < 3:
        print("Usage: python script.py <true_value_file> <other_file1> <other_file2> ...")
        sys.exit(1)

    # Get file name list
    file_names = sys.argv[1:]

    # Call main function
    main(file_names)