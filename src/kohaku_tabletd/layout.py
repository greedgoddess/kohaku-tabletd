"""Pure monitor-layout math, kept free of D-Bus so it can be tested."""

ROTATED = {1, 3, 5, 7}  # Mutter transforms 90/270, flipped or not


# [doc:lay-pick]
def pick_scale(target, supported):
    """Nearest scale Mutter supports for the current mode."""
    if not supported:
        return target
    return min(supported, key=lambda s: abs(s - target))


# [doc:lay-size]
def logical_size(lm, logical_layout=True):
    width, height = lm["width"], lm["height"]
    if lm["transform"] in ROTATED:
        width, height = height, width
    if logical_layout:
        return round(width / lm["scale"]), round(height / lm["scale"])
    return width, height


# [doc:lay-target]
def find_target(lms, output=""):
    """Index of the logical monitor to rescale: named connector or built-in panel."""
    for index, lm in enumerate(lms):
        if (output in lm["connectors"]) if output else lm["builtin"]:
            return index
    return None


# [doc:lay-rescale]
def rescale(lms, index, scale, logical_layout=True):
    """New layout with one monitor rescaled. Monitors right of / below it
    shift by the size change so nothing overlaps or leaves a gap."""
    new = [dict(lm) for lm in lms]
    target = new[index]
    old_w, old_h = logical_size(target, logical_layout)
    target["scale"] = scale
    new_w, new_h = logical_size(target, logical_layout)
    right, bottom = target["x"] + old_w, target["y"] + old_h
    for i, lm in enumerate(new):
        if i == index:
            continue
        if lm["x"] >= right:
            lm["x"] += new_w - old_w
        if lm["y"] >= bottom:
            lm["y"] += new_h - old_h
    return new
