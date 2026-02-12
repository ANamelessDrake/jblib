"""
Modern terminal color utilities.

Provides Color and BgColor classes with ANSI color constants for f-string use,
a colored() function for complex styling with auto-reset, and multicolor
functions (gradient, rainbow, fade, cycle) for per-character color effects.
"""

__all__ = ['Color', 'BgColor', 'jbcolor', 'gradient', 'rainbow', 'fade', 'cycle', 'pulse']

_ESC = '\x1b['
_RESET = '\x1b[0m'

# Color registry: name -> (fg_ansi_code, bg_ansi_code)
_COLORS = {
    'black':         ('30', '40'),
    'red':           ('31', '41'),
    'green':         ('32', '42'),
    'yellow':        ('33', '43'),
    'blue':          ('34', '44'),
    'purple':        ('35', '45'),
    'teal':          ('36', '46'),
    'white':         ('37', '47'),
    'bright_black':  ('90', '100'),
    'bright_red':    ('91', '101'),
    'bright_green':  ('92', '102'),
    'bright_yellow': ('93', '103'),
    'bright_blue':   ('94', '104'),
    'bright_purple': ('95', '105'),
    'bright_teal':   ('96', '106'),
    'bright_white':  ('97', '107'),
    'orange':        ('38;2;255;165;0', '48;2;255;165;0'),
}

_ATTRIBUTES = {
    'bold': '1',
    'dim': '2',
    'italic': '3',
    'underline': '4',
    'reverse': '7',
    'strikethrough': '9',
}

# RGB values for multicolor functions
_RGB = {
    'black':         (0, 0, 0),
    'red':           (205, 0, 0),
    'green':         (0, 205, 0),
    'yellow':        (205, 205, 0),
    'blue':          (0, 0, 205),
    'purple':        (205, 0, 205),
    'teal':          (0, 205, 205),
    'white':         (205, 205, 205),
    'bright_black':  (127, 127, 127),
    'bright_red':    (255, 0, 0),
    'bright_green':  (0, 255, 0),
    'bright_yellow': (255, 255, 0),
    'bright_blue':   (0, 0, 255),
    'bright_purple': (255, 0, 255),
    'bright_teal':   (0, 255, 255),
    'bright_white':  (255, 255, 255),
    'orange':        (255, 165, 0),
}


class Color:
    """Foreground color and text attribute constants for f-string use.

    Example:
        print(f"{Color.RED}error{Color.OFF}")
        print(f"{Color.BOLD}{Color.ORANGE}alert{Color.OFF}")
    """
    OFF = _RESET
    RESET = _RESET


class BgColor:
    """Background color constants for f-string use.

    Example:
        print(f"{BgColor.YELLOW}{Color.BLACK}warning{Color.OFF}")
    """
    pass


# Build Color and BgColor constants from registry
for _name, (_fg, _bg) in _COLORS.items():
    setattr(Color, _name.upper(), f'{_ESC}{_fg}m')
    setattr(BgColor, _name.upper(), f'{_ESC}{_bg}m')

for _name, _code in _ATTRIBUTES.items():
    setattr(Color, _name.upper(), f'{_ESC}{_code}m')


def _resolve_rgb(color):
    """Resolve a color name string or (r, g, b) tuple to an (r, g, b) tuple."""
    if isinstance(color, (tuple, list)):
        return tuple(color[:3])
    name = color.lower().replace(' ', '_')
    if name in _RGB:
        return _RGB[name]
    raise ValueError(f"Unknown color: {color}")


def _interpolate(c1, c2, t):
    """Linearly interpolate between two RGB tuples. t in [0, 1]."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _hsv_to_rgb(h, s, v):
    """Convert HSV to RGB. h in [0, 360), s and v in [0, 1]."""
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def jbcolor(text, fg=None, bg=None, bold=False, dim=False, italic=False,
            underline=False, reverse=False, strikethrough=False):
    """Apply ANSI color and formatting to text with auto-reset.

    Args:
        text: The string to colorize.
        fg: Foreground color -- a name string ("red", "orange", "bright_blue")
            or an (r, g, b) tuple.
        bg: Background color -- same format as fg.
        bold, dim, italic, underline, reverse, strikethrough: Text attributes.

    Returns:
        The styled string with reset appended.

    Example:
        jbcolor("Error", fg="red", bold=True)
        jbcolor("Custom", fg=(128, 0, 255), bg=(0, 0, 0))
    """
    codes = []

    if fg is not None:
        if isinstance(fg, (tuple, list)):
            r, g, b = fg[:3]
            codes.append(f'38;2;{r};{g};{b}')
        else:
            name = fg.lower().replace(' ', '_')
            if name in _COLORS:
                codes.append(_COLORS[name][0])
            else:
                raise ValueError(f"Unknown foreground color: {fg}")

    if bg is not None:
        if isinstance(bg, (tuple, list)):
            r, g, b = bg[:3]
            codes.append(f'48;2;{r};{g};{b}')
        else:
            name = bg.lower().replace(' ', '_')
            if name in _COLORS:
                codes.append(_COLORS[name][1])
            else:
                raise ValueError(f"Unknown background color: {bg}")

    for flag, attr_name in [(bold, 'bold'), (dim, 'dim'), (italic, 'italic'),
                            (underline, 'underline'), (reverse, 'reverse'),
                            (strikethrough, 'strikethrough')]:
        if flag:
            codes.append(_ATTRIBUTES[attr_name])

    if not codes:
        return str(text)

    return f'{_ESC}{";".join(codes)}m{text}{_RESET}'


def gradient(text, start, end, bold=False):
    """Apply a color gradient across text, fading from start to end.

    Args:
        text: The string to colorize.
        start: Start color -- name string or (r, g, b) tuple.
        end: End color -- name string or (r, g, b) tuple.
        bold: Apply bold attribute.

    Example:
        gradient("Hello World", "red", "blue")
        gradient("Smooth", (255, 0, 0), (0, 0, 255), bold=True)
    """
    c1 = _resolve_rgb(start)
    c2 = _resolve_rgb(end)
    n = len(text)
    if n == 0:
        return ''
    prefix = '1;' if bold else ''
    chars = []
    for i, ch in enumerate(text):
        t = i / max(n - 1, 1)
        r, g, b = _interpolate(c1, c2, t)
        chars.append(f'{_ESC}{prefix}38;2;{r};{g};{b}m{ch}')
    return ''.join(chars) + _RESET


def rainbow(text, bold=False):
    """Apply rainbow colors across text characters.

    Cycles through red, orange, yellow, green, teal, blue, and purple
    using HSV color space for smooth transitions.

    Args:
        text: The string to colorize.
        bold: Apply bold attribute.

    Example:
        rainbow("Rainbow Text!")
    """
    n = len(text)
    if n == 0:
        return ''
    prefix = '1;' if bold else ''
    chars = []
    for i, ch in enumerate(text):
        hue = (i / max(n - 1, 1)) * 300
        r, g, b = _hsv_to_rgb(hue, 1.0, 1.0)
        chars.append(f'{_ESC}{prefix}38;2;{r};{g};{b}m{ch}')
    return ''.join(chars) + _RESET


def fade(text, start, end, bold=False):
    """Fade from start color to end color and back across text.

    The first character uses the start color, the middle uses the end color,
    and the last character returns to the start color.

    Args:
        text: The string to colorize.
        start: Start/end color -- name string or (r, g, b) tuple.
        end: Middle color -- name string or (r, g, b) tuple.
        bold: Apply bold attribute.

    Example:
        fade("Breathing effect", "red", "blue")
    """
    c1 = _resolve_rgb(start)
    c2 = _resolve_rgb(end)
    n = len(text)
    if n == 0:
        return ''
    prefix = '1;' if bold else ''
    chars = []
    for i, ch in enumerate(text):
        t = i / max(n - 1, 1)
        t_bounce = 1 - abs(2 * t - 1)
        r, g, b = _interpolate(c1, c2, t_bounce)
        chars.append(f'{_ESC}{prefix}38;2;{r};{g};{b}m{ch}')
    return ''.join(chars) + _RESET


def cycle(text, colors, bold=False):
    """Cycle through a list of colors, one per character, repeating.

    Args:
        text: The string to colorize.
        colors: List of colors -- each a name string or (r, g, b) tuple.
        bold: Apply bold attribute.

    Example:
        cycle("Alternating!", ["red", "blue", "green"])
        cycle("Flag", [(255, 0, 0), (255, 255, 255), (0, 0, 255)])
    """
    if not colors:
        return str(text)
    rgb_colors = [_resolve_rgb(c) for c in colors]
    num = len(rgb_colors)
    prefix = '1;' if bold else ''
    chars = []
    for i, ch in enumerate(text):
        r, g, b = rgb_colors[i % num]
        chars.append(f'{_ESC}{prefix}38;2;{r};{g};{b}m{ch}')
    return ''.join(chars) + _RESET


def pulse(text, start, end, cycles=3, speed=0.05, steps=20, bold=False):
    """Animate text pulsing between two colors in place.

    The text stays on the same line and smoothly transitions from start
    to end color and back, repeating for the given number of cycles.

    Args:
        text: The string to animate.
        start: Start color -- name string or (r, g, b) tuple.
        end: End color -- name string or (r, g, b) tuple.
        cycles: Number of full pulse cycles. Use 0 for infinite (Ctrl+C to stop).
        speed: Delay in seconds between color steps.
        steps: Number of color steps per transition direction.
        bold: Apply bold attribute.

    Example:
        pulse("ALERT", "red", "yellow", cycles=5)
        pulse("Loading...", (0, 100, 255), (0, 255, 100), cycles=0)
    """
    import sys
    import time

    c1 = _resolve_rgb(start)
    c2 = _resolve_rgb(end)
    prefix = '1;' if bold else ''

    # Build frames for one full cycle: start -> end -> start
    frames = []
    for i in range(steps):
        t = i / steps
        r, g, b = _interpolate(c1, c2, t)
        frames.append(f'{_ESC}{prefix}38;2;{r};{g};{b}m{text}{_RESET}')
    for i in range(steps):
        t = i / steps
        r, g, b = _interpolate(c2, c1, t)
        frames.append(f'{_ESC}{prefix}38;2;{r};{g};{b}m{text}{_RESET}')

    try:
        count = 0
        while cycles == 0 or count < cycles:
            for frame in frames:
                sys.stdout.write(f'\r{frame}')
                sys.stdout.flush()
                time.sleep(speed)
            count += 1
    except KeyboardInterrupt:
        pass
    finally:
        r, g, b = c1
        sys.stdout.write(f'\r{_ESC}{prefix}38;2;{r};{g};{b}m{text}{_RESET}\n')
        sys.stdout.flush()
