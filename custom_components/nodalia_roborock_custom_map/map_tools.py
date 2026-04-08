"""Utilities for extracting richer geometry from Roborock maps."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import gzip
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

_IMAGE_BLOCK_TYPE = 2
_MAP_HEADER_SIZE_OFFSET = 0x02
_ROOM_PIXEL_MASK = 0x07
_ROOM_PIXEL_VALUE = 0x07
_ROOM_NUMBER_SHIFT = 3
_VACUUM_MAP_PIXEL_SIZE = 50

type GridPoint = tuple[int, int]
type Edge = tuple[GridPoint, GridPoint]
type VacuumPoint = dict[str, int]
type Polygon = list[VacuumPoint]

_TURN_PRIORITY: dict[GridPoint, tuple[GridPoint, ...]] = {
    (1, 0): ((0, 1), (1, 0), (0, -1), (-1, 0)),
    (0, 1): ((-1, 0), (0, 1), (1, 0), (0, -1)),
    (-1, 0): ((0, -1), (-1, 0), (0, 1), (1, 0)),
    (0, -1): ((1, 0), (0, -1), (-1, 0), (0, 1)),
}


@dataclass(slots=True)
class RawImageBlock:
    """Raw image metadata extracted from a Roborock map payload."""

    data: bytes
    width: int
    height: int
    left: int
    top: int

    @property
    def cache_key(self) -> tuple[int, int, int, int, int]:
        """Return a stable cache key for geometry derived from this image block."""
        return (
            self.left,
            self.top,
            self.width,
            self.height,
            hash(self.data),
        )


def extract_image_block(raw_map: bytes | None) -> RawImageBlock | None:
    """Extract the image block from the raw Roborock map payload."""
    if raw_map is None:
        return None

    unpacked = _decompress_map(raw_map)
    if unpacked is None:
        return None

    try:
        map_header_length = _get_int16(unpacked, _MAP_HEADER_SIZE_OFFSET)
        block_start = map_header_length
        while block_start < len(unpacked):
            block_header_length = _get_int16(unpacked, block_start + 0x02)
            header = unpacked[block_start : block_start + block_header_length]
            block_type = _get_int16(header, 0x00)
            block_data_length = _get_int32(header, 0x04)
            block_data_start = block_start + block_header_length
            data = unpacked[block_data_start : block_data_start + block_data_length]

            if block_type == _IMAGE_BLOCK_TYPE:
                return RawImageBlock(
                    data=data,
                    width=_get_int32(header, block_header_length - 4),
                    height=_get_int32(header, block_header_length - 8),
                    left=_get_int32(header, block_header_length - 12),
                    top=_get_int32(header, block_header_length - 16),
                )

            block_start += block_data_length + _get_int8(header, 0x02)
    except (IndexError, ValueError, OSError) as err:
        _LOGGER.debug("Failed to extract Roborock image block: %s", err)

    return None


def extract_room_outlines(image_block: RawImageBlock | None) -> dict[int, list[Polygon]]:
    """Extract polygons for every room from the raw image block."""
    if image_block is None or image_block.width <= 0 or image_block.height <= 0:
        return {}

    room_ids = _extract_room_ids(image_block)
    room_edges = _collect_room_edges(room_ids, image_block.width, image_block.height)

    outlines: dict[int, list[Polygon]] = {}
    for room_id, edges in room_edges.items():
        polygons = []
        for loop in _trace_loops(edges):
            polygon = _grid_loop_to_polygon(loop, image_block.left, image_block.top)
            if len(polygon) >= 3:
                polygons.append(polygon)

        if polygons:
            polygons.sort(key=lambda polygon: abs(_polygon_area(polygon)), reverse=True)
            outlines[room_id] = polygons

    return outlines


def rectangle_outline(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    """Return a rectangular polygon compatible with the map card."""
    return [
        {"x": round(x0), "y": round(y0)},
        {"x": round(x0), "y": round(y1)},
        {"x": round(x1), "y": round(y1)},
        {"x": round(x1), "y": round(y0)},
    ]


def polygon_center(polygons: list[Polygon]) -> VacuumPoint | None:
    """Return the centroid of the largest polygon, if available."""
    if not polygons:
        return None

    largest = max(polygons, key=lambda polygon: abs(_polygon_area(polygon)))
    centroid = _polygon_centroid(largest)
    if centroid is not None:
        return centroid

    if not largest:
        return None

    return {
        "x": round(sum(point["x"] for point in largest) / len(largest)),
        "y": round(sum(point["y"] for point in largest) / len(largest)),
    }


def _decompress_map(raw_map: bytes) -> bytes | None:
    try:
        return gzip.decompress(raw_map)
    except OSError:
        # Some callers may already hand us an unpacked payload.
        return raw_map


def _extract_room_ids(image_block: RawImageBlock) -> list[int]:
    room_ids = [0] * (image_block.width * image_block.height)
    for index, pixel_type in enumerate(image_block.data[: len(room_ids)]):
        if pixel_type & _ROOM_PIXEL_MASK == _ROOM_PIXEL_VALUE:
            room_ids[index] = pixel_type >> _ROOM_NUMBER_SHIFT
    return room_ids


def _collect_room_edges(
    room_ids: list[int], width: int, height: int
) -> dict[int, set[Edge]]:
    room_edges: dict[int, set[Edge]] = defaultdict(set)

    def room_at(x: int, y: int) -> int:
        if x < 0 or y < 0 or x >= width or y >= height:
            return 0
        return room_ids[x + width * y]

    for y in range(height):
        row_offset = y * width
        for x in range(width):
            room_id = room_ids[row_offset + x]
            if room_id == 0:
                continue

            if room_at(x, y - 1) != room_id:
                room_edges[room_id].add(((x, y), (x + 1, y)))
            if room_at(x + 1, y) != room_id:
                room_edges[room_id].add(((x + 1, y), (x + 1, y + 1)))
            if room_at(x, y + 1) != room_id:
                room_edges[room_id].add(((x + 1, y + 1), (x, y + 1)))
            if room_at(x - 1, y) != room_id:
                room_edges[room_id].add(((x, y + 1), (x, y)))

    return room_edges


def _trace_loops(edges: set[Edge]) -> list[list[GridPoint]]:
    outgoing: dict[GridPoint, set[GridPoint]] = defaultdict(set)
    for start, end in edges:
        outgoing[start].add(end)

    loops: list[list[GridPoint]] = []
    while outgoing:
        start = next(iter(outgoing))
        end = next(iter(outgoing[start]))
        _consume_edge(outgoing, start, end)

        loop = [start]
        previous = start
        current = end
        is_closed = False

        while current != start:
            loop.append(current)
            candidates = outgoing.get(current)
            if not candidates:
                break
            next_point = _pick_next_point(previous, current, candidates)
            _consume_edge(outgoing, current, next_point)
            previous, current = current, next_point
        else:
            is_closed = True

        simplified = _simplify_loop(loop)
        if is_closed and len(simplified) >= 3:
            loops.append(simplified)

    return loops


def _consume_edge(
    outgoing: dict[GridPoint, set[GridPoint]], start: GridPoint, end: GridPoint
) -> None:
    targets = outgoing[start]
    targets.remove(end)
    if not targets:
        del outgoing[start]


def _pick_next_point(
    previous: GridPoint, current: GridPoint, candidates: set[GridPoint]
) -> GridPoint:
    if len(candidates) == 1:
        return next(iter(candidates))

    direction = (current[0] - previous[0], current[1] - previous[1])
    for candidate_direction in _TURN_PRIORITY.get(direction, ()):
        candidate = (
            current[0] + candidate_direction[0],
            current[1] + candidate_direction[1],
        )
        if candidate in candidates:
            return candidate

    return next(iter(candidates))


def _simplify_loop(loop: list[GridPoint]) -> list[GridPoint]:
    points = loop[:]
    while len(points) >= 3:
        simplified: list[GridPoint] = []
        changed = False
        total = len(points)

        for index, point in enumerate(points):
            previous = points[index - 1]
            nxt = points[(index + 1) % total]
            if point == previous or point == nxt:
                changed = True
                continue
            if _is_collinear(previous, point, nxt):
                changed = True
                continue
            simplified.append(point)

        if not changed:
            return points
        points = simplified

    return points


def _is_collinear(a: GridPoint, b: GridPoint, c: GridPoint) -> bool:
    return (b[0] - a[0]) * (c[1] - b[1]) == (b[1] - a[1]) * (c[0] - b[0])


def _grid_loop_to_polygon(
    loop: list[GridPoint], image_left: int, image_top: int
) -> Polygon:
    return [
        {
            "x": (point[0] + image_left) * _VACUUM_MAP_PIXEL_SIZE,
            "y": (point[1] + image_top) * _VACUUM_MAP_PIXEL_SIZE,
        }
        for point in loop
    ]


def _polygon_area(polygon: list[dict[str, Any]]) -> float:
    if len(polygon) < 3:
        return 0

    area = 0.0
    for index, point in enumerate(polygon):
        nxt = polygon[(index + 1) % len(polygon)]
        area += point["x"] * nxt["y"] - nxt["x"] * point["y"]
    return area / 2.0


def _polygon_centroid(polygon: Polygon) -> VacuumPoint | None:
    area = _polygon_area(polygon)
    if not area:
        return None

    factor = 0.0
    x_sum = 0.0
    y_sum = 0.0
    for index, point in enumerate(polygon):
        nxt = polygon[(index + 1) % len(polygon)]
        factor = point["x"] * nxt["y"] - nxt["x"] * point["y"]
        x_sum += (point["x"] + nxt["x"]) * factor
        y_sum += (point["y"] + nxt["y"]) * factor

    scale = 1 / (6 * area)
    return {
        "x": round(x_sum * scale),
        "y": round(y_sum * scale),
    }


def _get_int8(data: bytes, address: int) -> int:
    return data[address] & 0xFF


def _get_int16(data: bytes, address: int) -> int:
    return ((data[address] << 0) & 0xFF) | ((data[address + 1] << 8) & 0xFFFF)


def _get_int32(data: bytes, address: int) -> int:
    return (
        ((data[address] << 0) & 0xFF)
        | ((data[address + 1] << 8) & 0xFFFF)
        | ((data[address + 2] << 16) & 0xFFFFFF)
        | ((data[address + 3] << 24) & 0xFFFFFFFF)
    )
