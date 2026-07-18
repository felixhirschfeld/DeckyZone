"""UMA framebuffer (VRAM) size control for the Zotac Zone.

The Zotac Windows launcher stores the UMA buffer size in CMOS byte
index 0x7A, written through the legacy RTC/CMOS I/O ports 0x70/0x71.
The BIOS reads that byte during boot and sizes the UMA framebuffer
accordingly, so a write only takes effect after a reboot. The setting
is not exposed through EFI variables (verified by diffing efivarfs
before/after a change in the Windows launcher); the CMOS byte is the
only known storage location. HandheldCompanion uses the same port I/O
mechanism on Windows via WinRing0.

Encoding (verified against the Windows Zotac launcher on a 16GB Zone):

    byte value = VRAM size in 256MB units (VRAM_GB * 4)
    4GB (default) = 16, 5GB = 20, 6GB = 24, 7GB = 28, 8GB = 32

The Windows launcher allows the 4GB base plus increments of 1GB up to
+4GB (4-8GB total); the same range is enforced here.
"""

import glob

PORT_DEVICE_PATH = "/dev/port"
CMOS_INDEX_PORT = 0x70
CMOS_DATA_PORT = 0x71
CMOS_VRAM_INDEX = 0x7A
CMOS_UNITS_PER_GB = 4
MIN_VRAM_GB = 4
MAX_VRAM_GB = 8
DRM_VRAM_TOTAL_GLOB = "/sys/class/drm/card*/device/mem_info_vram_total"
BYTES_PER_GB = 1024 ** 3


def is_valid_vram_gb(size_gb):
    return isinstance(size_gb, int) and MIN_VRAM_GB <= size_gb <= MAX_VRAM_GB


def _cmos_transaction(port_file, value=None):
    """Select the VRAM CMOS index, optionally write a byte, and read it back.

    The index and data accesses are kept back-to-back within a single open
    file handle to minimize the (already tiny) race window with the kernel
    rtc-cmos driver, which shares ports 0x70/0x71.
    """
    port_file.seek(CMOS_INDEX_PORT)
    port_file.write(bytes([CMOS_VRAM_INDEX]))
    if value is not None:
        port_file.seek(CMOS_DATA_PORT)
        port_file.write(bytes([value]))
        port_file.seek(CMOS_INDEX_PORT)
        port_file.write(bytes([CMOS_VRAM_INDEX]))
    port_file.seek(CMOS_DATA_PORT)
    data = port_file.read(1)
    if len(data) != 1:
        raise RuntimeError("Failed to read CMOS data port.")
    return data[0]


def read_pending_vram_gb():
    """Return the VRAM size in GB currently stored in CMOS.

    This is the value the BIOS will apply on the next boot. May be a
    fractional value if the stored byte is not a whole number of GB.
    """
    with open(PORT_DEVICE_PATH, "r+b", buffering=0) as port_file:
        raw_value = _cmos_transaction(port_file)
    return raw_value / CMOS_UNITS_PER_GB


def write_vram_gb(size_gb):
    """Store a new VRAM size in CMOS and verify the read-back.

    Takes effect on the next boot. Raises on invalid sizes or when the
    read-back does not match the written value.
    """
    if not is_valid_vram_gb(size_gb):
        raise ValueError(
            f"VRAM size must be a whole number between {MIN_VRAM_GB} and {MAX_VRAM_GB} GB."
        )

    raw_value = size_gb * CMOS_UNITS_PER_GB
    with open(PORT_DEVICE_PATH, "r+b", buffering=0) as port_file:
        read_back = _cmos_transaction(port_file, raw_value)

    if read_back != raw_value:
        raise RuntimeError(
            f"CMOS VRAM read-back mismatch: wrote {raw_value}, read {read_back}."
        )

    return size_gb


def read_active_vram_gb():
    """Return the VRAM size in GB currently in use by the amdgpu driver.

    Returns None when no amdgpu VRAM sysfs node is present.
    """
    for path in sorted(glob.glob(DRM_VRAM_TOTAL_GLOB)):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                vram_bytes = int(handle.read().strip())
        except (OSError, ValueError):
            continue
        if vram_bytes > 0:
            return round(vram_bytes / BYTES_PER_GB, 2)
    return None
