"""Pure-Python geometry helpers for the house cleaner robot.

Every function here is intentionally ROS2-free so the coverage planner can
be unit-tested without a running ROS graph (see ``test_core.py``).
"""

import math


def yaw_to_quat(yaw):
    """Yaw (rad) -> (x, y, z, w) quaternion for a planar rotation."""
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def quat_to_yaw(q):
    """(x, y, z, w) quaternion -> yaw (rad), unwrapped to (-pi, pi]."""
    return math.atan2(
        2.0 * (q[3] * q[2] + q[0] * q[1]),
        1.0 - 2.0 * (q[1] * q[1] + q[2] * q[2]),
    )


def clamp(v, lo, hi):
    """Clamp ``v`` into ``[lo, hi]``."""
    return lo if v < lo else (hi if v > hi else v)


def cell_value(grid, x, y):
    """Occupancy [0-100] at world ``(x, y)`` or ``None`` when out of window.

    ``grid`` is any object exposing ``.info`` (``OccupancyGrid``) plus a
    ``.data`` list of int8.  Cells with ``-1`` (unknown) are reported as-is
    so callers can decide how to treat them.
    """
    info = grid.info
    col = int((x - info.origin.position.x) / info.resolution)
    row = int((y - info.origin.position.y) / info.resolution)
    if col < 0 or row < 0 or col >= info.width or row >= info.height:
        return None
    return grid.data[row * info.width + col]


def is_known_free(occ):
    """True only for observed free space (0-49).

    Unknown (-1) and out-of-window (None) are NOT free for coverage goals:
    treating unknown as free put cleaning goals on furniture that SLAM had
    not yet marked, so the robot crawled into inflation and timed out.
    """
    return occ is not None and 0 <= occ < 50


def snap_to_free_row(grid, x, y, max_sweep_m=2.0):
    """Nearest known-free cell on row ``y`` to ``(x, y)``.

    Free means occupancy in [0, 50).  Unknown (-1) does not count.
    Scans outward along ``x`` in both directions (preserving the
    boustrophedon row pattern) and returns the adjusted ``(x, y)``.
    Returns ``None`` when the whole row within ``max_sweep_m`` is blocked
    or unknown.
    """
    info = grid.info
    occ = cell_value(grid, x, y)
    if is_known_free(occ):
        return (x, y)
    max_cells = int(max_sweep_m / info.resolution)
    for step in range(1, max_cells + 1):
        for cx in (x + step * info.resolution, x - step * info.resolution):
            c = cell_value(grid, cx, y)
            if is_known_free(c):
                return (cx, y)
    return None


def revalidate_goal(grid, x, y, max_sweep_m=2.0, blocked=None):
    """Re-check a plan-time goal against a matured map/costmap.

    ``blocked(grid, x, y)`` is the predicate that decides what "occupied"
    means for this grid (e.g. costmap: ``c >= 253 and c != 255``; SLAM map:
    ``c >= 50``).  Returns ``(x, y, drop_reason)`` where ``drop_reason`` is
    ``None`` when the goal is fine, or a string when the whole row within
    ``max_sweep_m`` is blocked and the caller should skip it.
    """
    if blocked is None:
        # Default: known-occupied or unknown/out-of-window is blocked.
        blocked = lambda g, px, py: not is_known_free(cell_value(g, px, py))  # noqa: E731
    if not blocked(grid, x, y):
        return (x, y, None)
    info = grid.info
    max_cells = int(max_sweep_m / info.resolution)
    for step in range(1, max_cells + 1):
        for cx in (x + step * info.resolution, x - step * info.resolution):
            if cx == x:
                continue
            c = cell_value(grid, cx, y)
            if c is None:
                continue  # off-window snap target — not a valid escape
            if not blocked(grid, cx, y):
                return (cx, y, None)
    return (x, y, "row blocked within %g m sweep" % max_sweep_m)


def build_boustrophedon(bounds, strip, grid=None):
    """Boustrophedon coverage grid over the given rectangle.

    ``bounds`` is ``(x_min, x_max, y_min, y_max)``.  Goals are clamped inward
    by ``strip/2`` so they stay inside the SLAM costmap even while the map is
    still resizing.  Returns a list of ``(x, y, yaw)`` tuples.

    When ``grid`` is provided, every goal is snapped to a free cell on its
    row (see :func:`snap_to_free_row`) so an obstacle-adjacent goal never
    lands inside furniture that reads unknown at plan time.
    """
    x_min, x_max, y_min, y_max = bounds
    margin = strip / 2.0
    x_min = x_min + margin
    x_max = x_max - margin
    y_min = y_min + margin
    y_max = y_max - margin
    if x_max <= x_min or y_max <= y_min:
        return []

    goals = []
    y = y_min + strip / 2.0
    row = 0
    while y <= y_max - strip / 2.0:
        if row % 2 == 0:
            x0, x1, yaw0, yaw1 = x_min, x_max, 0.0, math.pi
        else:
            x0, x1, yaw0, yaw1 = x_max, x_min, math.pi, 0.0
        for x, yaw in ((x0, yaw0), (x1, yaw1)):
            if grid is not None:
                snapped = snap_to_free_row(grid, x, y)
                if snapped is None:
                    continue  # no free cell on this row — skip goal
                x, y = snapped
            goals.append((x, y, yaw))
        y += strip
        row += 1
    return goals


def coverage_bounds(grid, margin=0.37, min_extent=(2.0, 1.0)):
    """Derive the cleaning rectangle from a live SLAM occupancy grid.

    Bounds come from the map window (origin + size), inset by ``margin``.
    Returns a degenerate window's fallback ``bounds`` when the map is too
    small to plan a sensible coverage rectangle.
    """
    info = grid.info
    x_min = info.origin.position.x + margin
    y_min = info.origin.position.y + margin
    x_max = info.origin.position.x + info.width * info.resolution - margin
    y_max = info.origin.position.y + info.height * info.resolution - margin
    if (x_max - x_min) < min_extent[0] or (y_max - y_min) < min_extent[1]:
        return None
    return (x_min, x_max, y_min, y_max)