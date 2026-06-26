import random
import sys
import tkinter as tk
from tkinter import colorchooser, ttk
from collections import deque
from dataclasses import dataclass, asdict
from enum import Enum


GRID_SIZE = 20

INITIAL_SNAKE_LENGTH = 3


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @staticmethod
    def opposite(direction: "Direction") -> "Direction | None":
        opposites = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT,
        }
        return opposites.get(direction)


@dataclass
class GameSettings:
    cols: int = 30
    rows: int = 30
    tick_ms: int = 100
    show_grid: bool = True

    background: str = "#000000"
    grid: str = "#282828"
    text: str = "#ffffff"
    accent: str = "#0078ff"
    danger: str = "#ff0000"

    snake_head: str = "#00ff00"
    snake_body: str = "#00b400"
    snake_outline: str = "#00ff00"

    food_fill: str = "#ff0000"
    food_outline: str = "#0078ff"

    def copy(self) -> "GameSettings":
        return GameSettings(**asdict(self))

    def clamp(self) -> None:
        self.cols = max(10, min(60, int(self.cols)))
        self.rows = max(10, min(60, int(self.rows)))
        self.tick_ms = max(40, min(300, int(self.tick_ms)))

    @property
    def width_px(self) -> int:
        return int(self.cols) * GRID_SIZE

    @property
    def height_px(self) -> int:
        return int(self.rows) * GRID_SIZE


class Snake:
    def __init__(self, settings: GameSettings) -> None:
        self.settings = settings
        self.reset()

    def reset(self) -> None:
        start_x = self.settings.cols // 2
        start_y = self.settings.rows // 2
        self.positions: deque[tuple[int, int]] = deque([(start_x, start_y)])
        self.direction = Direction.RIGHT
        self.next_direction = Direction.RIGHT
        self.grow_pending = INITIAL_SNAKE_LENGTH - 1
        self.score = 0

    def head(self) -> tuple[int, int]:
        return self.positions[0]

    def turn(self, direction: Direction) -> None:
        if len(self.positions) > 1 and direction == Direction.opposite(self.direction):
            return
        self.next_direction = direction

    def move(self) -> bool:
        self.direction = self.next_direction
        hx, hy = self.head()
        dx, dy = self.direction.value
        nx = (hx + dx) % self.settings.cols
        ny = (hy + dy) % self.settings.rows
        new_head = (nx, ny)

        if new_head in self.positions:
            return False

        self.positions.appendleft(new_head)
        if self.grow_pending > 0:
            self.grow_pending -= 1
        else:
            self.positions.pop()
        return True

    def grow(self) -> None:
        self.grow_pending += 1
        self.score += 10


class Food:
    def __init__(self, snake: Snake, settings: GameSettings) -> None:
        self.snake = snake
        self.settings = settings
        self.color_fill: str = self.settings.food_fill
        self.color_outline: str = self.settings.food_outline
        self.position = self.spawn()

    def spawn(self) -> tuple[int, int]:
        # Change food color randomly every 30 score (30, 60, 90, ...)
        if self.snake.score > 0 and self.snake.score % 30 == 0:
            self.color_fill = self._random_color()
            self.color_outline = self._random_color()

        while True:
            x = random.randint(0, self.settings.cols - 1)
            y = random.randint(0, self.settings.rows - 1)
            if (x, y) not in self.snake.positions:
                return (x, y)

    def _random_color(self) -> str:
        return "#" + "".join(random.choice("0123456789ABCDEF") for _ in range(6))


class GameView(tk.Frame):
    def __init__(self, parent: tk.Misc, app: "App", settings: GameSettings) -> None:
        super().__init__(parent)
        self.app = app
        self.settings = settings
        self.settings.clamp()

        self.canvas = tk.Canvas(
            self,
            width=self.settings.width_px,
            height=self.settings.height_px,
            bg=self.settings.background,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.snake = Snake(self.settings)
        self.food = Food(self.snake, self.settings)
        self.game_over = False
        self.paused = False
        self._after_id: str | None = None

        self.bind_all("<Up>", lambda e: self.snake.turn(Direction.UP))
        self.bind_all("<Down>", lambda e: self.snake.turn(Direction.DOWN))
        self.bind_all("<Left>", lambda e: self.snake.turn(Direction.LEFT))
        self.bind_all("<Right>", lambda e: self.snake.turn(Direction.RIGHT))
        self.bind_all("<space>", self._on_space)
        self.bind_all("<Escape>", lambda e: self.app.quit())

    def destroy(self) -> None:
        self._cancel_tick()
        self.unbind_all("<Up>")
        self.unbind_all("<Down>")
        self.unbind_all("<Left>")
        self.unbind_all("<Right>")
        self.unbind_all("<space>")
        self.unbind_all("<Escape>")
        super().destroy()

    def _cancel_tick(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _on_space(self, _event: tk.Event) -> None:
        self.paused = not self.paused

    def start(self) -> None:
        self.draw()
        self._after_id = self.after(self.settings.tick_ms, self.update)

    def update(self) -> None:
        if not self.game_over and not self.paused:
            alive = self.snake.move()
            if not alive:
                self.game_over = True
                score = self.snake.score
                self._cancel_tick()
                self.app.show_end(won=False, score=score)
                return
            if self.snake.head() == self.food.position:
                self.snake.grow()
                self.food.position = self.food.spawn()
                total_cells = int(self.settings.cols) * int(self.settings.rows)
                if len(self.snake.positions) + int(self.snake.grow_pending) >= total_cells:
                    self._cancel_tick()
                    self.app.show_end(won=True, score=self.snake.score)
                    return

        self.draw()
        self._after_id = self.after(self.settings.tick_ms, self.update)

    def draw(self) -> None:
        self.canvas.configure(bg=self.settings.background)
        self.canvas.delete("all")
        if self.settings.show_grid:
            self._draw_grid()
        self._draw_food()
        self._draw_snake()
        self._draw_ui()

    def _draw_grid(self) -> None:
        w = self.settings.width_px
        h = self.settings.height_px
        for x in range(0, w, GRID_SIZE):
            self.canvas.create_line(x, 0, x, h, fill=self.settings.grid, width=1)
        for y in range(0, h, GRID_SIZE):
            self.canvas.create_line(0, y, w, y, fill=self.settings.grid, width=1)

    def _draw_food(self) -> None:
        shape_idx = (max(0, int(self.snake.score)) // 10) % 5
        x, y = self.food.position
        x1 = x * GRID_SIZE
        y1 = y * GRID_SIZE
        x2 = x1 + GRID_SIZE
        y2 = y1 + GRID_SIZE
        pad = max(2, GRID_SIZE // 8)
        ix1, iy1, ix2, iy2 = x1 + pad, y1 + pad, x2 - pad, y2 - pad
        cx, cy = (ix1 + ix2) // 2, (iy1 + iy2) // 2

        if shape_idx == 0:
            self.canvas.create_rectangle(
                ix1, iy1, ix2, iy2, fill=self.food.color_fill, outline=self.food.color_outline, width=2
            )
        elif shape_idx == 1:
            self.canvas.create_oval(
                ix1, iy1, ix2, iy2, fill=self.food.color_fill, outline=self.food.color_outline, width=2
            )
        elif shape_idx == 2:
            self.canvas.create_polygon(
                cx,
                iy1,
                ix2,
                iy2,
                ix1,
                iy2,
                fill=self.food.color_fill,
                outline=self.food.color_outline,
                width=2,
            )
        elif shape_idx == 3:
            self.canvas.create_polygon(
                cx,
                iy1,
                ix2,
                cy,
                cx,
                iy2,
                ix1,
                cy,
                fill=self.food.color_fill,
                outline=self.food.color_outline,
                width=2,
            )
        else:
            r = max(3, (ix2 - ix1) // 2)
            points: list[int] = []
            import math

            for i in range(10):
                ang = math.pi / 2 + i * (math.pi / 5)
                rr = r if i % 2 == 0 else max(2, int(r * 0.5))
                px = int(cx + rr * math.cos(ang))
                py = int(cy - rr * math.sin(ang))
                points.extend([px, py])
            self.canvas.create_polygon(
                *points, fill=self.food.color_fill, outline=self.food.color_outline, width=2
            )

    def _draw_snake(self) -> None:
        for i, (x, y) in enumerate(self.snake.positions):
            x1 = x * GRID_SIZE
            y1 = y * GRID_SIZE
            x2 = x1 + GRID_SIZE
            y2 = y1 + GRID_SIZE
            if i == 0:
                self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill=self.settings.snake_head, outline=self.settings.text, width=2
                )
                self._draw_eyes(x1, y1, x2, y2)
            else:
                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=self.settings.snake_body,
                    outline=self.settings.snake_outline,
                    width=1,
                )

    def _draw_eyes(self, x1: int, y1: int, x2: int, y2: int) -> None:
        eye_size = GRID_SIZE // 6
        eye_offset = GRID_SIZE // 4
        eye_color = "#000000"

        cx = x1 + GRID_SIZE // 2
        cy = y1 + GRID_SIZE // 2

        if self.snake.direction == Direction.RIGHT:
            ex = x2 - eye_offset
            self._oval(ex, cy - eye_offset, eye_size, eye_color)
            self._oval(ex, cy + eye_offset, eye_size, eye_color)
        elif self.snake.direction == Direction.LEFT:
            ex = x1 + eye_offset
            self._oval(ex, cy - eye_offset, eye_size, eye_color)
            self._oval(ex, cy + eye_offset, eye_size, eye_color)
        elif self.snake.direction == Direction.UP:
            ey = y1 + eye_offset
            self._oval(cx - eye_offset, ey, eye_size, eye_color)
            self._oval(cx + eye_offset, ey, eye_size, eye_color)
        else:  # DOWN
            ey = y2 - eye_offset
            self._oval(cx - eye_offset, ey, eye_size, eye_color)
            self._oval(cx + eye_offset, ey, eye_size, eye_color)

    def _oval(self, cx: int, cy: int, r: int, fill: str) -> None:
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline="")

    def _draw_ui(self) -> None:
        self.canvas.create_text(
            10,
            10,
            anchor="nw",
            fill=self.settings.text,
            font=("Segoe UI", 20, "bold"),
            text=f"Score: {self.snake.score}",
        )

        if self.paused:
            self.canvas.create_text(
                self.settings.width_px // 2,
                self.settings.height_px // 2,
                fill=self.settings.accent,
                font=("Segoe UI", 40, "bold"),
                text="PAUSED",
            )


class MenuView(tk.Frame):
    def __init__(self, parent: tk.Misc, app: "App", settings: GameSettings) -> None:
        super().__init__(parent, padx=16, pady=16)
        self.app = app
        self.settings = settings
        self.last_score_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")
        self._defaults = GameSettings()

        title = tk.Label(self, text="Snake Game", font=("Segoe UI", 28, "bold"))
        title.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        score = tk.Label(self, textvariable=self.last_score_var, font=("Segoe UI", 12))
        score.grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 6))

        status = tk.Label(self, textvariable=self.status_var, font=("Segoe UI", 10), fg="#bbbbbb")
        status.grid(row=2, column=0, columnspan=4, sticky="w", pady=(0, 12))

        self.cols_var = tk.IntVar(value=self.settings.cols)
        self.rows_var = tk.IntVar(value=self.settings.rows)
        self.tick_var = tk.IntVar(value=self.settings.tick_ms)
        self.grid_var = tk.BooleanVar(value=self.settings.show_grid)

        self._color_vars: dict[str, tk.StringVar] = {
            "background": tk.StringVar(value=self.settings.background),
            "snake_head": tk.StringVar(value=self.settings.snake_head),
            "snake_body": tk.StringVar(value=self.settings.snake_body),
            "food_fill": tk.StringVar(value=self.settings.food_fill),
            "food_outline": tk.StringVar(value=self.settings.food_outline),
        }

        top = tk.Frame(self)
        top.grid(row=3, column=0, columnspan=4, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        form = ttk.LabelFrame(top, text="Settings")
        form.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        top.grid_columnconfigure(0, weight=1)
        top.grid_rowconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=1)

        r = 0
        ttk.Label(form, text="Map size").grid(row=r, column=0, sticky="w", padx=10, pady=(10, 6))
        size_row = tk.Frame(form)
        size_row.grid(row=r, column=1, sticky="w", padx=10, pady=(10, 6))
        ttk.Spinbox(size_row, from_=10, to=60, textvariable=self.cols_var, width=6).pack(side="left")
        ttk.Label(size_row, text="×").pack(side="left", padx=6)
        ttk.Spinbox(size_row, from_=10, to=60, textvariable=self.rows_var, width=6).pack(side="left")
        r += 1

        self.speed_label = tk.StringVar(value="")
        ttk.Label(form, text="Speed").grid(row=r, column=0, sticky="w", padx=10, pady=6)
        speed_row = tk.Frame(form)
        speed_row.grid(row=r, column=1, sticky="w", padx=10, pady=6)
        ttk.Scale(
            speed_row,
            from_=300,
            to=40,
            variable=self.tick_var,
            length=170,
            command=lambda _v: self._refresh_preview(),
        ).pack(side="left")
        ttk.Label(speed_row, textvariable=self.tick_var, width=4).pack(side="left", padx=(8, 0))
        ttk.Label(speed_row, text="ms").pack(side="left")
        ttk.Label(speed_row, textvariable=self.speed_label, width=8).pack(side="left", padx=(8, 0))
        r += 1

        ttk.Checkbutton(form, text="Show grid", variable=self.grid_var, command=self._refresh_preview).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=10, pady=(6, 10)
        )
        r += 1

        ttk.Separator(form, orient="horizontal").grid(row=r, column=0, columnspan=3, sticky="ew", padx=10, pady=(4, 10))
        r += 1

        ttk.Label(form, text="Colors").grid(row=r, column=0, sticky="w", padx=10, pady=(0, 6))
        presets_row = tk.Frame(form)
        presets_row.grid(row=r, column=1, sticky="w", padx=10, pady=(0, 6))
        self.preset_var = tk.StringVar(value="Classic")
        ttk.Label(presets_row, text="Preset:").pack(side="left")
        preset_box = ttk.Combobox(
            presets_row,
            textvariable=self.preset_var,
            state="readonly",
            width=12,
            values=["Classic", "Neon", "Ocean", "Candy"],
        )
        preset_box.pack(side="left", padx=(6, 0))
        preset_box.bind("<<ComboboxSelected>>", lambda _e: self._apply_preset())
        r += 1

        self._color_row(form, r, "Background", "background")
        r += 1
        self._color_row(form, r, "Snake head", "snake_head")
        r += 1
        self._color_row(form, r, "Snake body", "snake_body")
        r += 1
        self._color_row(form, r, "Food", "food_fill")
        r += 1
        self._color_row(form, r, "Food outline", "food_outline")

        preview = ttk.LabelFrame(top, text="Preview")
        preview.grid(row=0, column=1, sticky="nsew", padx=(12, 0), pady=(0, 12))
        self.preview_canvas = tk.Canvas(preview, width=220, height=220, highlightthickness=0, bg=self._color_vars["background"].get())
        self.preview_canvas.pack(padx=10, pady=10)

        actions = tk.Frame(self)
        actions.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        actions.grid_columnconfigure(0, weight=1)

        play_btn = ttk.Button(actions, text="Play", command=self._on_play)
        play_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        reset_btn = ttk.Button(actions, text="Reset", command=self._reset_defaults)
        reset_btn.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        quit_btn = ttk.Button(actions, text="Quit", command=self.app.quit)
        quit_btn.grid(row=0, column=2, sticky="ew")

        hint = tk.Label(
            self,
            text="Controls: Arrow keys move • Space pauses • Esc quits",
            font=("Segoe UI", 10),
        )
        hint.grid(row=5, column=0, columnspan=4, sticky="w", pady=(10, 0))

        for v in (self.cols_var, self.rows_var, self.tick_var, self.grid_var, *self._color_vars.values()):
            v.trace_add("write", lambda *_args: self._refresh_preview())

        # Keyboard shortcuts
        self.bind_all("<Return>", lambda _e: self._on_play())
        self.bind_all("<Control-r>", lambda _e: self._reset_defaults())
        self.bind_all("<Control-q>", lambda _e: self.app.quit())

        # Button hover feedback
        self._add_hover(play_btn)
        self._add_hover(reset_btn)
        self._add_hover(quit_btn)

        play_btn.focus_set()
        self._refresh_preview()

    def set_last_score(self, score: int | None) -> None:
        self.last_score_var.set("" if score is None else f"Last score: {score}")
        if score is None:
            self.status_var.set("Pick a preset, then press Play. (You can also click Pick… to choose colors.)")
        else:
            self.status_var.set("Game over! Adjust settings and press Play to try again.")

    def _color_row(self, parent: tk.Misc, row: int, label: str, key: str) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=6)
        row_frame = tk.Frame(parent)
        row_frame.grid(row=row, column=1, columnspan=2, sticky="w", padx=10, pady=6)
        swatch = tk.Label(row_frame, width=2, relief="ridge", bg=self._color_vars[key].get())
        swatch.pack(side="left", padx=(0, 8))
        entry = ttk.Entry(row_frame, textvariable=self._color_vars[key], width=12)
        entry.pack(side="left")
        ttk.Button(row_frame, text="Pick…", command=lambda k=key: self._pick_color(k)).pack(side="left", padx=(8, 0))
        self._color_vars[key].trace_add("write", lambda *_args, s=swatch, k=key: s.configure(bg=self._color_vars[k].get()))

    def _pick_color(self, key: str) -> None:
        initial = self._color_vars[key].get()
        result = colorchooser.askcolor(color=initial, parent=self)
        if result and result[1]:
            self._color_vars[key].set(result[1])

    def _apply_preset(self) -> None:
        preset = self.preset_var.get()
        presets: dict[str, dict[str, str]] = {
            "Classic": {
                "background": "#000000",
                "snake_head": "#00ff00",
                "snake_body": "#00b400",
                "food_fill": "#ff0000",
                "food_outline": "#0078ff",
            },
            "Neon": {
                "background": "#090018",
                "snake_head": "#00f5ff",
                "snake_body": "#7cff00",
                "food_fill": "#ff2bd6",
                "food_outline": "#ffffff",
            },
            "Ocean": {
                "background": "#001219",
                "snake_head": "#00b4d8",
                "snake_body": "#0077b6",
                "food_fill": "#ffb703",
                "food_outline": "#fb8500",
            },
            "Candy": {
                "background": "#14001f",
                "snake_head": "#ff4d6d",
                "snake_body": "#c77dff",
                "food_fill": "#4cc9f0",
                "food_outline": "#f72585",
            },
        }
        colors = presets.get(preset)
        if not colors:
            return
        for k, v in colors.items():
            self._color_vars[k].set(v)
        self.status_var.set(f"Preset applied: {preset}")

    def _reset_defaults(self) -> None:
        self.cols_var.set(self._defaults.cols)
        self.rows_var.set(self._defaults.rows)
        self.tick_var.set(self._defaults.tick_ms)
        self.grid_var.set(self._defaults.show_grid)
        self._color_vars["background"].set(self._defaults.background)
        self._color_vars["snake_head"].set(self._defaults.snake_head)
        self._color_vars["snake_body"].set(self._defaults.snake_body)
        self._color_vars["food_fill"].set(self._defaults.food_fill)
        self._color_vars["food_outline"].set(self._defaults.food_outline)
        self.preset_var.set("Classic")
        self.status_var.set("Reset to defaults.")

    def _apply_settings_from_ui(self) -> None:
        self.settings.cols = int(self.cols_var.get())
        self.settings.rows = int(self.rows_var.get())
        self.settings.tick_ms = int(self.tick_var.get())
        self.settings.show_grid = bool(self.grid_var.get())

        def _hex_or_fallback(value: str, fallback: str) -> str:
            v = value.strip()
            if len(v) == 7 and v.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in v[1:]):
                return v
            return fallback

        self.settings.background = _hex_or_fallback(self._color_vars["background"].get(), self.settings.background)
        self.settings.snake_head = _hex_or_fallback(self._color_vars["snake_head"].get(), self.settings.snake_head)
        self.settings.snake_body = _hex_or_fallback(self._color_vars["snake_body"].get(), self.settings.snake_body)
        self.settings.food_fill = _hex_or_fallback(self._color_vars["food_fill"].get(), self.settings.food_fill)
        self.settings.food_outline = _hex_or_fallback(self._color_vars["food_outline"].get(), self.settings.food_outline)

        self.settings.clamp()

    def _on_play(self) -> None:
        self._apply_settings_from_ui()
        self.app.start_game()

    def _refresh_preview(self) -> None:
        c = getattr(self, "preview_canvas", None)
        if c is None:
            return

        try:
            cols = max(10, min(60, int(self.cols_var.get())))
            rows = max(10, min(60, int(self.rows_var.get())))
        except Exception:
            cols, rows = 30, 30

        bg = self._color_vars["background"].get()
        snake_head = self._color_vars["snake_head"].get()
        snake_body = self._color_vars["snake_body"].get()
        food = self._color_vars["food_fill"].get()
        food_outline = self._color_vars["food_outline"].get()

        c.configure(bg=bg)
        c.delete("all")

        pad = 12
        size = 220 - pad * 2
        cell = max(6, min(16, size // max(cols, rows)))
        w = cell * cols
        h = cell * rows
        ox = (220 - w) // 2
        oy = (220 - h) // 2

        if bool(self.grid_var.get()):
            grid_color = "#333333"
            for x in range(0, w + 1, cell):
                c.create_line(ox + x, oy, ox + x, oy + h, fill=grid_color, width=1)
            for y in range(0, h + 1, cell):
                c.create_line(ox, oy + y, ox + w, oy + y, fill=grid_color, width=1)

        sx, sy = cols // 2, rows // 2
        segments = [(sx, sy), (sx - 1, sy), (sx - 2, sy)]
        for i, (x, y) in enumerate(segments):
            x1 = ox + x * cell
            y1 = oy + y * cell
            x2 = x1 + cell
            y2 = y1 + cell
            c.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=snake_head if i == 0 else snake_body,
                outline="#ffffff" if i == 0 else snake_body,
                width=1,
            )

        fx, fy = min(cols - 2, sx + 3), sy
        x1 = ox + fx * cell
        y1 = oy + fy * cell
        x2 = x1 + cell
        y2 = y1 + cell
        c.create_rectangle(x1, y1, x2, y2, fill=food, outline=food_outline, width=2)

        # Update friendly speed label
        ms = int(self.tick_var.get())
        if ms >= 220:
            label = "Very slow"
        elif ms >= 160:
            label = "Slow"
        elif ms >= 110:
            label = "Normal"
        elif ms >= 70:
            label = "Fast"
        else:
            label = "Very fast"
        self.speed_label.set(label)

        # Update status with live summary
        self.status_var.set(
            f"Map: {cols} × {rows} cells  |  Speed: {label}  |  Food changes every 10 score, colors every 30."
        )

    def _add_hover(self, button: ttk.Button) -> None:
        def on_enter(_e: tk.Event) -> None:
            button.configure(style="Accent.TButton")

        def on_leave(_e: tk.Event) -> None:
            button.configure(style="TButton")

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)


class EndView(tk.Frame):
    def __init__(self, parent: tk.Misc, app: "App") -> None:
        super().__init__(parent, padx=18, pady=18)
        self.app = app
        self.title_var = tk.StringVar(value="")
        self.subtitle_var = tk.StringVar(value="")

        title = tk.Label(self, textvariable=self.title_var, font=("Segoe UI", 34, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        subtitle = tk.Label(self, textvariable=self.subtitle_var, font=("Segoe UI", 14))
        subtitle.pack(anchor="w", pady=(0, 18))

        btns = tk.Frame(self)
        btns.pack(fill="x")
        btns.grid_columnconfigure(0, weight=1)

        play_again = ttk.Button(btns, text="Play again", command=self.app.start_game)
        play_again.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(btns, text="Main menu", command=lambda: self.app.show_menu(last_score=self.app.last_score)).grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        ttk.Button(btns, text="Quit", command=self.app.quit).grid(row=0, column=2, sticky="ew")

        hint = tk.Label(self, text="Tip: use Main menu to customize colors and map size.", font=("Segoe UI", 10), fg="#bbbbbb")
        hint.pack(anchor="w", pady=(14, 0))

        play_again.focus_set()

    def set_result(self, won: bool, score: int) -> None:
        if won:
            self.title_var.set("WINNER WINNER\nCHICKEN DINNER")
            self.subtitle_var.set(f"You filled the whole map!  Score: {score}\nStart again or go to Main menu?")
        else:
            self.title_var.set("GAME OVER")
            self.subtitle_var.set(f"Score: {score}\nStart again or go to Main menu?")


class App:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Snake Game")
        self.root.resizable(False, False)
        try:
            style = ttk.Style()
            style.theme_use("clam")
            # Accent style used for hover feedback
            style.configure("Accent.TButton")
        except tk.TclError:
            pass

        self.settings = GameSettings()
        self.container = tk.Frame(self.root)
        self.container.pack()

        self.menu = MenuView(self.container, self, self.settings)
        self.game: GameView | None = None
        self.end = EndView(self.container, self)
        self.last_score: int = 0
        self.show_menu(last_score=None)

    def quit(self) -> None:
        self.root.destroy()
        raise SystemExit(0)

    def show_menu(self, last_score: int | None) -> None:
        if self.game is not None:
            self.game.destroy()
            self.game = None
        self.end.pack_forget()
        self.menu.set_last_score(last_score)
        self.menu.pack(fill="both", expand=True)
        self.root.geometry("")  # shrink-wrap

    def start_game(self) -> None:
        self.end.pack_forget()
        self.menu.pack_forget()
        self.game = GameView(self.container, self, self.settings)
        self.game.pack()
        self.root.geometry("")
        self.game.start()

    def show_end(self, won: bool, score: int) -> None:
        self.last_score = int(score)
        if self.game is not None:
            self.game.destroy()
            self.game = None
        self.menu.pack_forget()
        self.end.set_result(won=won, score=self.last_score)
        self.end.pack(fill="both", expand=True)
        self.root.geometry("")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    try:
        App().run()
    except SystemExit:
        sys.exit(0)