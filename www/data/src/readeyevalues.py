import numpy as np

# Initialize the lists for X and Y values
x_values = []
y_values = []

# Open the file and read the lines
with open('eyevalues.txt', 'r') as file:
    lines = file.readlines()
    # Skip the first line (header)
    for line in lines[1:]:
        values = line.split()  # Split each line into values
        x_values.append(float(values[1]))  # Append the X value
        y_values.append(float(values[2]))  # Append the Y value

# Calculate and print the average standard deviation
x_std_dev = np.std(x_values)
y_std_dev = np.std(y_values)
avg_std_dev = (x_std_dev + y_std_dev) / 2
print(f'Average standard deviation: {avg_std_dev}')
