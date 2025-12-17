import string
from typing import Optional
import asyncio
import time

from CommonClient import (
    CommonContext,
    ClientCommandProcessor,
    get_base_parser,
    logger,
    server_loop,
    gui_enabled,
)
from NetUtils import ClientStatus


class HangmanClientCommandProcessor(ClientCommandProcessor):
    def _cmd_hello_world(self):
        """Say hello!"""
        asyncio.create_task(self.ctx.hello_world())

    def _cmd_status(self):
        """Print out the current status of the game."""
        asyncio.create_task(self.ctx.print_status())

class HangmanContext(CommonContext):
    """Hangman Game Context"""

    command_processor = HangmanClientCommandProcessor

    def __init__(self, server_address: Optional[str], password: Optional[str]) -> None:
        super().__init__(server_address, password)

        self.game = "Hangman"
        self.previous_received = []
        self.items_handling = 0b001 | 0b010 | 0b100  #Receive items from other worlds, starting inv, and own items
        self.location_ids = None
        self.location_name_to_ap_id = None
        self.location_ap_id_to_name = None
        self.item_name_to_ap_id = None
        self.item_ap_id_to_name = None
        self.found_checks = []
        self.missing_checks = []  # Stores all location checks found, for filtering
        self.prev_found = []
        self.seed_name = None
        self.options = None
        self.acquired_keys = []
        self.obtained_items_queue = asyncio.Queue()
        self.critical_section_lock = asyncio.Lock()
        self.player = None

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict):
        # logger.info("on_package(), cmd: " + cmd + ", args: " + str(args))

        if cmd == "Connected":

            self.missing_checks = args["missing_locations"]
            self.prev_found = args["checked_locations"]
            self.location_ids = set(args["missing_locations"] + args["checked_locations"])
            self.options = args["slot_data"]
            asyncio.create_task(self.send_msgs([{"cmd": "GetDataPackage", "games": ["Hangman"]}]))

            # if we don't have the seed name from the RoomInfo packet, wait until we do.
            while not self.seed_name:
                time.sleep(1)

        if cmd == "ReceivedItems":
            # If receiving an item, only append that item
            asyncio.create_task(self.receive_item())

        if cmd == "RoomInfo":
            self.seed_name = args['seed_name']

        elif cmd == "DataPackage":
            if not self.location_ids:
                # Connected package not recieved yet, wait for datapackage request after connected package
                return

            self.previous_received = []
            self.location_name_to_ap_id = args["data"]["games"]["Hangman"]["location_name_to_id"]
            self.location_name_to_ap_id = {
                name: loc_id for name, loc_id in
                self.location_name_to_ap_id.items() if loc_id in self.location_ids
            }
            self.location_ap_id_to_name = {v: k for k, v in self.location_name_to_ap_id.items()}
            self.item_name_to_ap_id = args["data"]["games"]["Hangman"]["item_name_to_id"]
            self.item_ap_id_to_name = {v: k for k, v in self.item_name_to_ap_id.items()}

            # If receiving data package, resync previous items
            asyncio.create_task(self.receive_item())

        elif cmd == "LocationInfo":
            # request after an item is obtained
            asyncio.create_task(self.obtained_items_queue.put(args["locations"][0]))

        # Any player can say "@{SLOT_NAME} status" to get the current game state
        if cmd == "PrintJSON" and "message" in args:
            message = args["message"]
            if message == "@" + self.username + " status":
                asyncio.create_task(self.print_status())

    async def receive_item(self):
        async with self.critical_section_lock:

            if not self.item_ap_id_to_name:
                return

            for network_item in self.items_received:
                if network_item not in self.previous_received:
                    self.previous_received.append(network_item)
                    item_name = self.item_ap_id_to_name[network_item.item]
                    self.acquired_keys.append(item_name)

                    word = self.options["word"]
                    # Announce whether the letter is in the word, and then print the status
                    if item_name in list(word):
                        await self.say("Yes, the word contains at least one " + item_name + "!")
                    else:
                        await self.say("Sorry, but the word doesn't contain the letter " + item_name + ".")
                    await self.print_status()

                    # Check if the item unlocks any locations and send checks accordingly
                    if item_name in list(word):
                        missing_loc_names = [self.location_ap_id_to_name[id] for id in self.missing_checks]
                        for i in range(len(word)):
                            if item_name == word[i]:
                                loc_names = list(filter(lambda loc_name: loc_name.startswith(f"Letter {i+1} "), missing_loc_names))
                                logger.info("related locs: " + str(loc_names))
                                self.found_checks += [self.location_name_to_ap_id[name] for name in loc_names]
                        await self.send_checks()
                        await self.check_for_goal()

    # Check whether we've goaled yet
    async def check_for_goal(self):
        word = self.options["word"]
        for letter in list(word):
            if not letter in self.acquired_keys:
                return
        await self.say("Congratulations! The word is " + word + "!")
        await self.end_goal()

    async def end_goal(self):
        message = [{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}]
        await self.send_msgs(message)

    async def send_checks(self):
        message = [{"cmd": 'LocationChecks', "locations": self.found_checks}]
        await self.send_msgs(message)
        self.remove_found_checks()
        self.found_checks.clear()

    def remove_found_checks(self):
        self.prev_found += self.found_checks
        self.missing_checks = [item for item in self.missing_checks if item not in self.found_checks]

    async def hello_world(self):
        logger.info("Hello, world! I'm " + self.username + "!")

    # Print out the current game state
    async def print_status(self):
        word = self.options["word"]
        # message = "The word is " + word + "... oops, spoilers!"
        # await self.say(message)
        message = ""
        for letter in list(word):
            if letter in self.acquired_keys:
                message += letter
            else:
                message += "_"
            message += " "
        await self.say(message)

        guessed = ""
        remaining = ""
        for letter in list(string.ascii_uppercase):
            if letter in self.acquired_keys:
                guessed += letter
            else:
                remaining += letter
        await self.say("Guessed: " + guessed)
        await self.say("Remaining: " + remaining)

    # Convenience wrapper for sending messages
    async def say(self, message):
        await self.send_msgs([{"cmd": "Say", "text": message}])

def launch():
    """
    Launch a client instance (wrapper / args parser)
    """

    async def main(args):
        """
        Launch a client instance (threaded)
        """
        ctx = HangmanContext(args.connect, args.password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        await ctx.exit_event.wait()
        await ctx.shutdown()

    parser = get_base_parser(description="Hangman Client")
    args, _ = parser.parse_known_args()

    asyncio.run(main(args))
