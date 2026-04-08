"""Support for Roborock image."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.components.roborock.coordinator import RoborockDataUpdateCoordinator
from homeassistant.components.roborock.entity import RoborockCoordinatedEntityV1
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from roborock.devices.traits.v1.home import HomeTrait
from roborock.devices.traits.v1.map_content import MapContent
from roborock.exceptions import RoborockException

from .const import (
    FAST_MAP_CLOUD_INTERVAL,
    FAST_MAP_LOCAL_INTERVAL,
    FAST_MAP_SCHEDULER_INTERVAL,
    LIVE_MAP_STATES,
)
from .map_tools import (
    extract_image_block,
    extract_room_outlines,
    polygon_center,
    rectangle_outline,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock image platform."""

    async_add_entities(
        RoborockMap(
            config_entry,
            f"{coord.duid_slug}_custom_map_{map_info.name or f'Map {map_info.map_flag}'}",
            coord,
            coord.properties_api.home,
            map_info.map_flag,
            map_info.name,
        )
        for coord in config_entry.runtime_data
        if coord.properties_api.home is not None
        for map_info in (coord.properties_api.home.home_map_info or {}).values()
    )


class RoborockMap(RoborockCoordinatedEntityV1, ImageEntity):
    """A class to let you visualize the map."""

    _attr_has_entity_name = True
    image_last_updated: datetime
    _attr_name: str

    def __init__(
        self,
        config_entry: ConfigEntry,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        home_trait: HomeTrait,
        map_flag: int,
        map_name: str,
    ) -> None:
        """Initialize a Roborock map."""
        RoborockCoordinatedEntityV1.__init__(self, unique_id, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self.config_entry = config_entry
        if not map_name:
            map_name = f"Map {map_flag}"
        self._attr_name = map_name + "_custom"
        self.map_flag = map_flag
        self._home_trait = home_trait

        self.cached_map = b""
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._fast_refresh_lock = asyncio.Lock()
        self._fast_refresh_unsub = None
        self._last_fast_refresh: datetime | None = None
        self._room_outlines_cache: dict[int, list[list[dict[str, int]]]] = {}
        self._room_outlines_cache_key: tuple[int, int, int, int, int] | None = None

    @property
    def is_selected(self) -> bool:
        """Return if this map is the currently selected map."""
        return self.map_flag == self.coordinator.properties_api.maps.current_map

    @property
    def _map_content(self) -> MapContent | None:
        if self._home_trait.home_map_content and (
            map_content := self._home_trait.home_map_content.get(self.map_flag)
        ):
            return map_content
        return None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass load any previously cached maps from disk."""
        await super().async_added_to_hass()
        self._attr_image_last_updated = self.coordinator.last_home_update
        self._fast_refresh_unsub = async_track_time_interval(
            self.hass,
            self._async_fast_map_refresh,
            FAST_MAP_SCHEDULER_INTERVAL,
        )
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when the entity is removed from Home Assistant."""
        if self._fast_refresh_unsub is not None:
            self._fast_refresh_unsub()
            self._fast_refresh_unsub = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data updates from the base Roborock coordinator."""
        if (map_content := self._map_content) is None:
            return
        if self.cached_map != map_content.image_content:
            self.cached_map = map_content.image_content
            self._attr_image_last_updated = self.coordinator.last_home_update

        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Get the cached image."""
        if (map_content := self._map_content) is None:
            raise HomeAssistantError("Map flag not found in coordinator maps")
        return map_content.image_content

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose map metadata for custom cards."""
        if (map_content := self._map_content) is None:
            raise HomeAssistantError("Map flag not found in coordinator maps")

        map_data = map_content.map_data
        if map_data is None:
            return {}

        rooms = self._build_room_payload(map_content)
        vacuum_room = map_data.vacuum_room
        vacuum_room_name = None
        if vacuum_room is not None:
            room_payload = rooms.get(str(vacuum_room))
            if room_payload is not None:
                vacuum_room_name = room_payload.get("name")

        return {
            "calibration_points": map_data.calibration(),
            "rooms": rooms,
            "zones": self._serialize_zones(map_data.zones),
            "vacuum_position": self._serialize_point(map_data.vacuum_position),
            "charger_position": self._serialize_point(map_data.charger),
            "goto_target": self._serialize_point(map_data.goto),
            "vacuum_room": vacuum_room,
            "vacuum_room_name": vacuum_room_name,
            "map_dimensions": self._serialize_map_dimensions(map_data),
            "map_flag": self.map_flag,
            "is_selected": self.is_selected,
        }

    async def _async_fast_map_refresh(self, now: datetime) -> None:
        """Refresh the live map more often while the robot is moving."""
        if not self._should_fast_refresh():
            return

        refresh_interval = self._target_refresh_interval()
        if (
            self._last_fast_refresh is not None
            and (now - self._last_fast_refresh) < refresh_interval
        ):
            return

        if self._fast_refresh_lock.locked():
            return

        async with self._fast_refresh_lock:
            try:
                await self._home_trait.refresh()
            except RoborockException as err:
                _LOGGER.debug("Failed to refresh live Roborock map: %s", err)
                return

            self._last_fast_refresh = dt_util.utcnow()
            self.coordinator.last_home_update = self._last_fast_refresh
            self.coordinator.async_update_listeners()

    def _should_fast_refresh(self) -> bool:
        """Return if the map should be refreshed aggressively."""
        if not self.is_selected or self._map_content is None:
            return False

        status = self.coordinator.properties_api.status
        state_name = str(getattr(status, "state_name", "") or "").lower()

        return bool(
            getattr(status, "in_cleaning", False)
            or state_name in LIVE_MAP_STATES
            or "return" in state_name
        )

    def _target_refresh_interval(self):
        """Return the active refresh interval for the current connection type."""
        if self.coordinator.device.is_local_connected:
            return FAST_MAP_LOCAL_INTERVAL
        return FAST_MAP_CLOUD_INTERVAL

    def _build_room_payload(self, map_content: MapContent) -> dict[str, dict[str, Any]]:
        """Build room metadata compatible with polygon-aware vacuum cards."""
        map_data = map_content.map_data
        if map_data is None or map_data.rooms is None:
            return {}

        room_outlines = self._room_outlines_for(map_content)
        room_payload: dict[str, dict[str, Any]] = {}

        for room in map_data.rooms.values():
            room_name = self._room_name_for(room.number)
            outlines = room_outlines.get(room.number)
            rectangles = [rectangle_outline(room.x0, room.y0, room.x1, room.y1)]
            if not outlines:
                outlines = rectangles

            center = polygon_center(outlines)
            room_payload[str(room.number)] = {
                "x0": round(room.x0),
                "y0": round(room.y0),
                "x1": round(room.x1),
                "y1": round(room.y1),
                "number": room.number,
                "name": room_name,
                "label": room_name,
                "pos_x": room.pos_x if room.pos_x is not None else center["x"] if center else None,
                "pos_y": room.pos_y if room.pos_y is not None else center["y"] if center else None,
                "outlines": outlines,
                "polygons": outlines,
                "rectangles": rectangles,
            }

        return room_payload

    def _room_outlines_for(self, map_content: MapContent) -> dict[int, list[list[dict[str, int]]]]:
        """Return cached room polygons for the current raw map payload."""
        image_block = extract_image_block(map_content.raw_api_response)
        if image_block is None:
            self._room_outlines_cache = {}
            self._room_outlines_cache_key = None
            return {}

        cache_key = image_block.cache_key
        if cache_key != self._room_outlines_cache_key:
            self._room_outlines_cache = extract_room_outlines(image_block)
            self._room_outlines_cache_key = cache_key

        return self._room_outlines_cache

    def _room_name_for(self, room_number: int) -> str:
        """Resolve the configured name of a room."""
        rooms_trait = getattr(self._home_trait, "_rooms_trait", None)
        room_map = getattr(rooms_trait, "room_map", {})
        room_name = room_map.get(room_number)
        return room_name.name if room_name else "Unknown"

    @staticmethod
    def _serialize_point(point: Any) -> dict[str, Any] | None:
        """Serialize a point-like object into JSON-safe data."""
        if point is None:
            return None

        payload = {
            "x": point.x,
            "y": point.y,
        }
        if getattr(point, "a", None) is not None:
            payload["a"] = point.a
        return payload

    @staticmethod
    def _serialize_map_dimensions(map_data: Any) -> dict[str, Any] | None:
        """Serialize the image metadata exposed by the Roborock parser."""
        if map_data.image is None:
            return None

        dimensions = map_data.image.dimensions
        return {
            "width": dimensions.width,
            "height": dimensions.height,
            "top": dimensions.top,
            "left": dimensions.left,
            "scale": dimensions.scale,
            "rotation": dimensions.rotation,
        }

    @staticmethod
    def _serialize_zones(zones: Any) -> list[dict[str, Any]] | None:
        """Serialize zones into a card-friendly structure."""
        if zones is None:
            return None

        payload = []
        for zone in zones:
            payload.append(
                {
                    "x0": zone.x0,
                    "y0": zone.y0,
                    "x1": zone.x1,
                    "y1": zone.y1,
                    "outlines": [rectangle_outline(zone.x0, zone.y0, zone.x1, zone.y1)],
                }
            )
        return payload
