"""Constants for the Inköp integration."""

from typing import Final

DOMAIN: Final = "inkop"

# The required ICA integration (https://github.com/per-lennartsson/ha-ica-todo)
ICA_DOMAIN: Final = "ica"
MIN_ICA_VERSION: Final = "0.10.0"

ICA_LISTS_CHANGED: Final = "ica_lists_changed"

# How long to wait for ha-ica-todo to finish its reload after creating/deleting a list
LISTS_CHANGED_TIMEOUT: Final = 30.0

STORAGE_VERSION: Final = 1
