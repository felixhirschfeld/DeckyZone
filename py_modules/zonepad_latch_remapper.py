#!/usr/bin/env python3
import argparse
import asyncio
import contextlib
import signal
import time

from evdev import AbsInfo, InputDevice, UInput, ecodes, list_devices


DEFAULT_DEVICE_NAME = "ZOTAC Gaming Zone Mouse"
DEFAULT_RELEASE_DELAY_MS = 400
DEFAULT_LONG_PRESS_MS = 650
DEFAULT_DRAG_THRESHOLD = 12
DEFAULT_RIGHT_CLICK_MS = 70


def find_device_path(name):
    for path in list_devices():
        try:
            device = InputDevice(path)
        except OSError:
            continue
        if device.name == name:
            return path
    return None


def signed_rel(value):
    if value >= 2**31:
        return value - 2**32
    return value


def build_capabilities(source):
    caps = source.capabilities(absinfo=True)
    result = {}
    for event_type, codes in caps.items():
        if event_type == ecodes.EV_SYN:
            continue
        if event_type == ecodes.EV_KEY:
            result[event_type] = [
                code for code in codes
                if isinstance(code, int) and ecodes.BTN_MOUSE <= code <= ecodes.BTN_TASK
            ]
        elif event_type == ecodes.EV_REL:
            result[event_type] = [code for code in codes if isinstance(code, int)]
        elif event_type == ecodes.EV_ABS:
            abs_codes = []
            for code, info in codes:
                if isinstance(info, AbsInfo):
                    abs_codes.append((code, info))
            if abs_codes:
                result[event_type] = abs_codes
    return {event_type: codes for event_type, codes in result.items() if codes}


class LeftButtonLatch:
    def __init__(
        self,
        ui,
        delay_seconds,
        long_press_seconds,
        right_click_seconds,
        drag_threshold,
        verbose=False,
    ):
        self.ui = ui
        self.delay_seconds = delay_seconds
        self.long_press_seconds = long_press_seconds
        self.right_click_seconds = right_click_seconds
        self.drag_threshold = drag_threshold
        self.verbose = verbose
        self.left_down = False
        self.press_pending = False
        self.suppress_until_release = False
        self.pending_long_press = None
        self.pending_motion = 0
        self.pending_release = None
        self.pending_started_at = None

    def log(self, message):
        line = f"{time.monotonic():.6f} {message}"
        if self.verbose:
            print(line, flush=True)

    def cancel_pending_release(self):
        if self.pending_release is None:
            return
        self.pending_release.cancel()
        self.pending_release = None
        self.pending_started_at = None
        self.log("cancel delayed BTN_LEFT up")

    def cancel_pending_long_press(self):
        if self.pending_long_press is None:
            return
        self.pending_long_press.cancel()
        self.pending_long_press = None

    def emit_left_down(self):
        self.cancel_pending_long_press()
        self.press_pending = False
        self.suppress_until_release = False
        if self.left_down:
            return
        self.left_down = True
        self.ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
        self.ui.syn()
        self.log("emit BTN_LEFT=1")

    async def emit_right_click(self):
        self.ui.write(ecodes.EV_KEY, ecodes.BTN_RIGHT, 1)
        self.ui.syn()
        self.log("emit BTN_RIGHT=1")
        await asyncio.sleep(self.right_click_seconds)
        self.ui.write(ecodes.EV_KEY, ecodes.BTN_RIGHT, 0)
        self.ui.syn()
        self.log("emit BTN_RIGHT=0")

    async def long_press(self):
        try:
            await asyncio.sleep(self.long_press_seconds)
            if not self.press_pending:
                return
            self.press_pending = False
            self.pending_long_press = None
            self.suppress_until_release = True
            self.log("long press -> right click")
            await self.emit_right_click()
        except asyncio.CancelledError:
            raise

    async def delayed_release(self):
        try:
            await asyncio.sleep(self.delay_seconds)
            self.left_down = False
            self.pending_release = None
            elapsed_ms = (time.monotonic() - self.pending_started_at) * 1000
            self.pending_started_at = None
            self.ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
            self.ui.syn()
            self.log(f"emit delayed BTN_LEFT=0 after {elapsed_ms:.1f}ms")
        except asyncio.CancelledError:
            raise

    def handle_left(self, value):
        if value:
            if self.pending_release is not None:
                self.cancel_pending_release()
                self.left_down = True
                return
            if self.left_down or self.press_pending:
                return
            self.press_pending = True
            self.suppress_until_release = False
            self.pending_motion = 0
            self.pending_long_press = asyncio.create_task(self.long_press())
            self.log("pending BTN_LEFT down")
            return

        if self.press_pending:
            self.cancel_pending_long_press()
            self.press_pending = False
            self.ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
            self.ui.syn()
            self.ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
            self.ui.syn()
            self.log("emit BTN_LEFT tap")
            return

        if self.suppress_until_release:
            self.suppress_until_release = False
            self.log("suppress BTN_LEFT release after right click")
            return

        if not self.left_down:
            return
        if self.pending_release is not None:
            return
        self.pending_started_at = time.monotonic()
        self.pending_release = asyncio.create_task(self.delayed_release())
        self.log("delay BTN_LEFT=0")

    def handle_motion(self, value):
        if not self.press_pending:
            return
        self.pending_motion += abs(value)
        if self.pending_motion >= self.drag_threshold:
            self.log(f"motion threshold {self.pending_motion} -> left drag")
            self.emit_left_down()

    async def flush(self):
        self.cancel_pending_long_press()
        self.press_pending = False
        self.suppress_until_release = False
        self.cancel_pending_release()
        if self.left_down:
            self.left_down = False
            self.ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
            self.ui.syn()
            self.log("flush BTN_LEFT=0")


async def run(args):
    path = args.device or find_device_path(args.name)
    if not path:
        raise SystemExit(f"Unable to find input device named {args.name!r}")

    source = InputDevice(path)
    caps = build_capabilities(source)
    ui = UInput(caps, name=args.output_name, phys="zonepad-latch/input0")

    latch = LeftButtonLatch(
        ui,
        args.release_delay_ms / 1000,
        args.long_press_ms / 1000,
        args.right_click_ms / 1000,
        args.drag_threshold,
        verbose=args.verbose,
    )
    stop = asyncio.Event()

    def request_stop():
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, request_stop)

    print(f"source={source.path} {source.name}")
    output_path = getattr(getattr(ui, "device", None), "path", None) or "/dev/uinput"
    print(f"output={output_path} {args.output_name}")
    print(f"release_delay_ms={args.release_delay_ms}")
    print(f"long_press_ms={args.long_press_ms}")
    print(f"drag_threshold={args.drag_threshold}")
    print("grabbing source device; Ctrl+C to stop")
    latch.log(
        "started "
        f"source={source.path} "
        f"release_delay_ms={args.release_delay_ms} "
        f"long_press_ms={args.long_press_ms} "
        f"drag_threshold={args.drag_threshold} "
        f"right_click_ms={args.right_click_ms}"
    )
    source.grab()

    async def read_events():
        async for event in source.async_read_loop():
            if event.type == ecodes.EV_SYN:
                continue

            if event.type == ecodes.EV_KEY and event.code == ecodes.BTN_LEFT:
                latch.handle_left(event.value)
                continue

            if event.type == ecodes.EV_REL:
                value = signed_rel(event.value)
                latch.handle_motion(value)
                if value:
                    ui.write(event.type, event.code, value)
                    ui.syn()
                continue

            ui.write(event.type, event.code, event.value)
            ui.syn()

    reader = asyncio.create_task(read_events())
    stopper = asyncio.create_task(stop.wait())
    try:
        done, pending = await asyncio.wait(
            {reader, stopper},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            if task is reader:
                task.result()
    finally:
        reader.cancel()
        stopper.cancel()
        with contextlib.suppress(Exception):
            await latch.flush()
        with contextlib.suppress(Exception):
            source.ungrab()
        ui.close()
        source.close()
        print("stopped")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", help="source evdev path, default: auto-detect Zotac mouse")
    parser.add_argument("--name", default=DEFAULT_DEVICE_NAME)
    parser.add_argument("--output-name", default="ZonePad Drag Fix Mouse")
    parser.add_argument("--release-delay-ms", type=int, default=DEFAULT_RELEASE_DELAY_MS)
    parser.add_argument("--long-press-ms", type=int, default=DEFAULT_LONG_PRESS_MS)
    parser.add_argument("--drag-threshold", type=int, default=DEFAULT_DRAG_THRESHOLD)
    parser.add_argument("--right-click-ms", type=int, default=DEFAULT_RIGHT_CLICK_MS)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main():
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
