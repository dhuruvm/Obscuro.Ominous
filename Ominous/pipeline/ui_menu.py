"""
Interactive Terminal Menu Engine for Obscuro Ominous.
Provides an Ollama-style keyboard-navigable CLI UI:
- Arrow keys (↑ / ↓) to navigate
- Enter to launch / select
- Right arrow (->) to configure
- Esc / q to quit or go back
- Dim subtitles and clean spacing matching Ollama 0.34+
"""

import os
import sys
import time

# Ensure UTF-8 output encoding for symbols like ↑/↓ and •
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Enable Windows VT100 / ANSI escape sequence processing
if os.name == 'nt':
    os.system('')

# ANSI styling codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BRIGHT_WHITE = "\033[97m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


class MenuItem:
    def __init__(self, title: str, description: str = "", badge: str = "", key: str = "", on_configure=None):
        self.title = title
        self.description = description
        self.badge = badge  # e.g. "(install)" or "(GPU)"
        self.key = key      # identifier
        self.on_configure = on_configure  # Callback when user presses ->


def _read_key() -> str:
    """
    Reads a single keypress without waiting for Enter.
    Returns normalized key strings:
    'UP', 'DOWN', 'LEFT', 'RIGHT', 'ENTER', 'ESC', 'BACKSPACE',
    'CONFIGURE', or single characters.
    """
    if os.name == 'nt':
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ('\x00', '\xe0'):
            code = msvcrt.getwch()
            if code == 'H':
                return 'UP'
            elif code == 'P':
                return 'DOWN'
            elif code == 'K':
                return 'LEFT'
            elif code == 'M':
                return 'RIGHT'
            return 'UNKNOWN'
        elif ch in ('\r', '\n'):
            return 'ENTER'
        elif ch == '\x1b':
            return 'ESC'
        elif ch in ('\x08', '\x7f'):
            return 'BACKSPACE'
        elif ch == '\t':
            return 'RIGHT'
        elif ch in ('q', 'Q'):
            return 'QUIT'
        elif ch in ('c', 'C'):
            return 'CONFIGURE'
        return ch
    else:
        import tty
        import termios
        import select
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                # Check if there are more characters (escape sequence)
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    seq = sys.stdin.read(2)
                    if seq == '[A':
                        return 'UP'
                    elif seq == '[B':
                        return 'DOWN'
                    elif seq == '[C':
                        return 'RIGHT'
                    elif seq == '[D':
                        return 'LEFT'
                return 'ESC'
            elif ch in ('\r', '\n'):
                return 'ENTER'
            elif ch in ('\x7f', '\x08'):
                return 'BACKSPACE'
            elif ch in ('q', 'Q'):
                return 'QUIT'
            elif ch in ('c', 'C'):
                return 'CONFIGURE'
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class InteractiveMenu:
    """
    Renders an Ollama-style interactive terminal menu.
    """
    def __init__(
        self,
        items: list[MenuItem],
        title: str = "Obscuro Ominous 2.0.0",
        subtitle: str = "",
        footer: str = "↑/↓ navigate • enter launch • -> configure • esc quit",
        initial_index: int = 0,
        show_header: bool = True,
        clear_screen: bool = True
    ):
        self.items = items
        self.title = title
        self.subtitle = subtitle
        self.footer = footer
        self.selected_index = max(0, min(initial_index, len(items) - 1)) if items else 0
        self.show_header = show_header
        self.clear_screen = clear_screen
        self._rendered_lines = 0

    def _render_to_lines(self) -> list[str]:
        lines = []

        if self.show_header:
            lines.append(f"{BRIGHT_WHITE}{BOLD}{self.title}{RESET}")
            if self.subtitle:
                lines.append(f"{DIM}{self.subtitle}{RESET}")
            lines.append("")

        for idx, item in enumerate(self.items):
            is_selected = (idx == self.selected_index)

            # Badge formatting
            badge_str = f" {DIM}{item.badge}{RESET}" if item.badge else ""

            if is_selected:
                # Active selection: > prefix and bright bold title
                lines.append(f"{CYAN}{BOLD}> {item.title}{RESET}{badge_str}")
            else:
                # Inactive item: 2 space indentation, standard color
                lines.append(f"  {WHITE}{item.title}{RESET}{badge_str}")

            # Subtitle / description indented under title
            if item.description:
                lines.append(f"  {DIM}{item.description}{RESET}")

            # Blank line between items
            lines.append("")

        # Footer navigation guide
        lines.append(f"{DIM}{self.footer}{RESET}")
        return lines

    def _display_first(self, lines: list[str]):
        if self.clear_screen:
            os.system('cls' if os.name == 'nt' else 'clear')
        sys.stdout.write(HIDE_CURSOR)
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()
        self._rendered_lines = len(lines)

    def _display_update(self, lines: list[str]):
        # Move cursor up by previously rendered lines
        if self._rendered_lines > 0:
            # \033[{N}F moves to beginning of line N lines up
            # \033[0J clears to the end of the screen
            sys.stdout.write(f"\033[{self._rendered_lines}F\033[0J")
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()
        self._rendered_lines = len(lines)

    def _display_cleanup(self):
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()

    def run(self) -> tuple[int | None, str]:
        """
        Runs the interactive event loop.
        Returns (selected_index, action):
          action can be 'launch', 'configure', or 'quit'
        """
        if not self.items:
            return None, 'quit'

        # Check if running in an interactive terminal
        is_interactive = False
        try:
            is_interactive = sys.stdin.isatty()
        except Exception:
            is_interactive = False

        if not is_interactive:
            # Non-interactive fallback
            return self._run_fallback()

        try:
            lines = self._render_to_lines()
            self._display_first(lines)

            while True:
                key = _read_key()

                if key in ('UP', 'k', 'K'):
                    self.selected_index = (self.selected_index - 1) % len(self.items)
                    self._display_update(self._render_to_lines())

                elif key in ('DOWN', 'j', 'J'):
                    self.selected_index = (self.selected_index + 1) % len(self.items)
                    self._display_update(self._render_to_lines())

                elif key == 'ENTER':
                    self._display_cleanup()
                    return self.selected_index, 'launch'

                elif key in ('RIGHT', 'CONFIGURE'):
                    curr_item = self.items[self.selected_index]
                    if curr_item.on_configure:
                        self._display_cleanup()
                        curr_item.on_configure()
                        # Re-display menu after configure
                        lines = self._render_to_lines()
                        self._display_first(lines)
                        continue
                    else:
                        self._display_cleanup()
                        return self.selected_index, 'configure'

                elif key in ('ESC', 'QUIT'):
                    self._display_cleanup()
                    return None, 'quit'

                # Number key shortcuts 1..9
                elif key.isdigit() and 1 <= int(key) <= len(self.items):
                    self.selected_index = int(key) - 1
                    self._display_cleanup()
                    return self.selected_index, 'launch'

        except KeyboardInterrupt:
            self._display_cleanup()
            return None, 'quit'
        except Exception:
            self._display_cleanup()
            # If any console error occurred, fallback
            return self._run_fallback()

    def _run_fallback(self) -> tuple[int | None, str]:
        """Standard prompt fallback for non-tty or restricted terminals."""
        print(f"\n=== {self.title} ===")
        for i, item in enumerate(self.items, 1):
            badge = f" {item.badge}" if item.badge else ""
            desc = f" ({item.description})" if item.description else ""
            print(f"  {i}. {item.title}{badge}{desc}")
        print(f"  0. Quit / Exit")

        try:
            choice = input(f"\nSelect an option (0-{len(self.items)}): ").strip()
            if choice == "0" or choice.lower() in ('q', 'exit'):
                return None, 'quit'
            val = int(choice)
            if 1 <= val <= len(self.items):
                return val - 1, 'launch'
        except (ValueError, KeyboardInterrupt, EOFError):
            pass
        return None, 'quit'

    @classmethod
    def select(
        cls,
        options: list[tuple[str, str] | str],
        title: str = "Select an Option",
        subtitle: str = "",
        footer: str = "↑/↓ navigate • enter select • esc back",
        initial_index: int = 0
    ) -> int | None:
        """
        Quick helper to show an Ollama-style selector dialog.
        options: list of (title, description) tuples or string titles
        Returns selected index or None if cancelled/escaped.
        """
        menu_items = []
        for opt in options:
            if isinstance(opt, tuple):
                menu_items.append(MenuItem(title=opt[0], description=opt[1] if len(opt) > 1 else ""))
            else:
                menu_items.append(MenuItem(title=str(opt)))

        menu = cls(
            items=menu_items,
            title=title,
            subtitle=subtitle,
            footer=footer,
            initial_index=initial_index
        )
        idx, action = menu.run()
        if action == 'quit':
            return None
        return idx
