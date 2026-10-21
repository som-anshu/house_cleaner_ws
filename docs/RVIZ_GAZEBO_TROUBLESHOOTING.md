# Open-Source Robotics Visualization

## High-Level Troubleshooting Guide for RViz & Gazebo Simulations

**Scope.** When working with open-source robotics frameworks (ROS 2, Gazebo, RViz),
complex data pipelines produce visualization bugs and mapping errors whose
symptoms look alike but whose causes are unrelated. This handout separates them.

**How to read it.** Every issue below has four parts:

| Part | Meaning |
| --- | --- |
| Symptom | What you actually see on screen |
| Measure | The command that turns a vague complaint into a number |
| Root cause | The mechanism, in pipeline terms |
| Resolution | What to change, and why that change works |

**Golden rule.** *Never tune a knob before you have measured the thing the knob
controls.* Every parameter named here was chosen from a measurement, not a
default. The two failures in this document — scan drift and pane flicker — look
similar on screen and share **nothing** in common mechanically. Diagnosing them
by symptom alone will waste a day.

---

## 1. Map Misalignment & Scan Drift (SLAM)

### 1.1 Symptom

Laser scans fail to align as the robot moves: the map footprint looks blurred,
jagged, or overlapping, and the rendered map appears to **jump or re-tear on each
new scan**. Distinct from slow drift — this is the whole map being yanked around.

### 1.2 Measure first

The single most informative measurement is the size and stability of the SLAM
correction, `map → odom`:

```sh
ros2 run tf2_ros tf2_echo map odom
```

Run it twice, a minute apart, and compare. Then quantify the *span* over time:

```sh
# In-container, or on the host with the ROS env sourced.
python3 - <<'PY'
import rclpy, math
from rclpy.node import Node
from tf2_msgs.msg import TFMessage
from rclpy.qos import QoSProfile, ReliabilityPolicy
rclpy.init(); n = Node('drift')
seen = []
def cb(m):
    for t in m.transforms:
        if t.header.frame_id.strip('/') == 'map' and t.child_frame_id.strip('/') == 'odom':
            seen.append((t.transform.translation.x, t.transform.translation.y))
n.create_subscription(TFMessage, '/tf', cb,
    QoSProfile(depth=50, reliability=ReliabilityPolicy.BEST_EFFORT))
import time; t0 = time.time()
while time.time() - t0 < 30: rclpy.spin_once(n, timeout_sec=0.1)
xs = [a for a, _ in seen]; ys = [b for _, b in seen]
print(f"samples={len(seen)}  x span={max(xs)-min(xs):.3f} m  y span={max(ys)-min(ys):.3f} m")
PY
```

**Interpretation.**

| `map → odom` span over ~30 s of normal driving | Meaning |
| --- | --- |
| < 0.10 m | Healthy. Scan matching is doing small corrections. |
| 0.1 – 0.5 m | Marginal. Odometry is noisy; scan matching is compensating. |
| **> 1.0 m** | **Broken.** SLAM is relocalising, not correcting. This is the tearing symptom. |

Also confirm the odometry is physically plausible. Compare `/odom` against the
known size of the world:

```sh
ros2 topic echo /odom --field pose.pose.position --once
```

If the robot is in a 5 × 6 m room but `/odom` reports a position 15 m away,
**no amount of SLAM tuning will fix the map.** The odometry itself is the fault,
and scan matching is being asked to correct an error it did not create.

### 1.3 Root causes, in priority order

**(a) Odometry is integrating in the wrong frame.** The Gazebo `DiffDrive`
plugin publishes a conventional `odom → base_footprint` transform. Its
`pose` is integrated from commanded wheel velocities. Under discontinuous
motion — docking creep, collision-monitor speed limiting, abrupt cancels — the
integration accumulates error that never gets corrected, because nothing feeds
back a ground-truth pose.

**(b) `/odom` covariance is all zeros.** SLAM fuses odometry and scan matching
by *weighting each by its stated uncertainty*. An all-zero covariance declares
"infinitely confident", which is self-contradictory and leaves the scan matcher
with no basis to override a bad odometry guess.

**(c) SLAM travel gates are mismatched to the motion profile.** Two parameters
govern when a new scan match is attempted:

| Parameter | Consequence if too large | Consequence if too small |
| --- | --- | --- |
| `minimum_travel_distance` | Short moves never trigger a match, so `map → odom` goes stale | Extra matching, more CPU |
| `minimum_travel_heading` | Small rotations never trigger a match | Extra matching |

The gate must be **smaller than the shortest meaningful motion** in the mission.
In a docking workflow the undock move is only ~0.48 m; a gate of 0.5 m means the
final undock never triggers a match, the map pose stays stale by ~0.5 m, and the
robot ends up *inside* the dock's lethal cells in the map — at which point the
planner legitimately reports it cannot find a plan.

**(d) Scan-topic QoS mismatch (a silent killer).** Laser scans are normally
published `BEST_EFFORT` + `VOLATILE`. A subscriber requesting `RELIABLE`
receives **nothing at all**, with no error: the scan display simply stays empty.
Verify both ends:

```sh
ros2 topic info /scan --verbose    # check reliability on publisher AND subscriber
```

**Check this before concluding "SLAM is broken" — it is far more common than a
genuinely bad scan matcher.**

**(e) Time is inconsistent.** Every node must agree on the clock source. With
`use_sim_time: true`, the clock comes from `/clock`; a single node left on wall
time will produce transforms that appear delayed or from the future, and the
scan matcher rejects them. Confirm `/clock` is publishing and that every node
reports `use_sim_time: true`:

```sh
ros2 param get /slam_toolbox use_sim_time
ros2 topic hz /clock
```

### 1.4 Resolutions

| Fix | Change | Why it works |
| --- | --- | --- |
| Verify the TF tree | Confirm one continuous chain `map → odom → base_footprint`, each at a steady rate | A dropped link makes scan matching impossible; the tree, not the algorithm, is the fault |
| Set the SLAM travel gate below the shortest motion | `minimum_travel_distance` < shortest move (e.g. 0.15 m for a 0.48 m undock) | Guarantees every meaningful move triggers a re-match |
| Give odometry honest covariance | Populate the `pose` and `twist` covariance diagonals from simulation noise | Lets the matcher know how much to distrust odometry |
| Match scan QoS | Subscriber `BEST_EFFORT` for `/scan` | A `RELIABLE` subscriber to a `BEST_EFFORT` publisher receives zero messages |
| Unify the clock | `use_sim_time: true` everywhere; confirm `/clock` | Removes spurious "transform too old/future" rejections |
| Reduce dependence on odometry | Use scan matching with a tighter search window and a higher-resolution grid | Shifts trust from a drifting integrator to the sensor |

> **Calibration note.** Wheel radius and wheel separation errors do cause
> *compound rotational* drift — a constant small yaw error grows without bound
> over distance. This is a real cause of drift, but it is **not** the cause when
> `/odom` is off by many metres after a few minutes: that magnitude indicates
> integration/frame error, not a miscalibrated wheel. Measure the drift rate
> first, then decide which of the two you have.

---

## 2. RViz Flickering & Black Screen Artifacts

### 2.1 Symptom

The RViz pane flickers heavily, or draws large black rectangles over the 3D
scene, especially under Docker, VMs, or venv-style GPU setups.

### 2.2 Measure first — do not assume it is the GPU

The supplied advice on this topic is *"set `LIBGL_ALWAYS_SOFTWARE=1`"*. **On a
machine with a working GPU this is actively harmful** — it replaces hardware
rendering with llvmpipe, making an already CPU-heavy simulation much slower, and
can *introduce* tearing rather than remove it.

Determine which renderer is genuinely in use before touching anything:

```sh
# On the host.
glxinfo -B | grep -E "OpenGL (vendor|renderer|version)"

# Inside the container — the answer that actually matters.
docker exec <container> bash -lc 'DISPLAY=:0 glxinfo -B | head -12'
```

| Result | Meaning | Action |
| --- | --- | --- |
| `NVIDIA` / `AMD` / `Intel`, `direct rendering: Yes` | **Hardware rendering works.** | Do **not** set `LIBGL_ALWAYS_SOFTWARE`. Fix the *content* instead (§2.3) |
| `llvmpipe` / `softpipe` | Genuinely software-rendered | Diagnose GPU passthrough before considering it acceptable |
| Error / no display | Display or device not visible to the container | Fix the X socket / device mount |

Confirm the environment is not fighting the driver:

```sh
docker exec <container> env | grep -iE "LIBGL|QT_X11|VBLANK|GL_SYNC|DISPLAY|MESA"
```

### 2.3 Root causes when the GPU is healthy

If hardware rendering is confirmed, flicker is almost always **content-driven**,
not driver-driven.

**(a) The map is moving under the camera.** This is the connection between §1
and §2, and it is the most commonly missed: a thrashing `map → odom` transform
means the *entire scene* is re-placed every frame. With `Fixed Frame: map`, the
map display, robot, TF axes and laser scan all jump together. That reads as
"flickering RViz" while the actual fault is SLAM instability. **Fix §1 and the
flicker frequently disappears.**

**(b) A heavy PointCloud2 display.** Dense clouds with a long decay time, large
point size, and a high queue size saturate the update path, producing stutter
that looks like flicker. Check:

```sh
grep -nE "Decay Time|Point Size|Size \(m\)|Queue Size|Alpha" <your>.rviz
```

**(c) Update-rate saturation.** An RViz `Frame Rate` far above what the displays
can sustain means the compositor is always behind, which presents as tearing.
Lower it to a rate the scene can actually hold (15–30 Hz), and reduce `Queue
Size` so a backlog cannot build up.

**(d) VSync interaction with the container.** Presenting every frame immediately,
rather than waiting on a vblank that never arrives correctly through the
container's display path, removes a common class of tearing. The relevant
environment variables are:

```sh
vblank_mode=xpresent      # present immediately instead of waiting on vblank
__GL_SYNC_TO_VBLANK=0     # do not block the GL client on the display refresh
```

**(e) Shared-memory (MIT-SHM) transfer problems.** Under X11 forwarding or in
containers, the shared-memory image path can corrupt or half-draw. Disabling it
is safe and cheap:

```sh
QT_X11_NO_MITSHM=1
```

**(f) TF axis rendering at high frame rate.** A TF display drawing axes for
every frame at full rate is more expensive than it appears, particularly with
many frames. Reduce the TF marker scale or disable the display when a frame tree
is large.

### 2.4 Resolutions

| Fix | Change | Why it works |
| --- | --- | --- |
| Confirm the renderer first | `glxinfo -B` in the container | Prevents "fixing" a working GPU into software mode |
| Stabilise SLAM | See §1 | Removes the moving-scene tearing at its source |
| Disable MIT-SHM | `QT_X11_NO_MITSHM=1` | Avoids the fragile shared-memory image path |
| Correct vsync behaviour | `vblank_mode=xpresent`, `__GL_SYNC_TO_VBLANK=0` | Presents immediately instead of waiting on an unreliable vblank |
| Lower display load | Shorter decay, smaller points, smaller queue, RViz `Frame Rate` 15–30 | Keeps the render loop inside its budget |
| Reserve software rendering | `LIBGL_ALWAYS_SOFTWARE=1` **only** with no GPU | Correct when there is no GPU; harmful when there is one |

> **Never bake `LIBGL_ALWAYS_SOFTWARE=1` into an image or a launch script.**
> It silently overrides a working GPU for every future run, and the resulting
> "the simulation got slow" report is hard to trace back to it.

---

## 3. System-Level Synchronization

### 3.1 Symptom

Everything *looks* configured correctly, yet the map is wrong, frames are late,
buffers are empty, or two subsystems disagree about where the robot is.

### 3.2 The three clocks

| Clock | Source | Failure signature |
| --- | --- | --- |
| Simulation time | `/clock` from Gazebo | Transforms "in the future", sim appears frozen, `ros2 topic hz` shows zero |
| Wall time | The host | Transforms rejected as stale/future when mixed with sim time |
| Sensor timestamps | Each plugin's message `header.stamp` | Scan matching fails; plots show nothing |

**Rule:** with a simulator, *every* node must set `use_sim_time: true`. One node
left on wall time is enough to break TF for the whole graph.

### 3.3 TF buffer versus producer rate

`tf_buffer_duration` and `transform_timeout` must comfortably exceed the slowest
*producer* of the frames they carry. If a transform is published every 5 s but
the buffer holds 3 s, lookups intermittently fail — which the user sees as
random flicker. Measure the producer rate, then size the buffer above it:

```sh
ros2 topic hz /tf
```

### 3.4 TF authority — exactly one publisher per edge

A transform edge must have exactly one authority. Two publishers for the same
`parent → child` pair causes the frame to alternate between them, which reads as
violent jitter. Enumerate the authorities:

```sh
ros2 topic info /tf --verbose | grep "Node name"
```

**Note:** `slam_toolbox` legitimately appears **twice** in that list, because it
publishes `map → odom` *and* internally republishes. Two entries for the same
node are fine; two *different* nodes claiming the same edge are not.

### 3.5 QoS consistency

QoS is a contract. A mismatch does not warn — it silently delivers nothing.

| Topic class | Typical publisher QoS | Consequence of a `RELIABLE` subscriber |
| --- | --- | --- |
| Laser scans | `BEST_EFFORT`, `VOLATILE` | Receives **zero** messages |
| Camera images | `BEST_EFFORT` | Receives **zero** messages |
| Maps / latched state | `RELIABLE`, `TRANSIENT_LOCAL` | A `VOLATILE` subscriber misses the latched value entirely |

Latching matters for state a late subscriber must still learn. A `TRANSIENT_LOCAL`
publisher hands the last value to a subscriber that joins afterwards; a
`VOLATILE` one leaves that subscriber waiting forever.

```sh
ros2 topic info <topic> --verbose    # compare reliability + durability both sides
```

### 3.6 Resolution checklist

| Check | Command | Healthy result |
| --- | --- | --- |
| Sim time everywhere | `ros2 param get <node> use_sim_time` | `true` for every node |
| Clock is running | `ros2 topic hz /clock` | Steady rate |
| Buffer exceeds producer period | `ros2 topic hz /tf` vs `tf_buffer_duration` | Buffer comfortably larger |
| One authority per TF edge | `ros2 topic info /tf --verbose` | One node per `parent → child` |
| QoS matches | `ros2 topic info <t> --verbose` | Same reliability/durability both ends |
| Scan matching settled | `ros2 run tf2_ros tf2_echo map odom` | Small, slowly varying values |

---

## 4. Diagnostic Order of Operations

Work top-down. Each step removes a whole class of causes, so later steps are
interpreted against a known-good baseline.

| # | Step | Command | Rules out |
| --- | --- | --- | --- |
| 1 | Is the clock healthy? | `ros2 topic hz /clock` | Every time-related failure |
| 2 | Are all nodes on sim time? | `ros2 param get <node> use_sim_time` | Stale/future transform rejection |
| 3 | Is the renderer hardware? | `docker exec … glxinfo -B` | The entire "GPU is broken" branch |
| 4 | Is the TF tree complete? | `ros2 run tf2_ros tf2_echo map base_footprint` | Missing-link failures |
| 5 | Is odometry plausible? | `ros2 topic echo /odom --field pose.pose.position` | Integrator/frame faults |
| 6 | Is the SLAM correction stable? | `tf2_echo map odom`, span over 30 s | Scan-matching thrash |
| 7 | Is QoS matched? | `ros2 topic info <t> --verbose` | Silent empty displays |
| 8 | Is the frame rate adequate? | RViz `Frame Rate`; host `nvidia-smi` | Content-driven stutter |

---

## 5. Anti-Patterns

| Anti-pattern | Why it is wrong |
| --- | --- |
| Setting `LIBGL_ALWAYS_SOFTWARE=1` on a machine with a GPU | Trades a working fast path for a slow one and can cause the tearing it was meant to fix |
| Tuning SLAM parameters before measuring `map → odom` | Chases a symptom the parameters may not govern |
| Assuming drift is wheel miscalibration | Multi-metre odometry error indicates integration/frame faults, not wheel radius |
| Treating a `RELIABLE` subscriber to a `BEST_EFFORT` topic as "no data yet" | It will never receive data; the mismatch is silent by design |
| Running two authorities for one TF edge | Produces jitter indistinguishable from a rendering fault |
| Mixing sim time and wall time "just for one node" | Breaks TF for the whole graph |
| Building analysis on an unverified baseline | Later measurements inherit the earlier fault |

---

## 6. Quick Reference

### 6.1 Environment variables

| Variable | Value | Purpose |
| --- | --- | --- |
| `LIBGL_ALWAYS_SOFTWARE` | `0` with a GPU, `1` without | Selects hardware vs software GL |
| `QT_X11_NO_MITSHM` | `1` | Avoids the shared-memory image path |
| `vblank_mode` | `xpresent` | Present immediately rather than wait on vblank |
| `__GL_SYNC_TO_VBLANK` | `0` | Do not block the GL client on refresh |
| `__GLX_VENDOR_LIBRARY_NAME` | `nvidia` | Selects the vendor GLX implementation |

### 6.2 Thresholds worth remembering

| Quantity | Healthy | Investigate | Broken |
| --- | --- | --- | --- |
| `map → odom` span over 30 s driving | < 0.10 m | 0.1 – 0.5 m | > 1.0 m |
| `/odom` position vs known world size | Inside the world | Near the boundary | Far outside |
| RViz frame rate | ≥ 15 FPS | 5 – 15 FPS | < 5 FPS |
| `map → odom` yaw span over 30 s | < 1° | 1 – 5° | > 5° |

### 6.3 One-line definitions

- **TF tree** — the graph of coordinate frames; every sensor reading is
  interpreted through it.
- **`odom → base_footprint`** — continuous but drifting; from wheel integration.
- **`map → odom`** — discontinuous but bounded; SLAM's correction of odometry.
- **Scan matching** — aligning a new scan to the existing map to estimate motion.
- **QoS** — a delivery contract; mismatched contracts deliver nothing silently.
- **Latching (`TRANSIENT_LOCAL`)** — replays the last message to late subscribers.

---

*Measure, then tune. The two failures in this handout present almost identically
on screen and have nothing in common mechanically — only measurement separates
them.*
