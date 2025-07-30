"""Constants used throughout the FeliCa Dumper."""

# Batch processing
MAX_BATCH_SIZE = 32

# Key node IDs
SYSTEM_KEY_NODE_ID = 0xFFFF
ROOT_AREA_KEY_NODE_ID = 0x0000
AREA_KEY_THRESHOLD = 0x1000

# Block processing
MAX_BLOCKS = 0x10000

# Service type masks and values
SERVICE_TYPE_MASK = 0b1111
SERVICE_NUMBER_MASK = 0x3F
SERVICE_PURSE_TYPE = 0b0100
SERVICE_RANDOM_TYPE = 0b0010
SERVICE_CYCLIC_TYPE = 0b0011

# Access type descriptions
RANDOM_CYCLIC_ACCESS_TYPES = [
    "write with key",
    "write w/o key",
    "read with key",
    "read w/o key",
]

PURSE_ACCESS_TYPES = [
    "direct with key",
    "direct w/o key",
    "cashback with key",
    "cashback w/o key",
    "decrement with key",
    "decrement w/o key",
    "read with key",
    "read w/o key",
]

# Key version display constants
NO_KEY_VALUE = 0xFFFF
