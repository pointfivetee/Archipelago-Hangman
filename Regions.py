from .Types import RegionData, ExitData
from .Rules import *

max_keys = 8

# Define regions, their connections, and required checks for those connections
def get_region_table(player):
    return {
        # Word
        "Word": RegionData(),
    }