import os
import random
import string
from BaseClasses import Item, MultiWorld, Region, Location, ItemClassification, CollectionState
from worlds.AutoWorld import World
from .Options import HangmanOptions, HangmanStartHints, Word
from .Items import item_table
from .Locations import get_location_name_to_id, get_location_table
from .Regions import get_region_table
from typing import Any, Dict, Optional, Callable
from worlds.LauncherComponents import Component, components, Type, launch_subprocess

def launch_client():
    from .Client import launch
    launch_subprocess(launch, name="HangmanClient")


components.append(Component(
    "Hangman Client",
    "HangmanClient",
    func=launch_client,
    component_type=Type.CLIENT
))

class HangmanWorld(World):
    """
    AP Hangman
    """

    word = None

    game = "Hangman"
    item_name_to_id = {name: data.id for name, data in item_table.items()}
    location_name_to_id = get_location_name_to_id()
    topology_present = False
    hidden = False
    options_dataclass = HangmanOptions
    options: HangmanOptions

    def set_rules(self):
        self.multiworld.completion_condition[self.player] =\
            lambda state: state.has_all(self.get_word(), self.player)

    def create_item(self, name: str) -> Item:
        item_data = item_table[name]
        return Item(name, item_data.classification, item_data.index, self.player)

    def create_items(self):
        item_pool = []
        for (name, data) in item_table.items():
            for i in range(data.count):
                item_pool.append(HangmanItem(
                    name,
                    data.classification,
                    data.id,
                    self.player
                ))

        self.multiworld.itempool += item_pool

    def create_regions(self):
        # Create the menu region
        menu_region = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions += [menu_region]

        # Now add the Hangman regions
        for (region, data) in get_region_table(self.player).items():
            self.multiworld.regions += [create_region(self.multiworld, self.player, region, list(self.get_word()))]

        # Connect Menu to Word
        menu_region.connect(self.multiworld.get_region("Word", self.player))

    def fill_slot_data(self) -> Dict[str, Any]:
        self.options.start_hints = HangmanStartHints(list(string.ascii_uppercase))
        return {
            "word": self.get_word()
        }

    def generate_early(self):
        self.options.non_local_items.value = set(item_table.keys())
        return

    def post_fill(self):
        return

    # Get the secret word
    def get_word(self):
        if not self.word:
            if len(self.options.word.value) > 0:
                # A specific word was set in the YAML options
                self.word = self.options.word.value
            else:
                # Pick a random word and add it to the options (so it shows up in the spoiler log)
                self.word = get_random_word()
                self.options.word = Word(self.word)

        return self.word

def create_region(world: MultiWorld, player: int, region_name: str, word: str):
    region = Region(region_name, player, world)
    # Add locations
    for (location_name, location_data) in get_location_table(player, word).items():
        # TODO: Group locations by region
        if location_data.region == region_name:
            location = HangmanLocation(player, location_name, location_data.id, region)
            region.locations.append(location)

            # Add an access rule for the location
            if location_data.rule:
                location.access_rule = location_data.rule

            # Handle "event" checks by adding a fixed item
            if location_data.event_name:
                location.place_locked_item(HangmanItem(
                    location_data.event_name,
                    ItemClassification.progression,
                    None,
                    player
                ))
    return region

def connect_regions(world: MultiWorld, player: int):
    for (region_name, region_data) in get_region_table(player).items():
        for exit in region_data.exits:
            connect(world, player, region_name, exit.destination, exit.rule)

# Connect two regions
def connect(world: MultiWorld, player: int, source: str, target: str, rule: Optional[Callable[[CollectionState], bool]] = None):
    sourceRegion = world.get_region(source, player)
    targetRegion = world.get_region(target, player)
    sourceRegion.connect(targetRegion, rule=rule)

# source: https://github.com/taikuukaits/SimpleWordlists/blob/master/Thesaurus-Synonyms-Common.txt
min_word_length = 6
def get_random_word():
    script_dir = os.path.dirname(__file__)
    rel_path = "data/words.txt"
    abs_file_path = os.path.join(script_dir, rel_path)
    with open(abs_file_path, "r") as file:
        words = [line.strip() for line in file]
    words = list(filter(lambda word: len(word) > min_word_length, words))
    return random.choice(words)

class HangmanItem(Item):
    game: str = "Hangman"

class HangmanLocation(Location):
    game: str = "Hangman"