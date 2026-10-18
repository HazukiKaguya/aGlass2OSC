"""VRCFT v5 eye module transport and direct v2 float avatar parameters."""
from dataclasses import dataclass

from .tracking import BLINK_ADDRESS, GAZE_ADDRESS, STEREO_ADDRESS, EyeOutput

BRIDGE_ADDRESS = "/aglass/v1/eyes"
ACTIVE_ADDRESS = "/avatar/parameters/EyeTrackingActive"


def cartesian(ray):
    # VRCFT 5.2.3's Vector2.ToYaw/ToPitch use atan(x/y); supply gaze slopes.
    # Expression parameters saturate at +/-1, corresponding to +/-45 degrees.
    return tuple(max(-1., min(1., v / max(1e-6, ray[2]))) for v in ray[:2])


@dataclass(frozen=True)
class EyeFrame:
    active: bool = False
    left: tuple = (0., 0., 1.)
    right: tuple = (0., 0., 1.)

    def values(self):
        return (self.active, *self.left, *self.right)


class VrcftOutput:
    def __init__(self, args, projection, active_eyes):
        self.args = args
        self.eyes = {eye: EyeOutput(args, projection, (eye,)) for eye in active_eyes}
        self.gaze = {}
        self.last_active = None
        self.next_status = 0.

    def frame(self, samples, now):
        states = {}
        for eye, output in self.eyes.items():
            messages = dict(output.messages(samples, now))
            ray = messages.get(GAZE_ADDRESS, messages.get(STEREO_ADDRESS))
            if ray is not None:
                self.gaze[eye] = cartesian(ray[:3])
            sample = samples.get(eye)
            # A recent, continuously reported invalid eye can be a blink. A missing
            # callback or a visible eye with invalid gaze cannot establish activity.
            blink = (self.args.blink == "validity" and sample is not None
                     and 0 <= now - sample.received <= self.args.stale_seconds
                     and not sample.valid and sample.eye_valid is not True
                     and output.last_valid is not None
                     and now - output.last_valid <= self.args.blink_max_seconds)
            active = ray is not None or blink
            if active:
                closed = messages.get(BLINK_ADDRESS, (0.,))[0]
                states[eye] = (*self.gaze.get(eye, (0., 0.)), 1. - closed)
        if not states:
            return EyeFrame()
        # Combined Client API and single-eye hardware drive both avatar eyes.
        # An eye which has never tracked is not interpreted as permanently closed.
        fallback = next(iter(states.values()))
        def resolve(eye):
            if eye in states:
                return states[eye]
            if eye in self.eyes and eye in self.gaze:
                # A previously tracked eye which stops reporting is a dropout,
                # not a second blink. Borrow gaze, but leave its eyelid open.
                return (*fallback[:2], 1.)
            return fallback
        return EyeFrame(True, resolve("left"), resolve("right"))

    def avatar_messages(self, frame, now, force=False):
        messages = []
        prefix = "/avatar/parameters/" + self.args.parameter_prefix + "/"
        lx, ly, lo = frame.left
        rx, ry, ro = frame.right
        if frame.active or self.last_active is True or force:
            values = {"EyeLeftX": lx, "EyeLeftY": ly, "EyeRightX": rx, "EyeRightY": ry,
                      "EyeX": (lx + rx) / 2, "EyeY": (ly + ry) / 2}
            if self.args.blink != "off":
                values.update(EyeLidLeft=lo * .75, EyeLidRight=ro * .75, EyeLid=(lo + ro) * .375)
            messages += [(prefix + name, (value,)) for name, value in values.items()]
        # Refresh status for late game launch / avatar changes without an OSCQuery client.
        if force or frame.active != self.last_active or now >= self.next_status:
            messages.append((ACTIVE_ADDRESS, (frame.active,)))
            self.next_status = now + 1.
        self.last_active = frame.active
        return messages

    def messages(self, samples, now):
        frame = self.frame(samples, now)
        if self.args.target == "vrcft-module":
            return [(BRIDGE_ADDRESS, frame.values())]
        return self.avatar_messages(frame, now)

    def shutdown_messages(self):
        if self.args.target == "vrcft-module":
            return [(BRIDGE_ADDRESS, EyeFrame().values())]
        return self.avatar_messages(EyeFrame(), 0., force=True)
