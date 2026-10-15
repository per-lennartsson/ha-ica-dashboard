"""Constants for the Handla integration."""

from typing import Final

DOMAIN: Final = "handla"

# The required ICA integration (https://github.com/per-lennartsson/ha-ica-todo)
ICA_DOMAIN: Final = "ica"
MIN_ICA_VERSION: Final = "0.10.0"

ICA_LISTS_CHANGED: Final = "ica_lists_changed"

# How long to wait for ha-ica-todo to finish its reload after creating/deleting a list
LISTS_CHANGED_TIMEOUT: Final = 30.0

STORAGE_VERSION: Final = 1

# Frequent items shown as quick-add buttons
QUICK_ADD_LIMIT: Final = 12
USAGE_SAVE_DELAY: Final = 10.0

# Notifications when someone adds items
CONF_RECIPIENTS: Final = "recipients"  # {user_id: notify service name}
EVENT_ITEM_ADDED: Final = "handla_item_added"
NOTIFY_DELAY: Final = 20.0  # seconds: adds within this window become one message

# Optional AI module (off by default)
CONF_AI_ENABLED: Final = "ai_enabled"
CONF_AI_ENTITY: Final = "ai_entity"  # entity id of the chosen ai_task entity
AI_TASK_DOMAIN: Final = "ai_task"
