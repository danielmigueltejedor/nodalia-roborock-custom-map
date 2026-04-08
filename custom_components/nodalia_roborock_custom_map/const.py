"""Constants for Nodalia Roborock Custom Map integration."""

from datetime import timedelta

DOMAIN = "nodalia_roborock_custom_map"

FAST_MAP_SCHEDULER_INTERVAL = timedelta(seconds=5)
FAST_MAP_LOCAL_INTERVAL = timedelta(seconds=5)
FAST_MAP_CLOUD_INTERVAL = timedelta(seconds=15)

LIVE_MAP_STATES = {
    "cleaning",
    "spot_cleaning",
    "segment_cleaning",
    "room_cleaning",
    "zone_cleaning",
    "clean_area",
    "returning",
    "return_to_base",
    "returning_home",
    "going_to_target",
    "goto",
}
