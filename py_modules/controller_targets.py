def build_target_devices(target_mode, include_mouse=True):
    targets = [str(target_mode), "keyboard"]
    if include_mouse:
        targets.append("mouse")
    return targets


def build_target_devices_busctl_args(target_mode, include_mouse=True):
    targets = build_target_devices(target_mode, include_mouse=include_mouse)
    return [str(len(targets)), *targets]
