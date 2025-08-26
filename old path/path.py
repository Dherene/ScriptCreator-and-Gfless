from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
from pathfinding.core.diagonal_movement import DiagonalMovement
import math
import time
import zipfile

def loadMap(map_id):
    try:
        archive = zipfile.ZipFile("resources\maps.zip", "r")
        data = archive.read(f"maps/{map_id}.bin")
    except Exception as e:
        print(e)
        return []
    
    # very ugly way of adjusting the datasize, but appeared easier than looking for pattern
    if data[1] == 0:
        width = data[0]
        height = int((len(data)-4)/data[0])
    elif data[3] == 0:
        height = data[2]
        width = int((len(data)-4)/data[2])
    elif data[0] == data[2]:
        sqroot = math.sqrt(len(data)-4)
        width,height = int(sqroot), int(sqroot)
    elif data[0] == 19 and data[2] == 14:
        width,height = 275,270
    elif data[0] == 204 and data[2] == 9:
        width,height = 460,265
    elif data[0] == 54 and data[2] == 34:
        width,height = 310,290
    elif data[0] == 54 and data[2] == 44:
        width,height = 310,300
    elif data[0] == 94 and data[2] == 145:
        width,height = 350,401
    elif data[0] == 4 and data[2] == 24:
        width,height = 260,280
    elif data[0] == 16 and data[2] == 10:
        width,height = 272,266
    else:
        print(f"Error while loading map: {map_id}")
        return []

    result = convertToArray(data[4:], width, height)

    return(result)

def convertToArray(data, width, height):
    # Calculate the total number of elements in the data
    total_elements = width * height
    
    # Check if the length of the data is equal to the total number of elements
    if len(data) != total_elements:
        raise ValueError("Invalid data length for the given width and height")

    # Use a list comprehension to create the 2D array
    result_array = [[0 if int(data[i * width + j]) != 0 else 1 for j in range(width)] for i in range(height)]

    return result_array

def findPath(PlayerPos,destination,mapArray):
    cur_time = time.time()
    if mapArray != []:
        grid = Grid(matrix=mapArray)

        start = grid.node(int(PlayerPos[0]), int(PlayerPos[1]))
        end = grid.node(int(destination[0]), int(destination[1]))

        finder = AStarFinder(diagonal_movement=DiagonalMovement.always)
        path, runs = finder.find_path(start, end, grid)

        print(time.time()-cur_time)
        return path
    else:
        return []
    