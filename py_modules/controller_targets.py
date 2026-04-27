STARTUP_TARGET_GAMEPAD_DEVICE_NAMES = frozenset(
    {
        "Valve Steam Deck Controller",
        "Steam Controller",
        "Zone Controller",
    }
)
STARTUP_TARGET_GAMEPAD_DEVICE_PREFIXES = ("Microsoft X-Box 360 pad",)
MISSING_GLYPH_FIX_TARGET_MODE = "xbox-elite"
MISSING_GLYPH_FIX_TARGET_GAMEPAD_DEVICE_NAMES = frozenset(
    {
        "Microsoft X-Box One Elite pad",
    }
)


def build_target_devices(target_mode, include_keyboard=True, include_mouse=True):
    targets = [str(target_mode)]
    if include_keyboard:
        targets.append("keyboard")
    if include_mouse:
        targets.append("mouse")
    return targets


def build_target_devices_busctl_args(target_mode, include_keyboard=True, include_mouse=True):
    targets = build_target_devices(
        target_mode,
        include_keyboard=include_keyboard,
        include_mouse=include_mouse,
    )
    return [str(len(targets)), *targets]


def is_startup_target_gamepad_device_name(device_name):
    if not device_name:
        return False

    if device_name in STARTUP_TARGET_GAMEPAD_DEVICE_NAMES:
        return True

    return any(
        device_name.startswith(prefix)
        for prefix in STARTUP_TARGET_GAMEPAD_DEVICE_PREFIXES
    )


def describe_startup_target_gamepad_names():
    exact_names = ", ".join(sorted(STARTUP_TARGET_GAMEPAD_DEVICE_NAMES))
    prefix_names = ", ".join(
        f"{prefix}*" for prefix in STARTUP_TARGET_GAMEPAD_DEVICE_PREFIXES
    )
    return ", ".join(part for part in (exact_names, prefix_names) if part)


def is_target_gamepad_device_name(target_mode, device_name):
    if target_mode == MISSING_GLYPH_FIX_TARGET_MODE:
        return device_name in MISSING_GLYPH_FIX_TARGET_GAMEPAD_DEVICE_NAMES

    return is_startup_target_gamepad_device_name(device_name)
