# implemented based on Roman_ example, but withouth the use of numpy

import math
import time

def eliminate(r1, r2, col, target=0):
    fac = (r2[col]-target) / r1[col]
    for i in range(len(r2)):
        r2[i] -= fac * r1[i]

def gauss(a):
    for i in range(len(a)):
        if a[i][i] == 0:
            for j in range(i+1, len(a)):
                if a[i][j] != 0:
                    a[i], a[j] = a[j], a[i]
                    break
            else:
                raise ValueError("Matrix is not invertible")
        for j in range(i+1, len(a)):
            eliminate(a[i], a[j], i)
    for i in range(len(a)-1, -1, -1):
        for j in range(i-1, -1, -1):
            eliminate(a[i], a[j], i)
    for i in range(len(a)):
        eliminate(a[i], a[i], i, target=1)
    return a

def inverse(a):
    tmp = [[] for _ in a]
    for i,row in enumerate(a):
        assert len(row) == len(a)
        tmp[i].extend(row + [0]*i + [1] + [0]*(len(a)-i-1))
    gauss(tmp)
    return [tmp[i][len(tmp[i])//2:] for i in range(len(tmp))]

def matrix_multiply(matrix1, matrix2):
    # Determine the dimensions of the matrices
    rows1, cols1 = len(matrix1), len(matrix1[0])
    rows2, cols2 = len(matrix2), 1  # Assuming matrix2 is a column vector

    # Check if the matrices can be multiplied
    if cols1 != rows2:
        raise ValueError("Incompatible matrix dimensions for multiplication")

    # Initialize the result matrix with zeros
    result = [0] * rows1

    # Perform matrix multiplication
    for i in range(rows1):
        for j in range(cols1):
            result[i] += matrix1[i][j] * matrix2[j]

    return result

# angle of the red arrow can be wrong (both visually and in packet)
# this function fixes it
def fix_angle(angle):
    whole_part, decimal_part = str(angle).split(".")

    if len(decimal_part) == 1:
        decimal_part = "0" + decimal_part

    new_number_string = whole_part + "." + decimal_part
    return(float(new_number_string))

def find_walkable_pos(x, y, map_array):
    closest_distance = float('inf')
    closest_coord = None

    #this iterates over the entire array, rework this to just go from the x, y in a "circle"
    for i in range(len(map_array[0])):
        for j in range(len(map_array)):
            if map_array[j][i] == 1:  # if walkable
                distance = abs(i - x) + abs(j - y)
                if distance < closest_distance:
                    closest_distance = distance
                    closest_coord = (i, j)

    return closest_coord

#calculate where to go based on current position an angle to get the second point required for triangulation
def calculate_point_B_position(x, y, angle, map_array, offset = 20):
    plus_y = 0
    plus_x = 0

    if 0 <= angle <= 0.785:
        plus_y = offset
    elif -0.785 <= angle < 0:
        plus_y = -offset
    elif -1.57 <= angle < -0.785:
        plus_x = offset
    elif -2.355 <= angle < -1.57:
        plus_x = -offset
    elif -3.14 <= angle < -2.355:
        plus_y = -offset
    elif 2.355 <= angle <= 3.14:
        plus_y = offset
    elif 1.57 <= angle < 2.355:
        plus_x = -offset
    elif 0.785 <= angle < 1.571:
        plus_x = offset

    new_x = (x + plus_x)
    new_y = (y + plus_y)

    new_x, new_y = find_walkable_pos(new_x, new_y, map_array)
    return(new_x, new_y)

def calculate_field_location(a, b, a_angle, b_angle, map_array = None):
    cur_time = time.time()
    if a_angle == b_angle:
        print("Fail while calculating field loaction, try to use rod in a better place...")
        return None
        #x, y = len(map_array[0])/2, len(map_array)/2
        #if map_array:
        #    x,y = find_walkable_pos(x, y, map_array)
        #return x,y
    a_angle = fix_angle(a_angle)
    b_angle = fix_angle(b_angle)

    params = matrix_multiply(inverse([[math.cos(a_angle), math.cos(b_angle)],[math.sin(a_angle), math.sin(b_angle)]]), [b[0]-a[0], b[1]-a[1]])

    # calculating final position
    x = int(a[0] + params[0] * math.cos(a_angle))
    y = int(a[1] + params[0] * math.sin(a_angle))

    if map_array:
        x,y = find_walkable_pos(x, y, map_array)
    return x,y