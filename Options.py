from dataclasses import dataclass

from Options import PerGameCommonOptions, StartHints, FreeText

class HangmanStartHints(StartHints):
    """Start with these items' locations prefilled into the ``!hint`` command."""
    default = []

class Word(FreeText):
    """The secret word. Leave unset to pick a word at random."""
    display_name: "Word"
    default = ""

@dataclass
class HangmanOptions(PerGameCommonOptions):
    start_hints: HangmanStartHints
    word: Word
