"""Gaze geometry and stale-data / optional blink handling, independent of native SDKs."""
import logging
import math

LOG = logging.getLogger(__name__)
GAZE_ADDRESS = "/tracking/eye/CenterVec"
STEREO_ADDRESS = "/tracking/eye/LeftRightVec"
BLINK_ADDRESS = "/tracking/eye/EyesClosedAmount"


def unit(v):
    length = math.sqrt(sum(x * x for x in v))
    if not math.isfinite(length) or length < 1e-10:
        raise ValueError("Invalid gaze direction")
    return tuple(x / length for x in v)


def ray_from_uv(x, y, frustum, rotation=None):
    """OpenVR raw top/bottom follow image Y; eye space is right/up/backward."""
    left, right, top, bottom = frustum
    ray = (left + (right - left) * x, -(top + (bottom - top) * y), -1.)
    if rotation is not None:
        # Direction: rotation only; eye translation does not affect a direction.
        ray = tuple(sum(rotation[i][j] * ray[j] for j in range(3)) for i in range(3))
    return unit((ray[0], ray[1], -ray[2]))  # Unity / VRChat: right, up, forward.


class Projection:
    def __init__(self, args):
        self.args = args
        self.vr = self.system = None
        self.mode = None
        self.frusta, self.rotations = {}, {}
        if args.projection != "fov":
            try:
                import openvr
                self.vr = openvr
                # Background applications do not launch SteamVR if it is closed.
                self.system = openvr.init(openvr.VRApplication_Background)
                for eye in (0, 1):
                    self.frusta[eye] = tuple(self.system.getProjectionRaw(eye))
                    matrix = self.system.getEyeToHeadTransform(eye)
                    self.rotations[eye] = tuple(tuple(matrix.m[i][j] for j in range(3)) for i in range(3))
                self._validate()
                self.mode = "steamvr"
                LOG.info("SteamVR projection: left=%s right=%s", self.frusta[0], self.frusta[1])
            except Exception as exc:
                self.close()
                self.frusta, self.rotations = {}, {}
                detail = str(exc).strip() or type(exc).__name__
                if args.projection == "steamvr" or args.gaze_space == "panel":
                    raise RuntimeError(f"SteamVR projection unavailable ({detail}). Desktop mode: use "
                                       "--projection auto --gaze-space viewport, or --projection fov. "
                                       "Panel distortion correction requires SteamVR.") from exc
                LOG.info("SteamVR unavailable (%s); using desktop FOV mapping. SteamVR is optional.", detail)
        if self.mode is None:
            h, v = math.tan(math.radians(args.fov_x / 2)), math.tan(math.radians(args.fov_y / 2))
            self.frusta = {0: (-h, h, -v, v), 1: (-h, h, -v, v)}
            self.mode = "fov"
            self._validate()
            LOG.info("Approximate symmetric FOV mapping: %s x %s degrees", args.fov_x, args.fov_y)

    def _validate(self):
        for frustum in self.frusta.values():
            if len(frustum) != 4 or not all(math.isfinite(v) for v in frustum) or frustum[0] >= frustum[1] or frustum[2] >= frustum[3]:
                raise RuntimeError(f"Invalid projection bounds: {frustum}")
        for rotation in self.rotations.values():
            if not all(math.isfinite(v) for row in rotation for v in row):
                raise RuntimeError("Invalid eye rotation")

    def direction(self, sample, eye):
        a = self.args
        x = (sample.x - a.center_x) * a.gain_x * (-1 if a.invert_x else 1) + .5
        y = (sample.y - a.center_y) * a.gain_y * (-1 if a.invert_y else 1) + .5
        x, y = max(0., min(1., x)), max(0., min(1., y))
        if eye == "center":
            # Client has already merged both eyes. Estimate one center ray, not vergence.
            return unit(tuple(l + r for l, r in zip(self._ray(x, y, 0), self._ray(x, y, 1))))
        return self._ray(x, y, 0 if eye == "left" else 1)

    def _ray(self, x, y, index):
        if self.args.gaze_space == "panel":
            ok, distortion = self.system.computeDistortion(index, x, y)
            if not ok:
                raise RuntimeError("SteamVR could not map panel coordinates to render coordinates.")
            x, y = distortion.rfGreen[0], distortion.rfGreen[1]
        return ray_from_uv(x, y, self.frusta[index], self.rotations.get(index))

    def close(self):
        if self.vr is not None and self.system is not None:
            try:
                self.vr.shutdown()
            except Exception:
                LOG.warning("Could not release OpenVR projection client", exc_info=True)
        self.system = self.vr = None


class EyeOutput:
    def __init__(self, args, projection, active_eyes):
        self.args, self.projection, self.active_eyes = args, projection, active_eyes
        self.smooth = {}
        self.last_valid = None
        self.invalid_since = None
        self.sent_closed = False

    def messages(self, samples, now):
        a = self.args
        fresh = {e: s for e, s in samples.items() if e in self.active_eyes and 0 <= now - s.received <= a.stale_seconds}
        valid = {e: s for e, s in fresh.items() if s.valid}
        messages, rays = [], {}
        for eye, sample in valid.items():
            ray = self.projection.direction(sample, eye)
            old = self.smooth.get(eye)
            if old and sample.received != old[0] and 0 < sample.received - old[0] <= a.stale_seconds:
                dt = sample.received - old[0]
                alpha = 1. if a.smoothing_ms == 0 else 1. - math.exp(-dt / (a.smoothing_ms / 1000))
                ray = unit(tuple(p + alpha * (q - p) for p, q in zip(old[1], ray)))
            elif old and sample.received == old[0]:
                ray = old[1]
            self.smooth[eye] = (sample.received, ray)
            rays[eye] = ray
        for eye in list(self.smooth):
            if eye not in valid:
                self.smooth.pop(eye)
        if rays:
            self.last_valid = now
            self.invalid_since = None
            if a.output == "per-eye":
                fallback = next(iter(rays.values()))
                values = rays.get("left", fallback) + rays.get("right", fallback)
                messages.append((STEREO_ADDRESS, values))
            else:
                messages.append((GAZE_ADDRESS, unit(tuple(sum(v[i] for v in rays.values()) for i in range(3)))))
        if a.blink == "validity":
            # Missing callbacks / prolonged loss must not leave the avatar's eyes closed.
            complete = all(e in fresh for e in self.active_eyes)
            invalid_eye = complete and all(not s.valid and s.eye_valid is not True for s in fresh.values())
            if rays:
                messages.append((BLINK_ADDRESS, (0.,)))
                self.sent_closed = False
            elif invalid_eye and self.last_valid is not None and now - self.last_valid <= a.blink_max_seconds:
                if self.invalid_since is None:
                    self.invalid_since = now
                closed = float(now - self.invalid_since >= a.blink_delay_ms / 1000)
                messages.append((BLINK_ADDRESS, (closed,)))
                self.sent_closed = bool(closed)
            else:
                self.invalid_since = None
                if self.sent_closed:
                    messages.append((BLINK_ADDRESS, (0.,)))
                    self.sent_closed = False
        return messages
