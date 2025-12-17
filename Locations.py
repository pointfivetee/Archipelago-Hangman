import math
from .Types import LocData
from .Rules import *

starting_id = 1

# e.g., COMPARTMENTALIZATION
max_length = 20
# For a six-letter word (the current minimum), the first letter will have 5 rewards
max_rewards = 5

# Return a name -> ID map for ALL possible locations. Many of these will be impossible in practice,
# but it's easier to build the table this way.
def get_location_name_to_id():
    def create_kv_pair(i):
        id = i + starting_id
        word_pos = i % max_length
        reward_number = math.floor(i / max_length) + 1
        name = "Letter " + str(word_pos + 1) + " Reward " + str(reward_number)
        return (name, id)
    kv_pairs = map(create_kv_pair, range(0, max_length * max_rewards))
    return dict(kv_pairs)
location_name_to_id = get_location_name_to_id()

# Return a name -> LocData table with all the possible locations for a specific word
def get_location_table(player, word):
    def create_kv_pair(i):
        word_pos = i % len(word)
        target_letter = word[word_pos]
        reward_number = math.floor(i / len(word)) + 1
        name = "Letter " + str(word_pos + 1) + " Reward " + str(reward_number)
        rule=lambda state: state.has(target_letter, player)
        id = location_name_to_id[name]
        return (name, LocData(id, region="Word", rule=rule))
    kv_pairs = map(create_kv_pair, range(0, 26))
    return dict(kv_pairs)