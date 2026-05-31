TRACKPAD_MODE_DEFAULT = "default"
LEGACY_TRACKPAD_MODE_MOUSE = "mouse"
TRACKPAD_MODE_DISABLED = "disabled"
TRACKPAD_MODE_DIRECTIONAL_BUTTONS = "directional_buttons"
TRACKPAD_MODE_MOUSE_DRAG_FIX = "mouse_drag_fix"

DEFAULT_TRACKPAD_MODE = TRACKPAD_MODE_DEFAULT
VALID_TRACKPAD_MODES = {
    TRACKPAD_MODE_DEFAULT,
    TRACKPAD_MODE_DISABLED,
    TRACKPAD_MODE_DIRECTIONAL_BUTTONS,
    TRACKPAD_MODE_MOUSE_DRAG_FIX,
}

DIRECTIONAL_CAPABILITY_MAP_ID = "deckyzone_zone_trackpad_directional"

ZOTAC_BUTTON_MAPPING_SOURCE_INDEX = 0
ZOTAC_BUTTON_MAPPING_GAMEPAD_START_INDEX = 1
ZOTAC_BUTTON_MAPPING_GAMEPAD_SIZE = 4
ZOTAC_BUTTON_MAPPING_MODIFIER_INDEX = 5
ZOTAC_BUTTON_MAPPING_KEYBOARD_START_INDEX = 7
ZOTAC_BUTTON_MAPPING_KEYBOARD_SIZE = 6
ZOTAC_BUTTON_MAPPING_MOUSE_INDEX = 13
ZOTAC_BUTTON_MAPPING_PAYLOAD_SIZE = 14

ZOTAC_TOUCH_BUTTON_DIRECTIONAL_MAPPINGS = (
    ("Left Touch Up", 0x03, "dpad_up"),
    ("Left Touch Down", 0x04, "dpad_down"),
    ("Left Touch Left", 0x05, "dpad_left"),
    ("Left Touch Right", 0x06, "dpad_right"),
    ("Right Touch Up", 0x07, "y"),
    ("Right Touch Down", 0x08, "a"),
    ("Right Touch Left", 0x09, "x"),
    ("Right Touch Right", 0x0A, "b"),
)

# Current firmware defaults observed on-device:
# the left touch directions are unmapped, while the right touch left/right
# directions drive mouse left/right click.
ZOTAC_TOUCH_BUTTON_DEFAULT_MAPPINGS = (
    ("Left Touch Up", 0x03, (), ()),
    ("Left Touch Down", 0x04, (), ()),
    ("Left Touch Left", 0x05, (), ()),
    ("Left Touch Right", 0x06, (), ()),
    ("Right Touch Up", 0x07, (), ()),
    ("Right Touch Down", 0x08, (), ()),
    ("Right Touch Left", 0x09, (), ("left",)),
    ("Right Touch Right", 0x0A, (), ("right",)),
)

ZOTAC_TOUCH_BUTTON_MOUSE_DRAG_FIX_MAPPINGS = (
    ("Left Touch Up", 0x03, (), ()),
    ("Left Touch Down", 0x04, (), ()),
    ("Left Touch Left", 0x05, (), ()),
    ("Left Touch Right", 0x06, (), ()),
    ("Right Touch Up", 0x07, (), ()),
    ("Right Touch Down", 0x08, (), ()),
    ("Right Touch Left", 0x09, (), ("left",)),
    ("Right Touch Right", 0x0A, (), ("left",)),
)

ZOTAC_GAMEPAD_BUTTON_BITS = {
    "dpad_up": (0, 0x01),
    "dpad_down": (0, 0x02),
    "dpad_left": (0, 0x04),
    "dpad_right": (0, 0x08),
    "ls": (0, 0x40),
    "rs": (0, 0x80),
    "lb": (1, 0x01),
    "rb": (1, 0x02),
    "a": (1, 0x10),
    "b": (1, 0x20),
    "x": (1, 0x40),
    "y": (1, 0x80),
    "lt": (2, 0x01),
    "rt": (2, 0x02),
}

ZOTAC_MOUSE_BUTTON_BITS = {
    "left": 0x01,
    "right": 0x02,
    "middle": 0x04,
}


def normalize_trackpad_mode(value, legacy_disabled=False):
    if isinstance(value, str):
        normalized_value = value.strip().lower()
        if normalized_value == LEGACY_TRACKPAD_MODE_MOUSE:
            return TRACKPAD_MODE_DEFAULT
        if normalized_value in VALID_TRACKPAD_MODES:
            return normalized_value

    if legacy_disabled:
        return TRACKPAD_MODE_DISABLED

    if value is True:
        return TRACKPAD_MODE_DISABLED

    return DEFAULT_TRACKPAD_MODE


def is_trackpad_mode_disabled(mode):
    return normalize_trackpad_mode(mode) == TRACKPAD_MODE_DISABLED


def is_trackpad_mode_directional(mode):
    return normalize_trackpad_mode(mode) == TRACKPAD_MODE_DIRECTIONAL_BUTTONS


def is_trackpad_mode_mouse_drag_fix(mode):
    return normalize_trackpad_mode(mode) == TRACKPAD_MODE_MOUSE_DRAG_FIX


def _build_zotac_button_mapping_payload(
    source_button_id,
    *,
    gamepad_buttons=(),
    mouse_buttons=(),
    modifier_keys=0,
    keyboard_keys=(),
):
    payload = bytearray(ZOTAC_BUTTON_MAPPING_PAYLOAD_SIZE)
    payload[ZOTAC_BUTTON_MAPPING_SOURCE_INDEX] = source_button_id
    payload[ZOTAC_BUTTON_MAPPING_MODIFIER_INDEX] = modifier_keys & 0xFF

    for button_name in gamepad_buttons:
        byte_index, bit_mask = ZOTAC_GAMEPAD_BUTTON_BITS[button_name]
        payload[ZOTAC_BUTTON_MAPPING_GAMEPAD_START_INDEX + byte_index] |= bit_mask

    for index, keycode in enumerate(tuple(keyboard_keys)[:ZOTAC_BUTTON_MAPPING_KEYBOARD_SIZE]):
        payload[ZOTAC_BUTTON_MAPPING_KEYBOARD_START_INDEX + index] = keycode & 0xFF

    mouse_mask = 0
    for button_name in mouse_buttons:
        mouse_mask |= ZOTAC_MOUSE_BUTTON_BITS[button_name]
    payload[ZOTAC_BUTTON_MAPPING_MOUSE_INDEX] = mouse_mask

    return bytes(payload)


def build_directional_trackpad_button_payloads():
    return {
        source_button_id: _build_zotac_button_mapping_payload(
            source_button_id,
            gamepad_buttons=(target_button,),
        )
        for _, source_button_id, target_button in ZOTAC_TOUCH_BUTTON_DIRECTIONAL_MAPPINGS
    }


def build_default_trackpad_button_payloads():
    return {
        source_button_id: _build_zotac_button_mapping_payload(
            source_button_id,
            gamepad_buttons=tuple(gamepad_buttons),
            mouse_buttons=tuple(mouse_buttons),
        )
        for _, source_button_id, gamepad_buttons, mouse_buttons in ZOTAC_TOUCH_BUTTON_DEFAULT_MAPPINGS
    }


def build_mouse_drag_fix_trackpad_button_payloads():
    return {
        source_button_id: _build_zotac_button_mapping_payload(
            source_button_id,
            gamepad_buttons=tuple(gamepad_buttons),
            mouse_buttons=tuple(mouse_buttons),
        )
        for _, source_button_id, gamepad_buttons, mouse_buttons in ZOTAC_TOUCH_BUTTON_MOUSE_DRAG_FIX_MAPPINGS
    }
