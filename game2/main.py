import json
import os
import random
import sys
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.graphics import Color, Ellipse, Rectangle, Line, InstructionGroup
from kivy.properties import NumericProperty
from kivy.core.audio import SoundLoader

# On phones/tablets Kivy already sizes the window to the real device
# resolution, so we must never force a fixed pixel size there - doing so
# was the cause of the game rendering into a tiny corner (or being
# clipped) on real hardware. The forced size is only useful for desktop
# testing, where there is no "real" screen size to respect.
IS_MOBILE = platform in ('android', 'ios')
if not IS_MOBILE:
    Window.size = (390, 844)
    Window.minimum_width, Window.minimum_height = (320, 560)

Window.clearcolor = (0.02, 0.04, 0.08, 1)


def get_game_font():
    """Look for a bundled font first; fall back to Kivy's built-in
    cross-platform default instead of Windows-only fonts (which don't
    exist on Android/iOS and used to silently break custom text)."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, 'COMIC.TTF'),
        os.path.join(base_dir, 'comic.ttf'),
        os.path.join(base_dir, 'Comic.ttf'),
    ]
    if sys.platform.startswith('win'):
        candidates += [
            r'C:\Windows\Fonts\comic.ttf',
            r'C:\Windows\Fonts\comicbd.ttf',
            r'C:\Windows\Fonts\comici.ttf',
            r'C:\Windows\Fonts\Comic Sans MS.ttf',
            r'C:\Windows\Fonts\Comic Sans MS Bold.ttf',
        ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return 'Roboto'  # Kivy's bundled default font - works on every platform


def format_number(value):
    """Human-readable short form for click counts, e.g. 1234567 -> '1.23M'.
    Falls back to plain digits under 1,000 so small numbers stay exact."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return str(value)
    sign = '-' if value < 0 else ''
    value = abs(value)
    if value < 1000:
        return f'{sign}{value}'
    for threshold, suffix in (
        (1_000_000_000_000, 'T'),
        (1_000_000_000, 'B'),
        (1_000_000, 'M'),
        (1_000, 'K'),
    ):
        if value >= threshold:
            scaled = value / threshold
            text = f'{scaled:.2f}'.rstrip('0').rstrip('.')
            return f'{sign}{text}{suffix}'
    return f'{sign}{value}'


def format_duration(total_seconds):
    """Human-readable playtime, e.g. 3725 -> '1h 2m'."""
    total_seconds = max(0, int(total_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f'{hours}h {minutes}m'
    if minutes > 0:
        return f'{minutes}m {seconds}s'
    return f'{seconds}s'


class IntroScreen(Screen):
    loading_progress = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = RelativeLayout()

        self.title = Label(
            text='a normal clicker game',
            font_size=sp(32),
            bold=True,
            color=(1, 1, 1, 0),
            font_name=get_game_font(),
            pos_hint={'center_x': 0.5, 'center_y': 0.56},
        )
        layout.add_widget(self.title)

        self.loading_label = Label(
            text='loading...',
            font_size=sp(13),
            color=(0.6, 0.75, 0.95, 0),
            font_name=get_game_font(),
            pos_hint={'center_x': 0.5, 'center_y': 0.47},
        )
        layout.add_widget(self.loading_label)

        self.loading_track = Widget(
            size_hint=(None, None),
            size=(dp(200), dp(6)),
            pos_hint={'center_x': 0.5, 'center_y': 0.42},
        )
        with self.loading_track.canvas:
            Color(1, 1, 1, 0.12)
            self._loading_track_rect = Rectangle(pos=self.loading_track.pos, size=self.loading_track.size)
            Color(0.28, 0.78, 1, 0.9)
            self._loading_fill_rect = Rectangle(pos=self.loading_track.pos, size=(0, dp(6)))
        self.loading_track.bind(pos=self._update_loading_track, size=self._update_loading_track)
        self.bind(loading_progress=self._on_loading_progress)
        layout.add_widget(self.loading_track)

        self.add_widget(layout)

    def _update_loading_track(self, *args):
        self._loading_track_rect.pos = self.loading_track.pos
        self._loading_track_rect.size = self.loading_track.size
        self._on_loading_progress(self, self.loading_progress)

    def _on_loading_progress(self, instance, value):
        self._loading_fill_rect.pos = self.loading_track.pos
        self._loading_fill_rect.size = (self.loading_track.width * value, dp(6))

    def on_enter(self):
        self.loading_progress = 0.0
        Animation(color=(1, 1, 1, 1), duration=0.5).start(self.title)
        Animation(color=(0.6, 0.75, 0.95, 1), duration=0.5).start(self.loading_label)

        bar_anim = Animation(loading_progress=1.0, duration=1.4, t='out_quad')
        bar_anim.bind(on_complete=self.go_to_game)
        bar_anim.start(self)

    def go_to_game(self, *args):
        if self.manager:
            self.manager.current = 'game'


class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # user_data_dir is a writable, per-app folder on every platform.
        # The old path (next to main.py) breaks on Android, where the app's
        # install folder is read-only, so saving would silently fail there.
        app = App.get_running_app()
        data_dir = app.user_data_dir if app is not None else os.path.dirname(os.path.abspath(__file__))
        os.makedirs(data_dir, exist_ok=True)
        self.save_path = os.path.join(data_dir, 'save_data.json')
        self.milestone_thresholds = [10, 50, 100, 200, 500, 1000, 5000, 10000, 15000, 20000, 30000, 40000, 50000, 75000, 100000, 250000, 500000, 1000000, 5000000, 10000000, 25000000, 50000000, 100000000, 250000000, 500000000, 1000000000, 2500000000, 5000000000, 10000000000]
        self.milestone_messages = {
            10: 'wow nice your at 10',
            50: 'hey half way..... to 100....',
            100: 'hey atleast your not half way anymore',
            200: 'the button is officially scared of you',
            500: 'you won 500!.. nothing!',
            1000: '1k and still no prizes. this is a scam',
            5000: 'half way there version 2.0',
            10000: 'try doing something else. like breathing',
            15000: 'im starting to think that your becoming insane',
            20000: '....20k how wow.... you need to get out of here',
            30000: 'bro 30k is okay but you need to stop',
            40000: 'you should stop here. but you wont',
            50000: '50k!! holy you should touch grass',
            75000: 'i said touch grass not your screen',
            100000: 'at this point you should be in a mental hospital',
            250000: 'click more i dare you',
            500000: 'half a mill.. you just wish this was money',
            1000000: 'WOW thats like a lottory win. but its not money',
            5000000: 'im still not giving you anything',
            10000000: 'you should get a job. this is not a hobby',
            25000000: '25 million and the button is now afraid that your hurting him',
            50000000: 'button is now hurting and thinking it will file a case on you',
            100000000: 'you are now in court with the button. he is suing you for hurting him',
            250000000: '250 million. the button is now in the hospital. you should be too',
            500000000: '500 million. the button is now dead and you still want to click it',
            1000000000: '1 billion you know your closer to your goal now',
            2500000000: '2.5 billion alright....... a few more billion',
            5000000000: '5 billion. half way there 3.0',
            10000000000: 'you are now the concept of boredom. GET A LIFE'
        }
        self.milestones_unlocked = []
        self.click_count = 0
        self.clicks_per_tap = 1
        self.upgrade_level = 0
        self.auto_click_level = 0
        self.auto_click_rate = 0
        self.server_mining_level = 0
        self.mining_efficiency = 0
        self.overclock_level = 0
        self.cooling_level = 0
        self.psu_boost_level = 0
        self.ram_boost_level = 0
        self.gpu_boost_level = 0
        self.network_level = 0
        self.cache_level = 0
        self.core_level = 0
        self.server_online = False

        self.combo_streak = 0
        self.last_tap_time = 0.0
        self.combo_boost_level = 0
        self.daily_chest_last_claim = 0
        self.stock_prices = {'NEXUS': 100, 'VOLT': 140, 'BYTE': 180}
        self.stock_holdings = {'NEXUS': 0, 'VOLT': 0, 'BYTE': 0}
        self.roulette_level = 0
        self.firewall_level = 0
        self.overdrive_until = 0.0
        self.energy_cache = 0
        self.auto_repair_level = 0
        self.rare_drop_level = 0
        self.offline_bonus_total = 0
        self.highest_click_count = 0
        self.best_combo_streak = 0
        self.hack_battles_won = 0
        self.total_playtime_seconds = 0
        self.last_seen_time = time.time()
        self.sound_enabled = True
        self.music_enabled = True
        # Background music playlist - drop music1.ogg and music2.ogg next to
        # main.py and they'll be picked up and looped automatically. OGG is
        # used instead of mp3 for more reliable playback across Kivy's audio
        # backends on Android.
        self.music_tracks = ['music1.ogg', 'music2.ogg']
        self.music_track_index = 0
        self.music_sound = None
        self._pending_offline_popup = 0

        self.hacked_event_active = False
        self.hacked_event_overlay = None
        self.hacked_event_label = None
        self.hack_battle_active = False
        self.hack_battle_overlay = None
        self.hack_battle_label = None
        self.hack_battle_status = None
        self.hack_battle_target = 0
        self.hack_battle_progress = 0
        self.hack_steal_clock = None
        self._hacked_event_timer = None
        self._hacked_battle_clear_timer = None
        # Hacked event chances (reduced to 2%)
        self.hack_event_chance_per_click = 0.02
        self.hack_event_chance_per_tick = 0.02
        self.rank_tiers = [
            'Bronze I', 'Bronze II', 'Bronze III', 'Bronze IV', 'Bronze V',
            'Silver I', 'Silver II', 'Silver III', 'Silver IV', 'Silver V',
            'Gold I', 'Gold II', 'Gold III', 'Gold IV', 'Gold V',
            'Platinum I', 'Platinum II', 'Platinum III', 'Platinum IV', 'Platinum V',
            'Diamond I', 'Diamond II', 'Diamond III', 'Diamond IV', 'Diamond V',
            'Obsidian I', 'Obsidian II', 'Obsidian III', 'Obsidian IV', 'Obsidian V',
        ]
        # Clicks needed (all-time high, never derank) to reach each tier above.
        # Index 0 lines up with 'Bronze I' (free starting rank); the last
        # entry is the Obsidian V cap at 150 million clicks.
        self.rank_thresholds = [
            0, 1000, 5000, 15000, 40000,
            100000, 250000, 500000, 1000000, 2000000,
            4000000, 7000000, 11000000, 16000000, 22000000,
            30000000, 40000000, 52000000, 66000000, 82000000,
            100000000, 110000000, 120000000, 130000000, 140000000,
            143000000, 146000000, 148000000, 149000000, 150000000,
        ]
        self.server_parts = {
            'CPU': [
                {'name': 'Pentium G6400', 'cost': 350, 'power': 30, 'socket': 'LGA1200', 'tdp': 65},
                {'name': 'Core i3-12100F', 'cost': 950, 'power': 70, 'socket': 'LGA1700', 'tdp': 60},
                {'name': 'Core i5-12400F', 'cost': 1800, 'power': 120, 'socket': 'LGA1700', 'tdp': 65},
                {'name': 'Core i5-12600K', 'cost': 2600, 'power': 180, 'socket': 'LGA1700', 'tdp': 125},
                {'name': 'Ryzen 5 5600', 'cost': 1600, 'power': 90, 'socket': 'AM4', 'tdp': 65},
                {'name': 'Ryzen 5 7600X', 'cost': 2850, 'power': 170, 'socket': 'AM5', 'tdp': 105},
                {'name': 'Ryzen 7 5700X', 'cost': 2800, 'power': 165, 'socket': 'AM4', 'tdp': 65},
                {'name': 'Ryzen 7 7700X', 'cost': 4200, 'power': 240, 'socket': 'AM5', 'tdp': 105},
                {'name': 'Core i7-12700K', 'cost': 3500, 'power': 220, 'socket': 'LGA1700', 'tdp': 125},
                {'name': 'Core i7-13700K', 'cost': 5200, 'power': 300, 'socket': 'LGA1700', 'tdp': 125},
                {'name': 'Ryzen 9 5900X', 'cost': 5000, 'power': 270, 'socket': 'AM4', 'tdp': 105},
                {'name': 'Ryzen 9 7900X', 'cost': 6800, 'power': 360, 'socket': 'AM5', 'tdp': 170},
                {'name': 'Core i9-12900K', 'cost': 6200, 'power': 340, 'socket': 'LGA1700', 'tdp': 241},
                {'name': 'Core i9-13900K', 'cost': 9800, 'power': 520, 'socket': 'LGA1700', 'tdp': 253},
                {'name': 'Ryzen 9 7950X', 'cost': 10000, 'power': 510, 'socket': 'AM5', 'tdp': 170},
                {'name': 'Ryzen 9 9950X', 'cost': 14000, 'power': 650, 'socket': 'AM5', 'tdp': 170},
            ],
            'Motherboard': [
                {'name': 'H610', 'cost': 500, 'power': 18, 'socket': 'LGA1700', 'memory_generation': 'DDR4', 'form_factor': 'Micro-ATX'},
                {'name': 'B560', 'cost': 550, 'power': 20, 'socket': 'LGA1200', 'memory_generation': 'DDR4', 'form_factor': 'ATX'},
                {'name': 'B660', 'cost': 700, 'power': 30, 'socket': 'LGA1700', 'memory_generation': 'DDR4', 'form_factor': 'ATX'},
                {'name': 'Z790', 'cost': 1500, 'power': 60, 'socket': 'LGA1700', 'memory_generation': 'DDR5', 'form_factor': 'ATX'},
                {'name': 'B550', 'cost': 600, 'power': 25, 'socket': 'AM4', 'memory_generation': 'DDR4', 'form_factor': 'ATX'},
                {'name': 'X570', 'cost': 1200, 'power': 45, 'socket': 'AM4', 'memory_generation': 'DDR4', 'form_factor': 'ATX'},
                {'name': 'B650', 'cost': 900, 'power': 40, 'socket': 'AM5', 'memory_generation': 'DDR5', 'form_factor': 'ATX'},
                {'name': 'X670', 'cost': 1800, 'power': 80, 'socket': 'AM5', 'memory_generation': 'DDR5', 'form_factor': 'ATX'},
            ],
            'RAM': [
                {'name': '16GB DDR4-3200', 'cost': 200, 'power': 25, 'generation': 'DDR4', 'capacity': 16, 'speed': 3200},
                {'name': '32GB DDR4-3600', 'cost': 400, 'power': 45, 'generation': 'DDR4', 'capacity': 32, 'speed': 3600},
                {'name': '32GB DDR4-4800', 'cost': 550, 'power': 60, 'generation': 'DDR4', 'capacity': 32, 'speed': 4800},
                {'name': '32GB DDR5-6000', 'cost': 700, 'power': 70, 'generation': 'DDR5', 'capacity': 32, 'speed': 6000},
                {'name': '64GB DDR5-6000', 'cost': 1500, 'power': 120, 'generation': 'DDR5', 'capacity': 64, 'speed': 6000},
                {'name': '64GB DDR5-6400', 'cost': 1900, 'power': 150, 'generation': 'DDR5', 'capacity': 64, 'speed': 6400},
            ],
            'GPU': [
                {'name': 'GTX 1650 Super', 'cost': 1400, 'power': 110, 'vram': 4, 'length': 180, 'power_draw': 100},
                {'name': 'GTX 1660 Super', 'cost': 1700, 'power': 140, 'vram': 6, 'length': 200, 'power_draw': 125},
                {'name': 'GTX 1660 Ti', 'cost': 1900, 'power': 155, 'vram': 6, 'length': 200, 'power_draw': 130},
                {'name': 'RTX 2060 6GB', 'cost': 2100, 'power': 180, 'vram': 6, 'length': 205, 'power_draw': 160},
                {'name': 'RTX 3060 12GB', 'cost': 2200, 'power': 200, 'vram': 12, 'length': 210, 'power_draw': 170},
                {'name': 'RTX 3060 Ti 8GB', 'cost': 2600, 'power': 230, 'vram': 8, 'length': 215, 'power_draw': 200},
                {'name': 'RX 6700 XT 12GB', 'cost': 2700, 'power': 220, 'vram': 12, 'length': 220, 'power_draw': 230},
                {'name': 'RTX 3070 8GB', 'cost': 3200, 'power': 260, 'vram': 8, 'length': 230, 'power_draw': 220},
                {'name': 'RTX 3070 Ti 8GB', 'cost': 3600, 'power': 290, 'vram': 8, 'length': 232, 'power_draw': 240},
                {'name': 'RTX 4070 12GB', 'cost': 5400, 'power': 390, 'vram': 12, 'length': 240, 'power_draw': 200},
                {'name': 'RTX 4070 Super 12GB', 'cost': 6200, 'power': 430, 'vram': 12, 'length': 245, 'power_draw': 220},
                {'name': 'RX 7800 XT 16GB', 'cost': 5500, 'power': 430, 'vram': 16, 'length': 245, 'power_draw': 263},
                {'name': 'RTX 4080 16GB', 'cost': 8500, 'power': 590, 'vram': 16, 'length': 255, 'power_draw': 320},
                {'name': 'RTX 4090 24GB', 'cost': 12000, 'power': 760, 'vram': 24, 'length': 268, 'power_draw': 450},
                {'name': 'RX 7900 XT 20GB', 'cost': 9800, 'power': 680, 'vram': 20, 'length': 267, 'power_draw': 315},
                {'name': 'RX 7900 XTX 24GB', 'cost': 11000, 'power': 720, 'vram': 24, 'length': 270, 'power_draw': 355},
            ],
            'PSU': [
                {'name': '550W Bronze', 'cost': 200, 'power': 20, 'watts': 550},
                {'name': '650W Gold', 'cost': 360, 'power': 35, 'watts': 650},
                {'name': '750W Gold', 'cost': 550, 'power': 55, 'watts': 750},
                {'name': '850W Gold', 'cost': 800, 'power': 75, 'watts': 850},
                {'name': '1000W Platinum', 'cost': 1100, 'power': 90, 'watts': 1000},
                {'name': '1200W Titanium', 'cost': 1500, 'power': 110, 'watts': 1200},
                {'name': '1500W Titanium', 'cost': 2100, 'power': 140, 'watts': 1500},
            ],
            'Case': [
                {'name': 'Mini-ITX Case', 'cost': 220, 'power': 15, 'supports': ['Mini-ITX'], 'gpu_max_length': 180, 'psu_max_length': 140},
                {'name': 'Micro-ATX Case', 'cost': 250, 'power': 20, 'supports': ['Micro-ATX', 'Mini-ITX'], 'gpu_max_length': 220, 'psu_max_length': 170},
                {'name': 'ATX Case', 'cost': 450, 'power': 40, 'supports': ['ATX', 'Micro-ATX', 'Mini-ITX'], 'gpu_max_length': 330, 'psu_max_length': 190},
                {'name': 'E-ATX Tower', 'cost': 700, 'power': 65, 'supports': ['ATX', 'Micro-ATX', 'Mini-ITX'], 'gpu_max_length': 380, 'psu_max_length': 220},
                {'name': 'Workstation Case', 'cost': 950, 'power': 90, 'supports': ['ATX', 'Micro-ATX', 'Mini-ITX'], 'gpu_max_length': 420, 'psu_max_length': 240},
            ],
        }
        self.server_build = {category: None for category in self.server_parts}
        self.load_progress()
        self.init_music()

        self.root = RelativeLayout()
        root = self.root

        # Full-bleed background that always tracks the real screen size,
        # instead of a hardcoded 390x844 rect that used to leave the rest
        # of the screen blank/uncovered on other device resolutions.
        with root.canvas.before:
            Color(0.02, 0.04, 0.08, 1)
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
            Color(0.08, 0.14, 0.20, 1)
            self._bg_top_strip = Rectangle(pos=(root.x, root.top - dp(102)), size=(root.width, dp(102)))
        root.bind(pos=self._update_background, size=self._update_background)

        self.top_bar = BoxLayout(size_hint=(1, None), height=dp(62), padding=[dp(12), dp(10), dp(12), dp(8)], pos_hint={'top': 1})
        self._bind_rect_to_widget(self.top_bar, 'top_bar_bg_rect', (0.07, 0.12, 0.17, 1))
        root.add_widget(self.top_bar)

        self.click_label = Label(
            text=f'clicks : {self.click_count}',
            font_size=sp(24),
            bold=True,
            color=(0.86, 0.95, 1, 1),
            font_name=get_game_font(),
            pos_hint={'center_x': 0.5, 'center_y': 0.83},
            size_hint=(None, None),
            size=(dp(200), dp(34)),
        )
        root.add_widget(self.click_label)

        self.rank_badge = Button(
            text=self.get_rank_name(),
            font_size=sp(12),
            bold=True,
            color=(0.92, 0.78, 0.35, 1),
            font_name=get_game_font(),
            pos_hint={'center_x': 0.5, 'center_y': 0.74},
            size_hint=(None, None),
            size=(dp(120), dp(22)),
            background_normal='',
            background_down='',
            background_color=(0, 0, 0, 0),
        )
        self.rank_badge.bind(on_press=self.show_rank_info)
        root.add_widget(self.rank_badge)

        self.settings_button = Button(
            text='⚙',
            font_size=sp(22),
            bold=True,
            font_name=get_game_font(),
            size_hint=(None, None),
            size=(dp(34), dp(34)),
            pos_hint={'right': 0.96, 'top': 0.96},
            background_normal='',
            background_down='',
            background_color=(0.10, 0.16, 0.25, 1),
        )
        self.settings_button.bind(on_press=self.open_settings_menu)

        self.button = Button(
            text='CLICK ME',
            font_size=sp(28),
            bold=True,
            font_name=get_game_font(),
            size_hint=(None, None),
            size=(dp(200), dp(200)),
            pos_hint={'center_x': 0.5, 'center_y': 0.43},
            background_normal='',
            background_down='',
            background_color=(0, 0, 0, 0),
        )
        self.button.bind(on_press=self.on_click)

        with self.button.canvas.before:
            Color(0.08, 0.45, 1, 1)
            self.circle = Ellipse(size=(dp(200), dp(200)), pos=self.button.pos)

        with self.button.canvas:
            Color(0.28, 0.78, 1, 0.22)
            self.glow = Ellipse(size=(dp(260), dp(260)), pos=(self.button.center_x - 130, self.button.center_y - 130))

        self.button.bind(pos=self.update_circle, size=self.update_circle)

        self.milestone_button = Button(
            text='MILESTONE',
            font_size=sp(14),
            bold=True,
            font_name=get_game_font(),
            color=(0.92, 0.96, 1, 1),
            size_hint=(None, None),
            size=(dp(122), dp(38)),
            pos_hint={'x': 0.045, 'y': 0.02},
            background_normal='',
            background_down='',
            background_color=(0.13, 0.18, 0.26, 1),
        )
        self._bind_rect_to_widget(self.milestone_button, 'milestone_button_bg_rect', (0.12, 0.18, 0.28, 1))
        self.milestone_button.bind(on_press=self.show_milestones)
        self.milestone_button.bind(pos=self.update_milestone_button_bg, size=self.update_milestone_button_bg)

        self.server_button = Button(
            text='SERVER',
            font_size=sp(14),
            bold=True,
            font_name=get_game_font(),
            color=(0.92, 0.96, 1, 1),
            size_hint=(None, None),
            size=(dp(104), dp(38)),
            pos_hint={'center_x': 0.5, 'y': 0.02},
            background_normal='',
            background_down='',
            background_color=(0.15, 0.23, 0.32, 1),
        )
        self._bind_rect_to_widget(self.server_button, 'server_button_bg_rect', (0.15, 0.23, 0.32, 1))
        self.server_button.bind(on_press=self.show_server_builder)
        self.server_button.bind(pos=self.update_server_button_bg, size=self.update_server_button_bg)

        self.upgrades_button = Button(
            text='UPGRADES',
            font_size=sp(14),
            bold=True,
            font_name=get_game_font(),
            color=(0.92, 0.96, 1, 1),
            size_hint=(None, None),
            size=(dp(122), dp(38)),
            pos_hint={'right': 0.955, 'y': 0.02},
            background_normal='',
            background_down='',
            background_color=(0.13, 0.18, 0.26, 1),
        )
        self._bind_rect_to_widget(self.upgrades_button, 'upgrades_button_bg_rect', (0.13, 0.18, 0.26, 1))
        self.upgrades_button.bind(on_press=self.show_upgrades)
        self.upgrades_button.bind(pos=self.update_upgrades_button_bg, size=self.update_upgrades_button_bg)

        # Rank is now shown via the tappable rank_badge near the top of the
        # HUD (see above) instead of a bottom-row button, so it no longer
        # overlaps the UPGRADES button down here.

        root.add_widget(self.settings_button)
        root.add_widget(self.button)
        root.add_widget(self.milestone_button)
        root.add_widget(self.server_button)
        root.add_widget(self.upgrades_button)
        self.add_widget(root)
        Window.bind(on_keyboard=self._on_keyboard)

    def _on_keyboard(self, window, key, scancode, codepoint, modifiers):
        key_char = codepoint.lower() if codepoint else ''
        if key_char == 'h':
            if self.server_online and self.is_server_build_compatible():
                self.trigger_hacked_event()
            return True
        return False

    def load_progress(self):
        if not os.path.exists(self.save_path):
            self.click_count = 0
            self.milestones_unlocked = []
            self.clicks_per_tap = 1
            self.upgrade_level = 0
            self.auto_click_level = 0
            self.auto_click_rate = 0
            self.server_mining_level = 0
            self.mining_efficiency = 0
            self.overclock_level = 0
            self.cooling_level = 0
            self.psu_boost_level = 0
            self.ram_boost_level = 0
            self.gpu_boost_level = 0
            self.network_level = 0
            self.cache_level = 0
            self.core_level = 0
            self.server_online = False
            self.highest_click_count = 0
            self.best_combo_streak = 0
            self.hack_battles_won = 0
            self.total_playtime_seconds = 0
            return

        try:
            with open(self.save_path, 'r', encoding='utf-8') as save_file:
                data = json.load(save_file)
            self.click_count = int(data.get('click_count', 0))
            unlocked = data.get('milestones_unlocked', [])
            self.milestones_unlocked = [int(value) for value in unlocked if int(value) in self.milestone_messages]
            self.upgrade_level = int(data.get('upgrade_level', 0))
            self.clicks_per_tap = max(1, int(data.get('clicks_per_tap', 1)))
            self.auto_click_level = int(data.get('auto_click_level', 0))
            self.auto_click_rate = int(data.get('auto_click_rate', 0))
            self.server_mining_level = int(data.get('server_mining_level', 0))
            self.mining_efficiency = int(data.get('mining_efficiency', 0))
            self.overclock_level = int(data.get('overclock_level', 0))
            self.cooling_level = int(data.get('cooling_level', 0))
            self.psu_boost_level = int(data.get('psu_boost_level', 0))
            self.ram_boost_level = int(data.get('ram_boost_level', 0))
            self.gpu_boost_level = int(data.get('gpu_boost_level', 0))
            self.network_level = int(data.get('network_level', 0))
            self.cache_level = int(data.get('cache_level', 0))
            self.core_level = int(data.get('core_level', 0))
            self.server_online = bool(data.get('server_online', False))
            self.combo_streak = int(data.get('combo_streak', 0))
            self.last_tap_time = float(data.get('last_tap_time', 0.0))
            self.combo_boost_level = int(data.get('combo_boost_level', 0))
            self.daily_chest_last_claim = float(data.get('daily_chest_last_claim', 0))
            self.stock_prices = data.get('stock_prices', {'NEXUS': 100, 'VOLT': 140, 'BYTE': 180})
            self.stock_holdings = data.get('stock_holdings', {'NEXUS': 0, 'VOLT': 0, 'BYTE': 0})
            self.roulette_level = int(data.get('roulette_level', 0))
            self.firewall_level = int(data.get('firewall_level', 0))
            self.overdrive_until = float(data.get('overdrive_until', 0.0))
            self.energy_cache = int(data.get('energy_cache', 0))
            self.auto_repair_level = int(data.get('auto_repair_level', 0))
            self.rare_drop_level = int(data.get('rare_drop_level', 0))
            self.offline_bonus_total = int(data.get('offline_bonus_total', 0))
            self.highest_click_count = int(data.get('highest_click_count', self.click_count))
            self.best_combo_streak = int(data.get('best_combo_streak', 0))
            self.hack_battles_won = int(data.get('hack_battles_won', 0))
            self.total_playtime_seconds = int(data.get('total_playtime_seconds', 0))
            self.last_seen_time = float(data.get('last_seen_time', time.time()))
            self.sound_enabled = bool(data.get('sound_enabled', True))
            self.music_enabled = bool(data.get('music_enabled', True))
            raw_build = data.get('server_build', {})
            for category, parts in self.server_parts.items():
                part_name = raw_build.get(category)
                if part_name is None:
                    self.server_build[category] = None
                    continue
                found = next((part for part in parts if part['name'] == part_name), None)
                self.server_build[category] = found
            self.apply_offline_gain()
            # rank is a one-way, all-time-high tracker - make sure it accounts
            # for anything the offline gain above just added
            self.highest_click_count = max(self.highest_click_count, self.click_count)
        except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
            self.click_count = 0
            self.milestones_unlocked = []
            self.clicks_per_tap = 1
            self.upgrade_level = 0
            self.auto_click_level = 0
            self.auto_click_rate = 0
            self.server_mining_level = 0
            self.mining_efficiency = 0
            self.overclock_level = 0
            self.cooling_level = 0
            self.psu_boost_level = 0
            self.ram_boost_level = 0
            self.gpu_boost_level = 0
            self.network_level = 0
            self.cache_level = 0
            self.core_level = 0
            self.server_online = False
            self.combo_streak = 0
            self.last_tap_time = 0.0
            self.combo_boost_level = 0
            self.daily_chest_last_claim = 0
            self.stock_prices = {'NEXUS': 100, 'VOLT': 140, 'BYTE': 180}
            self.stock_holdings = {'NEXUS': 0, 'VOLT': 0, 'BYTE': 0}
            self.roulette_level = 0
            self.firewall_level = 0
            self.overdrive_until = 0.0
            self.energy_cache = 0
            self.auto_repair_level = 0
            self.rare_drop_level = 0
            self.offline_bonus_total = 0
            self.highest_click_count = 0
            self.last_seen_time = time.time()
            self.server_build = {category: None for category in self.server_parts}

    def save_progress(self):
        self.last_seen_time = time.time()
        payload = {
            'click_count': self.click_count,
            'milestones_unlocked': self.milestones_unlocked,
            'upgrade_level': self.upgrade_level,
            'clicks_per_tap': self.clicks_per_tap,
            'auto_click_level': self.auto_click_level,
            'auto_click_rate': self.auto_click_rate,
            'server_mining_level': self.server_mining_level,
            'mining_efficiency': self.mining_efficiency,
            'overclock_level': self.overclock_level,
            'cooling_level': self.cooling_level,
            'psu_boost_level': self.psu_boost_level,
            'ram_boost_level': self.ram_boost_level,
            'gpu_boost_level': self.gpu_boost_level,
            'network_level': self.network_level,
            'cache_level': self.cache_level,
            'core_level': self.core_level,
            'server_online': self.server_online,
            'combo_streak': self.combo_streak,
            'last_tap_time': self.last_tap_time,
            'combo_boost_level': self.combo_boost_level,
            'daily_chest_last_claim': self.daily_chest_last_claim,
            'stock_prices': self.stock_prices,
            'stock_holdings': self.stock_holdings,
            'roulette_level': self.roulette_level,
            'firewall_level': self.firewall_level,
            'overdrive_until': self.overdrive_until,
            'energy_cache': self.energy_cache,
            'auto_repair_level': self.auto_repair_level,
            'rare_drop_level': self.rare_drop_level,
            'offline_bonus_total': self.offline_bonus_total,
            'highest_click_count': self.highest_click_count,
            'last_seen_time': self.last_seen_time,
            'sound_enabled': self.sound_enabled,
            'music_enabled': self.music_enabled,
            'server_build': {category: part['name'] if part else None for category, part in self.server_build.items()},
        }
        with open(self.save_path, 'w', encoding='utf-8') as save_file:
            json.dump(payload, save_file)

    def get_music_path(self, filename):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, filename)

    def init_music(self):
        # Placeholder playlist - drop music1.ogg and music2.ogg in the same
        # folder as main.py. Missing files are handled quietly (SoundLoader
        # just returns None), so the game runs fine without them too.
        if not self.music_enabled:
            return
        self.play_music_track(self.music_track_index)

    def play_music_track(self, index):
        if not self.music_tracks:
            return
        if self.music_sound is not None:
            self.music_sound.unbind(on_stop=self._on_music_track_end)
            self.music_sound.stop()
            self.music_sound = None

        self.music_track_index = index % len(self.music_tracks)
        track_path = self.get_music_path(self.music_tracks[self.music_track_index])
        if not os.path.isfile(track_path):
            return

        sound = SoundLoader.load(track_path)
        if sound is None:
            return
        sound.volume = 0.5
        sound.bind(on_stop=self._on_music_track_end)
        sound.play()
        self.music_sound = sound

    def _on_music_track_end(self, instance):
        # Advance to the next track and loop the playlist. Guard against
        # stop() (called when toggling music off) re-triggering this.
        if not self.music_enabled or self.music_sound is not instance:
            return
        Clock.schedule_once(lambda dt: self.play_music_track(self.music_track_index + 1), 0.1)

    def stop_music(self):
        if self.music_sound is not None:
            self.music_sound.unbind(on_stop=self._on_music_track_end)
            self.music_sound.stop()
            self.music_sound = None

    def toggle_music(self, enabled):
        self.music_enabled = enabled
        if enabled:
            self.play_music_track(self.music_track_index)
        else:
            self.stop_music()
        self.save_progress()

    def play_ui_sound(self, kind='tap'):
        # winsound only exists (and only makes sense) on Windows desktop.
        # Guarding on sys.platform up front avoids a pointless import
        # attempt on every tap on Android/iOS/macOS/Linux.
        if not self.sound_enabled or not sys.platform.startswith('win'):
            return
        try:
            import winsound
            tones = {
                'tap': [(640, 40), (820, 35)],
                'upgrade': [(420, 60), (620, 40), (820, 50)],
                'server': [(240, 80), (520, 60), (760, 70)],
                'reset': [(180, 80), (120, 120)],
            }
            for frequency, duration in tones.get(kind, tones['tap']):
                winsound.Beep(frequency, duration)
        except Exception:
            pass

    def _update_hacked_rects(self, instance, value):
        if hasattr(self, 'hacked_event_black_rect') and self.hacked_event_black_rect is not None:
            self.hacked_event_black_rect.pos = instance.pos
            self.hacked_event_black_rect.size = instance.size
        if hasattr(self, 'hacked_event_red_rect') and self.hacked_event_red_rect is not None:
            self.hacked_event_red_rect.pos = instance.pos
            self.hacked_event_red_rect.size = instance.size

    def _update_background(self, *args):
        root = self.root
        self._bg_rect.pos = root.pos
        self._bg_rect.size = root.size
        self._bg_top_strip.pos = (root.x, root.top - dp(102))
        self._bg_top_strip.size = (root.width, dp(102))

    def _bind_rect_to_widget(self, widget, rect_attr, color):
        with widget.canvas.before:
            Color(*color)
            rect = Rectangle(pos=widget.pos, size=widget.size)
            setattr(self, rect_attr, rect)

        def update_rect(instance, value):
            if hasattr(self, rect_attr):
                rect_obj = getattr(self, rect_attr)
                rect_obj.pos = instance.pos
                rect_obj.size = instance.size

        widget.bind(pos=update_rect, size=update_rect)

    def trigger_hacked_event(self, *args):
        if not self.server_online or not self.is_server_build_compatible():
            return
        if self.hacked_event_active or self.hack_battle_active or self.hacked_event_overlay is not None:
            return
        if self._hacked_event_timer is not None:
            self._hacked_event_timer.cancel()
            self._hacked_event_timer = None

        self.hacked_event_active = True
        self.play_ui_sound('server')

        overlay = RelativeLayout(size_hint=(1, 1), opacity=0)
        black = Widget(size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})
        self._bind_rect_to_widget(black, 'hacked_event_black_rect', (0, 0, 0, 0.92))

        red = Widget(size_hint=(1, 1), pos_hint={'x': 0, 'y': 0}, opacity=0.0)
        self._bind_rect_to_widget(red, 'hacked_event_red_rect', (0.80, 0.10, 0.12, 0.35))

        label = Label(
            text='',
            font_name=get_game_font(),
            font_size=sp(54),
            bold=True,
            halign='center',
            valign='middle',
            color=(1.0, 0.22, 0.22, 1),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            size_hint=(None, None),
            size=(dp(250), dp(80)),
        )

        overlay.add_widget(black)
        overlay.add_widget(red)
        overlay.add_widget(label)
        self.root.add_widget(overlay)
        self.hacked_event_overlay = overlay
        self.hacked_event_label = label

        overlay.opacity = 1
        black.opacity = 1
        red.opacity = 1

        reveal_anim = Animation(opacity=1, duration=0.18)
        reveal_anim.start(overlay)

        red_anim = Animation(opacity=0.12, duration=0.08) + Animation(opacity=0.82, duration=0.12) + Animation(opacity=0.25, duration=0.1)
        red_anim.start(red)

        message = 'HACKED'
        for index, char in enumerate(message):
            Clock.schedule_once(lambda dt, i=index, c=char: self._advance_hacked_text(i, c, message), 0.05 * index)

        if self._hacked_event_timer is not None:
            self._hacked_event_timer.cancel()
        self._hacked_event_timer = Clock.schedule_once(self._finish_hacked_event, 1.7)

    def _advance_hacked_text(self, index, char, full_message):
        if self.hacked_event_overlay is None or self.hacked_event_label is None:
            return

        glitch_text = []
        for i in range(len(full_message)):
            if i < index:
                glitch_text.append(full_message[i])
            elif i == index:
                glitch_text.append(char)
            else:
                glitch_text.append(random.choice(['#', '@', 'H', 'A', 'C', 'K', 'E', 'D', '0', '1']))

        if random.random() < 0.35:
            glitch_index = random.randint(0, len(full_message) - 1)
            glitch_text[glitch_index] = random.choice(['#', '@', 'H', 'A', 'C', 'K', 'E', 'D', '0', '1'])

        self.hacked_event_label.text = ''.join(glitch_text)

        if index == len(full_message) - 1:
            self.hacked_event_label.text = full_message
            self.hacked_event_label.color = (0.95, 0.3, 0.3, 1)

    def _finish_hacked_event(self, dt):
        self._hacked_event_timer = None
        if self.hacked_event_overlay is None:
            self.hacked_event_active = False
            self._start_hack_battle()
            return

        fade_out = Animation(opacity=0, duration=0.35)
        fade_out.bind(on_complete=self._start_hack_battle)
        fade_out.start(self.hacked_event_overlay)
        self.hacked_event_active = False

    def _start_hack_battle(self, *args):
        if self.hacked_event_overlay is not None and self.hacked_event_overlay.parent is not None:
            self.root.remove_widget(self.hacked_event_overlay)
        self.hacked_event_overlay = None
        self.hacked_event_label = None

        if self.hack_battle_active or self.hack_battle_overlay is not None:
            return
        if self.hack_steal_clock is not None:
            self.hack_steal_clock.cancel()
            self.hack_steal_clock = None

        self.hack_battle_target = random.randint(200, 500)
        self.hack_battle_progress = 0
        self.hack_battle_active = True

        overlay = RelativeLayout(size_hint=(1, 1), opacity=0)
        black = Widget(size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})
        self._bind_rect_to_widget(black, 'hack_battle_black_rect', (0, 0, 0, 0.8))

        top_banner = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            size=(dp(330), dp(180)),
            pos_hint={'center_x': 0.5, 'center_y': 0.72},
            spacing=dp(8),
            padding=[dp(12), dp(12), dp(12), dp(12)],
        )
        self._bind_rect_to_widget(top_banner, 'hack_battle_banner_rect', (0.18, 0.04, 0.06, 0.82))

        title = Label(
            text='HACKER ATTACK',
            font_name=get_game_font(),
            font_size=sp(24),
            bold=True,
            color=(0.98, 0.42, 0.42, 1),
            size_hint_y=None,
            height=dp(28),
        )
        target = Label(
            text=f'CLICK {self.hack_battle_target} MORE\nTO FIGHT BACK',
            font_name=get_game_font(),
            font_size=sp(28),
            bold=True,
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle',
            text_size=(dp(300), None),
            size_hint_y=None,
            height=dp(86),
        )
        status = Label(
            text='Hackers are stealing your clicks...',
            font_name=get_game_font(),
            font_size=sp(16),
            color=(0.9, 0.8, 0.8, 1),
            size_hint_y=None,
            height=dp(22),
        )
        top_banner.add_widget(title)
        top_banner.add_widget(target)
        top_banner.add_widget(status)

        full = Button(
            text=' ',
            background_normal='',
            background_down='',
            background_color=(0, 0, 0, 0),
            size_hint=(1, 1),
        )
        full.bind(on_press=self._attack_hacker_click)

        overlay.add_widget(black)
        overlay.add_widget(full)
        overlay.add_widget(top_banner)
        self.root.add_widget(overlay)
        self.hack_battle_overlay = overlay
        self.hack_battle_label = target
        self.hack_battle_status = status

        Animation(opacity=1, duration=0.35).start(overlay)
        self.hack_steal_clock = Clock.schedule_interval(self._hack_click_steal, 1.0)

    def _hack_click_steal(self, dt):
        if not self.hack_battle_active or self.hack_battle_overlay is None:
            if self.hack_steal_clock is not None:
                self.hack_steal_clock.cancel()
                self.hack_steal_clock = None
            return

        stolen = random.randint(25, 150)
        reduction = self.get_hack_steal_reduction()
        stolen = max(0, stolen - reduction)
        self.click_count = max(0, self.click_count - stolen)
        self.refresh_click_label()
        self.hack_battle_status.text = f'Hackers stole {stolen} clicks!'
        self.save_progress()

    def _attack_hacker_click(self, instance):
        if not self.hack_battle_active:
            return

        attack_power = self.get_hack_attack_power()
        self.hack_battle_progress += attack_power
        remaining = max(self.hack_battle_target - self.hack_battle_progress, 0)
        if remaining <= 0:
            self.hack_battle_label.text = 'CLICK 0 MORE\nTO FIGHT BACK'
        else:
            self.hack_battle_label.text = f'CLICK {remaining} MORE\nTO FIGHT BACK'
        self.hack_battle_status.text = f'Fighting back... {self.hack_battle_progress}/{self.hack_battle_target} (x{attack_power})'

        if self.hack_battle_progress >= self.hack_battle_target:
            self.hack_battle_active = False
            if self.hack_steal_clock is not None:
                self.hack_steal_clock.cancel()
                self.hack_steal_clock = None
            self.click_count += random.randint(200, 900)
            self.refresh_click_label()
            self.update_rank_progress()
            self.hack_battles_won += 1
            self.hack_battle_status.text = 'Attack blocked. You held the line.'
            self.play_ui_sound('upgrade')
            self.check_milestones()
            self.save_progress()
            if self.hack_battle_overlay is not None and self.hack_battle_overlay.parent is not None:
                Animation(opacity=0, duration=0.35).start(self.hack_battle_overlay)
                if self._hacked_battle_clear_timer is not None:
                    self._hacked_battle_clear_timer.cancel()
                self._hacked_battle_clear_timer = Clock.schedule_once(self._clear_hack_battle_overlay, 0.4)

    def _clear_hack_battle_overlay(self, dt):
        self._hacked_battle_clear_timer = None
        if self.hack_battle_overlay is not None and self.hack_battle_overlay.parent is not None:
            self.root.remove_widget(self.hack_battle_overlay)
        self.hack_battle_overlay = None
        self.hack_battle_label = None
        self.hack_battle_status = None
        self.hack_battle_active = False
        self.hack_battle_target = 0
        self.hack_battle_progress = 0

    def check_milestones(self):
        unlocked_now = []
        for milestone in self.milestone_thresholds:
            if self.click_count >= milestone and milestone not in self.milestones_unlocked:
                self.milestones_unlocked.append(milestone)
                unlocked_now.append(milestone)
        for milestone in unlocked_now:
            self.show_achievement(milestone)
        if unlocked_now:
            self.save_progress()

    def _show_toast(self, title_text, body_text, title_color=(0.82, 0.96, 1, 1)):
        """Generic slide-down/slide-up toast panel used for achievements
        and the welcome-back popup. Width is clamped to the actual window
        width so it never clips off the edge of narrower phone screens."""
        if hasattr(self, 'achievement_widget') and self.achievement_widget is not None:
            self.root.remove_widget(self.achievement_widget)
            self.achievement_widget = None

        panel_width = min(dp(340), Window.width - dp(24))
        panel = BoxLayout(
            orientation='vertical',
            padding=[dp(18), dp(14), dp(18), dp(14)],
            spacing=dp(8),
            size_hint=(None, None),
            size=(panel_width, dp(130)),
            pos_hint={}
        )
        self._bind_rect_to_widget(panel, '_toast_bg_rect', (0.07, 0.10, 0.15, 0.96))

        start_x = (Window.width - panel.width) / 2
        rest_y = Window.height - dp(170)
        off_y = Window.height + dp(40)

        title = Label(
            text=title_text,
            font_name=get_game_font(),
            font_size=sp(22),
            bold=True,
            color=title_color,
            size_hint_y=None,
            height=dp(26),
        )
        body = Label(
            text=body_text,
            font_name=get_game_font(),
            font_size=sp(18),
            halign='center',
            valign='middle',
            text_size=(panel_width - dp(40), None),
            size_hint_y=1,
        )
        panel.add_widget(title)
        panel.add_widget(body)

        self.achievement_widget = panel
        self.root.add_widget(panel)

        panel.opacity = 0
        panel.pos = (start_x, off_y)
        anim = Animation(opacity=1, duration=0.25, pos=(start_x, rest_y))
        anim += Animation(opacity=1, duration=4.0)
        anim += Animation(opacity=0, duration=0.45, pos=(start_x, off_y))
        anim.bind(on_complete=self._dismiss_achievement)
        anim.start(panel)

    def show_achievement(self, milestone):
        self._show_toast(
            'ACHIEVEMENT',
            f'{format_number(milestone)} clicks\n{self.milestone_messages.get(milestone, "you did it")}',
        )

    def show_welcome_back(self, offline_gain):
        self._show_toast(
            'WELCOME BACK',
            f'+{format_number(offline_gain)} clicks\nearned while you were away',
            title_color=(0.6, 0.95, 0.75, 1),
        )

    def _dismiss_achievement(self, *args):
        if hasattr(self, 'achievement_widget') and self.achievement_widget is not None:
            if self.root and self.achievement_widget in self.root.children:
                self.root.remove_widget(self.achievement_widget)
            self.achievement_widget = None

    def show_milestones(self, instance):
        modal = ModalView(size_hint=(0.9, None), height=dp(390), auto_dismiss=True)
        container = BoxLayout(orientation='vertical', padding=[dp(14), dp(14), dp(14), dp(14)], spacing=dp(10))
        self._bind_rect_to_widget(container, 'milestones_container_bg_rect', (0.12, 0.15, 0.20, 1))

        header = Label(
            text='MILESTONES',
            font_name=get_game_font(),
            font_size=sp(22),
            bold=True,
            color=(0.78, 0.92, 1, 1),
            size_hint_y=None,
            height=dp(30),
        )
        container.add_widget(header)

        divider = BoxLayout(size_hint_y=None, height=dp(2))
        self._bind_rect_to_widget(divider, 'milestone_divider_bg_rect', (0.50, 0.54, 0.60, 0.8))
        container.add_widget(divider)

        rows = BoxLayout(orientation='vertical', spacing=dp(8), size_hint_y=None)
        rows.bind(minimum_height=rows.setter('height'))

        for milestone in self.milestone_thresholds:
            row = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(34), padding=[dp(4), dp(0), dp(4), dp(0)])
            self._bind_rect_to_widget(row, f'milestone_row_bg_{len(rows.children)}', (0.10, 0.13, 0.17, 1))

            value = Label(
                text=format_number(milestone),
                font_name=get_game_font(),
                font_size=sp(17),
                bold=True,
                color=(0.93, 0.97, 1, 1),
                halign='left',
                valign='middle',
                size_hint_x=0.28,
            )

            if self.click_count >= milestone:
                progress_value = 100.0
                percent_text = '100%'
                bar_color = (0.38, 0.88, 0.64, 1)
            else:
                progress_value = min((self.click_count / milestone) * 100.0, 100.0)
                percent_text = f'{progress_value:.0f}%'
                bar_color = (0.38, 0.74, 1, 1)

            progress_container = BoxLayout(size_hint_x=0.56, padding=[dp(0), dp(6), dp(0), dp(6)])
            progress = ProgressBar(max=100, value=progress_value, size_hint=(1, 1))
            progress.background_color = (0.18, 0.24, 0.33, 1)
            progress.color = bar_color
            progress_container.add_widget(progress)

            percent = Label(
                text=percent_text,
                font_name=get_game_font(),
                font_size=sp(15),
                bold=True,
                color=(0.8, 0.9, 1, 1),
                halign='right',
                valign='middle',
                size_hint_x=0.16,
            )

            row.add_widget(value)
            row.add_widget(progress_container)
            row.add_widget(percent)
            rows.add_widget(row)

        scroll = ScrollView(do_scroll_x=False, size_hint=(1, 1))
        scroll.add_widget(rows)
        container.add_widget(scroll)

        close_btn = Button(
            text='CLOSE',
            font_name=get_game_font(),
            font_size=sp(16),
            bold=True,
            size_hint_y=None,
            height=dp(36),
            background_normal='',
            background_down='',
            background_color=(0, 0, 0, 0),
        )
        self._bind_rect_to_widget(close_btn, 'milestone_close_button_bg_rect', (0.10, 0.14, 0.20, 1))
        close_btn.bind(on_press=modal.dismiss)
        container.add_widget(close_btn)
        modal.add_widget(container)
        modal.open()

    def make_menu_button(self, text, callback):
        button = Button(
            text=text,
            font_name=get_game_font(),
            font_size=sp(18),
            size_hint_y=None,
            height=dp(44),
            background_normal='',
            background_color=(0.12, 0.19, 0.31, 1),
        )
        button.bind(on_press=callback)
        return button

    def show_reset_confirmation(self, instance, *args):
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=[dp(18), dp(18), dp(18), dp(18)])

        title = Label(
            text='Confirm',
            font_name=get_game_font(),
            font_size=sp(22),
            bold=True,
            color=(0.75, 0.9, 1, 1),
            size_hint_y=None,
            height=dp(30),
        )
        content.add_widget(title)

        label = Label(
            text='Reset your save?',
            font_name=get_game_font(),
            font_size=sp(20),
            halign='center',
            valign='middle',
            size_hint_y=0.8,
        )
        label.text_size = (220, None)
        content.add_widget(label)

        buttons = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(12))
        modal = ModalView(size_hint=(0.9, None), height=dp(200), auto_dismiss=True)
        modal.add_widget(content)

        yes_btn = self.make_menu_button('Yes', lambda *_: (modal.dismiss(), self.show_final_reset_confirmation()))
        no_btn = self.make_menu_button('No', lambda *_: modal.dismiss())
        buttons.add_widget(yes_btn)
        buttons.add_widget(no_btn)
        content.add_widget(buttons)
        modal.open()

    def show_final_reset_confirmation(self):
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=[dp(18), dp(18), dp(18), dp(18)])

        title = Label(
            text='Final check',
            font_name=get_game_font(),
            font_size=sp(22),
            bold=True,
            color=(0.75, 0.9, 1, 1),
            size_hint_y=None,
            height=dp(30),
        )
        content.add_widget(title)

        label = Label(
            text='This will erase all progress.\nAre you absolutely sure?',
            font_name=get_game_font(),
            font_size=sp(18),
            halign='center',
            valign='middle',
            size_hint_y=0.9,
        )
        label.text_size = (240, None)
        content.add_widget(label)

        buttons = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(12))
        modal = ModalView(size_hint=(0.9, None), height=dp(220), auto_dismiss=True)
        modal.add_widget(content)

        yes_btn = self.make_menu_button('Yes, reset', lambda *_: (modal.dismiss(), self.reset_game_save()))
        no_btn = self.make_menu_button('Cancel', lambda *_: modal.dismiss())
        buttons.add_widget(yes_btn)
        buttons.add_widget(no_btn)
        content.add_widget(buttons)
        modal.open()

    def reset_game_save(self):
        self.click_count = 0
        self.milestones_unlocked = []
        self.clicks_per_tap = 1
        self.upgrade_level = 0
        self.auto_click_level = 0
        self.auto_click_rate = 0
        self.server_mining_level = 0
        self.mining_efficiency = 0
        self.overclock_level = 0
        self.cooling_level = 0
        self.psu_boost_level = 0
        self.ram_boost_level = 0
        self.gpu_boost_level = 0
        self.network_level = 0
        self.cache_level = 0
        self.core_level = 0
        self.server_online = False
        self.combo_streak = 0
        self.last_tap_time = 0.0
        self.combo_boost_level = 0
        self.daily_chest_last_claim = 0
        self.stock_prices = {'NEXUS': 100, 'VOLT': 140, 'BYTE': 180}
        self.stock_holdings = {'NEXUS': 0, 'VOLT': 0, 'BYTE': 0}
        self.roulette_level = 0
        self.firewall_level = 0
        self.overdrive_until = 0.0
        self.energy_cache = 0
        self.auto_repair_level = 0
        self.rare_drop_level = 0
        self.offline_bonus_total = 0
        self.server_build = {category: None for category in self.server_parts}
        self.click_label.text = 'clicks : 0'
        self.save_progress()

    def show_guide(self, instance, *args):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=[dp(14), dp(14), dp(14), dp(10)])

        title = Label(
            text='Guide',
            font_name=get_game_font(),
            font_size=sp(20),
            bold=True,
            color=(0.75, 0.9, 1, 1),
            size_hint_y=None,
            height=dp(26),
        )
        content.add_widget(title)

        guide_text = (
            "[b]The basics[/b]\n"
            "Tap the button to earn clicks. Spend clicks on UPGRADES to "
            "raise how much each tap and auto-click earns.\n\n"
            "[b]Rank[/b]\n"
            "Your rank (top of screen) rises with your all-time clicks and "
            "never goes down, even after you spend. Higher rank = a "
            "permanent bonus to every click. Tap it to see progress.\n\n"
            "[b]Server & hacks - read this one[/b]\n"
            "Building and booting a server (SERVER tab) boosts your "
            "income, but once it's online and compatible it can also get "
            "targeted by hacked events and hack battles that steal your "
            "clicks. [b]Don't rush a weak, early server online[/b] - a "
            "cheap build with no auto-repair or firewall upgrades gets "
            "hit hard and can set you back more than it earns. Build up "
            "some upgrades first, or invest in Firewall/Auto-Repair "
            "before booting.\n\n"
            "[b]Other tips[/b]\n"
            "- MILESTONE shows every click goal and its message.\n"
            "- Claim your daily chest and check the stock market and "
            "roulette for extra clicks.\n"
            "- Closing the app is safe - you'll get an offline bonus "
            "based on time away when you come back."
        )
        guide_label = Label(
            text=guide_text,
            font_name=get_game_font(),
            font_size=sp(13),
            color=(0.9, 0.95, 1, 1),
            markup=True,
            halign='left',
            valign='top',
            size_hint_y=None,
        )
        guide_label.bind(width=lambda inst, w: setattr(inst, 'text_size', (w, None)))
        guide_label.bind(texture_size=lambda inst, size: setattr(inst, 'height', size[1]))

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(guide_label)
        content.add_widget(scroll)

        modal = ModalView(size_hint=(0.92, 0.8), auto_dismiss=True)
        modal.add_widget(content)

        close_btn = self.make_menu_button('Close', lambda *_: modal.dismiss())
        content.add_widget(close_btn)
        modal.open()

    def show_credits(self, instance, *args):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=[dp(14), dp(14), dp(14), dp(14)])

        title = Label(
            text='Credits',
            font_name=get_game_font(),
            font_size=sp(20),
            bold=True,
            color=(0.75, 0.9, 1, 1),
            size_hint_y=None,
            height=dp(26),
        )
        content.add_widget(title)

        label = Label(
            text='Made by Iwodv',
            font_name=get_game_font(),
            font_size=sp(16),
            halign='center',
            valign='middle',
            size_hint_y=1,
        )
        label.text_size = (200, None)
        content.add_widget(label)

        modal = ModalView(size_hint=(0.9, None), height=dp(180), auto_dismiss=True)
        modal.add_widget(content)

        close_btn = self.make_menu_button('Close', lambda *_: modal.dismiss())
        content.add_widget(close_btn)
        modal.open()

    def buy_combo_boost(self, instance=None):
        cost = int(150 * (2 ** self.combo_boost_level))
        if self.click_count < cost:
            return False
        self.click_count -= cost
        self.combo_boost_level += 1
        self.refresh_click_label()
        self.save_progress()
        return True

    def claim_daily_chest(self, instance=None):
        now = time.time()
        if now - self.daily_chest_last_claim < 43200:
            return False
        reward = 150 + (self.upgrade_level * 35) + (self.server_mining_level * 25)
        self.click_count += reward
        self.daily_chest_last_claim = now
        self.refresh_click_label()
        self.update_rank_progress()
        self.check_milestones()
        self.save_progress()
        return True

    def update_stock_market(self):
        for key in self.stock_prices:
            drift = random.randint(-12, 12)
            self.stock_prices[key] = max(30, self.stock_prices[key] + drift)

    def buy_stock(self, symbol, instance=None):
        price = self.stock_prices.get(symbol, 100)
        if self.click_count < price:
            return False
        self.click_count -= price
        self.stock_holdings[symbol] = self.stock_holdings.get(symbol, 0) + 1
        self.refresh_click_label()
        self.save_progress()
        return True

    def sell_stock(self, symbol, instance=None):
        if self.stock_holdings.get(symbol, 0) <= 0:
            return False
        price = self.stock_prices.get(symbol, 100)
        self.click_count += price
        self.stock_holdings[symbol] -= 1
        self.refresh_click_label()
        self.update_rank_progress()
        self.check_milestones()
        self.save_progress()
        return True

    def spin_roulette(self, instance=None):
        cost = 250 + (self.roulette_level * 40)
        if self.click_count < cost:
            return False
        self.click_count -= cost
        roll = random.random()
        if roll < 0.35:
            reward = random.randint(250, 1200)
            self.click_count += reward
            self.refresh_click_label()
            self.update_rank_progress()
            self.check_milestones()
            self.save_progress()
            return True
        if roll < 0.7:
            self.click_count = max(0, self.click_count - random.randint(50, 250))
            self.refresh_click_label()
        else:
            self.click_count += random.randint(50, 200)
            self.refresh_click_label()
            self.update_rank_progress()
        self.save_progress()
        return True

    def buy_firewall(self, instance=None):
        cost = int(500 * (2 ** self.firewall_level))
        if self.click_count < cost:
            return False
        self.click_count -= cost
        self.firewall_level += 1
        self.refresh_click_label()
        self.save_progress()
        return True

    def activate_overdrive(self, instance=None):
        cost = 300
        if self.click_count < cost:
            return False
        self.click_count -= cost
        self.overdrive_until = time.time() + 12.0
        self.refresh_click_label()
        self.save_progress()
        return True

    def buy_auto_repair(self, instance=None):
        cost = int(600 * (2 ** self.auto_repair_level))
        if self.click_count < cost:
            return False
        self.click_count -= cost
        self.auto_repair_level += 1
        self.refresh_click_label()
        self.save_progress()
        return True

    def buy_rare_drop(self, instance=None):
        cost = int(700 * (2 ** self.rare_drop_level))
        if self.click_count < cost:
            return False
        self.click_count -= cost
        self.rare_drop_level += 1
        self.refresh_click_label()
        self.save_progress()
        return True

    def collect_energy(self, instance=None):
        if self.energy_cache <= 0:
            return False
        self.click_count += self.energy_cache
        self.energy_cache = 0
        self.refresh_click_label()
        self.update_rank_progress()
        self.check_milestones()
        self.save_progress()
        return True

    def get_combo_multiplier(self):
        now = time.time()
        if now - self.last_tap_time < 0.9:
            self.combo_streak += 1
        else:
            self.combo_streak = 1
        self.last_tap_time = now
        if self.combo_streak > self.best_combo_streak:
            self.best_combo_streak = self.combo_streak
        return 1 + min(5, self.combo_streak) * (0.15 + (self.combo_boost_level * 0.05))

    def apply_offline_gain(self):
        now = time.time()
        elapsed = max(0, now - self.last_seen_time)
        if elapsed <= 0:
            return 0
        offline_gain = int(elapsed / 20) + self.server_mining_level * 2
        if self.server_online and self.is_server_build_compatible():
            offline_gain += int(self.get_server_power_score() / 80)
        self.click_count += offline_gain
        self.offline_bonus_total = offline_gain
        self.last_seen_time = now
        self.save_progress()
        return offline_gain

    def get_rank_index(self):
        # Rank is earned by all-time clicks, not current balance, and it
        # only ever goes up - spending clicks on upgrades never deranks you.
        index = 0
        for i, threshold in enumerate(self.rank_thresholds):
            if self.highest_click_count >= threshold:
                index = i
            else:
                break
        return index

    def get_rank_name(self):
        return self.rank_tiers[self.get_rank_index()]

    def get_next_rank_requirement(self):
        # Clicks still needed (all-time) to reach the next rank, or None if
        # already at the top rank (Obsidian V, 150 million clicks).
        index = self.get_rank_index()
        if index >= len(self.rank_thresholds) - 1:
            return None
        return self.rank_thresholds[index + 1] - self.highest_click_count

    def get_rank_multiplier(self):
        # A small permanent bonus for climbing the ranks - 2% per tier, so
        # topping out at Obsidian V (index 29) gives a +58% click bonus.
        return 1.0 + (self.get_rank_index() * 0.02)

    def refresh_click_label(self):
        self.click_label.text = f'clicks : {format_number(self.click_count)}'

    def update_rank_progress(self):
        # Call whenever click_count changes - tracks the all-time high used
        # for ranking and refreshes the HUD badge if the rank just went up.
        if self.click_count > self.highest_click_count:
            self.highest_click_count = self.click_count
        self.rank_badge.text = self.get_rank_name()

    def show_rank_info(self, instance):
        modal = ModalView(size_hint=(0.9, None), height=dp(250), auto_dismiss=True)
        content = BoxLayout(orientation='vertical', spacing=dp(8), padding=[dp(14), dp(14), dp(14), dp(14)])
        self._bind_rect_to_widget(content, 'rank_bg_rect', (0.12, 0.16, 0.22, 1))

        title = Label(text='RANK', font_name=get_game_font(), font_size=sp(22), bold=True, color=(0.8, 0.95, 1, 1), size_hint_y=None, height=dp(28))
        rank = Label(text=f'Rank: {self.get_rank_name()}', font_name=get_game_font(), font_size=sp(16), bold=True, color=(0.92, 0.8, 0.42, 1), size_hint_y=None, height=dp(22))
        bonus_pct = round((self.get_rank_multiplier() - 1.0) * 100)
        bonus = Label(
            text=f'+{bonus_pct}% clicks from rank',
            font_name=get_game_font(),
            font_size=sp(12),
            color=(0.6, 0.9, 0.7, 1),
            size_hint_y=None,
            height=dp(18),
        )
        remaining = self.get_next_rank_requirement()
        if remaining is None:
            status_text = 'Top rank reached - Obsidian V at 150M clicks'
        else:
            index = self.get_rank_index()
            next_name = self.rank_tiers[index + 1]
            status_text = f'{format_number(remaining)} more all-time clicks to rise to {next_name}'
        status = Label(
            text=status_text,
            font_name=get_game_font(),
            font_size=sp(12),
            color=(0.9, 0.97, 1, 1),
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(40),
        )

        close_btn = Button(
            text='CLOSE',
            font_name=get_game_font(),
            font_size=sp(13),
            bold=True,
            background_normal='',
            background_down='',
            background_color=(0.16, 0.20, 0.28, 1),
            size_hint_y=None,
            height=dp(30),
        )
        close_btn.bind(on_press=modal.dismiss)

        content.add_widget(title)
        content.add_widget(rank)
        content.add_widget(bonus)
        content.add_widget(status)
        content.add_widget(close_btn)
        modal.add_widget(content)
        modal.open()

    def get_extra_click_gain(self):
        extra = 0
        if self.server_online and self.is_server_build_compatible() and self.auto_repair_level > 0:
            extra += self.auto_repair_level
        if time.time() < self.overdrive_until:
            extra += self.auto_click_rate + self.server_mining_level
        if self.rare_drop_level > 0 and random.random() < 0.05 + (self.rare_drop_level * 0.02):
            extra += random.randint(10, 80)
        return extra

    def open_settings_menu(self, instance):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=[dp(14), dp(14), dp(14), dp(14)])

        title = Label(
            text='Settings',
            font_name=get_game_font(),
            font_size=sp(22),
            bold=True,
            color=(0.75, 0.9, 1, 1),
            size_hint_y=None,
            height=dp(28),
        )
        content.add_widget(title)

        menu = BoxLayout(orientation='vertical', spacing=dp(10))

        def toggle_sound(btn):
            self.sound_enabled = not self.sound_enabled
            btn.text = f'Sound: {"ON" if self.sound_enabled else "OFF"}'
            self.save_progress()

        def toggle_music(btn):
            self.toggle_music(not self.music_enabled)
            btn.text = f'Music: {"ON" if self.music_enabled else "OFF"}'

        sound_button = self.make_menu_button(
            f'Sound: {"ON" if self.sound_enabled else "OFF"}', lambda inst: toggle_sound(inst)
        )
        music_button = self.make_menu_button(
            f'Music: {"ON" if self.music_enabled else "OFF"}', lambda inst: toggle_music(inst)
        )
        reset_button = self.make_menu_button('Reset Save', self.show_reset_confirmation)
        guide_button = self.make_menu_button('Guide', self.show_guide)
        credits_button = self.make_menu_button('Credits', self.show_credits)
        menu.add_widget(sound_button)
        menu.add_widget(music_button)
        menu.add_widget(reset_button)
        menu.add_widget(guide_button)
        menu.add_widget(credits_button)

        close_button = self.make_menu_button('Close', lambda *_: modal.dismiss())
        menu.add_widget(close_button)
        content.add_widget(menu)

        modal = ModalView(size_hint=(0.9, None), height=dp(370), auto_dismiss=True)
        modal.add_widget(content)
        modal.open()

    def update_circle(self, instance, value):
        self.circle.pos = instance.pos
        self.circle.size = instance.size
        self.glow.pos = (instance.center_x - self.glow.size[0] / 2, instance.center_y - self.glow.size[1] / 2)

    def update_milestone_button_bg(self, instance, value):
        if hasattr(self, 'milestone_button_bg'):
            self.milestone_button_bg.pos = instance.pos
            self.milestone_button_bg.size = instance.size

    def update_upgrades_button_bg(self, instance, value):
        if hasattr(self, 'upgrades_button_bg'):
            self.upgrades_button_bg.pos = instance.pos
            self.upgrades_button_bg.size = instance.size

    def update_server_button_bg(self, instance, value):
        if hasattr(self, 'server_button_bg'):
            self.server_button_bg.pos = instance.pos
            self.server_button_bg.size = instance.size

    def get_server_power_score(self, build=None):
        if build is None:
            build = self.server_build
        total = 0
        for category, part in build.items():
            if part is None:
                continue
            total += part.get('power', 0)
        return total

    def is_server_build_compatible(self, build=None):
        if build is None:
            build = self.server_build
        for category, part in build.items():
            if part is None:
                return False

        cpu = build['CPU']
        motherboard = build['Motherboard']
        ram = build['RAM']
        gpu = build['GPU']
        psu = build['PSU']
        case = build['Case']

        if cpu['socket'] != motherboard['socket']:
            return False
        if ram['generation'] != motherboard['memory_generation']:
            return False
        if motherboard['form_factor'] not in case['supports']:
            return False
        if gpu['length'] > case['gpu_max_length']:
            return False

        total_wattage = cpu['tdp'] + gpu['power_draw'] + ram['capacity'] * 0.5 + 120
        if psu['watts'] < total_wattage:
            return False
        return True

    def get_server_status_text(self, build=None):
        if build is None:
            build = self.server_build
        if any(build[category] is None for category in build):
            return 'Missing parts'
        if self.is_server_build_compatible(build):
            return 'Build ready'
        if build['CPU']['socket'] != build['Motherboard']['socket']:
            return 'CPU socket mismatch'
        if build['RAM']['generation'] != build['Motherboard']['memory_generation']:
            return 'RAM and motherboard mismatch'
        if build['Motherboard']['form_factor'] not in build['Case']['supports']:
            return 'Board too big for case'
        if build['GPU']['length'] > build['Case']['gpu_max_length']:
            return 'GPU too long for case'
        if build['PSU']['watts'] < build['CPU']['tdp'] + build['GPU']['power_draw'] + 120:
            return 'PSU too weak'
        return 'Build invalid'

    def buy_server_part(self, category, part):
        cost = part['cost']
        if self.click_count < cost:
            return

        self.click_count -= cost
        self.server_build[category] = part
        self.refresh_click_label()
        self.save_progress()

    def get_click_upgrade_cost(self):
        return int(round(50 * (2 ** self.upgrade_level)))

    def get_auto_click_cost(self):
        return int(round(250 * (2 ** self.auto_click_level)))

    def get_server_mining_cost(self):
        return int(round(500 * (2 ** self.server_mining_level)))

    def get_mining_efficiency_cost(self):
        return int(round(900 * (2 ** self.mining_efficiency)))

    def get_overclock_cost(self):
        return int(round(950 * (2 ** self.overclock_level)))

    def get_cooling_cost(self):
        return int(round(1200 * (2 ** self.cooling_level)))

    def get_psu_boost_cost(self):
        return int(round(1350 * (2 ** self.psu_boost_level)))

    def get_ram_boost_cost(self):
        return int(round(1500 * (2 ** self.ram_boost_level)))

    def get_gpu_boost_cost(self):
        return int(round(1800 * (2 ** self.gpu_boost_level)))

    def get_network_cost(self):
        return int(round(1700 * (2 ** self.network_level)))

    def get_cache_cost(self):
        return int(round(1650 * (2 ** self.cache_level)))

    def get_core_cost(self):
        return int(round(2200 * (2 ** self.core_level)))

    def get_hack_attack_power(self):
        power = self.clicks_per_tap
        power += self.overclock_level
        power += self.ram_boost_level
        power += self.gpu_boost_level
        power += self.core_level
        power += self.psu_boost_level
        power += self.network_level
        power += self.cache_level
        power += self.server_mining_level
        power += self.mining_efficiency
        power += self.combo_boost_level
        power += self.firewall_level
        if self.server_online and self.is_server_build_compatible():
            power += 2 + (self.get_server_power_score() // 180)
        return max(1, power)

    def get_hack_steal_reduction(self):
        reduction = self.firewall_level * 12
        reduction += self.auto_repair_level * 8
        reduction += int(self.energy_cache / 10)
        return min(reduction, 80)

    def get_server_mining_reward(self):
        if not self.server_online:
            return 0
        if not self.is_server_build_compatible() or any(part is None for part in self.server_build.values()):
            return 0

        power = self.get_server_power_score()
        power += self.overclock_level * 15
        power += self.cooling_level * 10
        power += self.gpu_boost_level * 18
        power += self.ram_boost_level * 12
        power += self.network_level * 8
        power += self.cache_level * 9
        power += self.core_level * 20
        if power <= 0:
            return 0

        roll = random.random()
        base_chance = min(0.94, 0.18 + (power / 1800.0) + (self.server_mining_level * 0.08) + (self.mining_efficiency * 0.06))
        if roll > base_chance:
            return 0

        gain_floor = 1 + self.server_mining_level + self.mining_efficiency
        gain_ceiling = max(2, int(power / 22) + self.server_mining_level + self.mining_efficiency + self.gpu_boost_level)
        return random.randint(gain_floor, gain_ceiling)

    def show_server_builder(self, instance):
        modal = ModalView(size_hint=(1, 1), auto_dismiss=True)
        content = BoxLayout(orientation='vertical', padding=[dp(10), dp(10), dp(10), dp(10)], spacing=dp(6))
        self._bind_rect_to_widget(content, 'server_builder_content_bg_rect', (0.12, 0.15, 0.20, 1))

        header = Label(
            text='SERVER BUILDER',
            font_name=get_game_font(),
            font_size=sp(20),
            bold=True,
            color=(0.78, 0.92, 1, 1),
            size_hint_y=None,
            height=dp(26),
        )
        content.add_widget(header)

        summary = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(42))
        power = Label(
            text=f'Power Score: {self.get_server_power_score()}',
            font_name=get_game_font(),
            font_size=sp(13),
            color=(0.92, 0.97, 1, 1),
            size_hint_y=None,
            height=dp(18),
        )
        status = Label(
            text=self.get_server_status_text(),
            font_name=get_game_font(),
            font_size=sp(11),
            color=(0.75, 0.86, 1, 1),
            size_hint_y=None,
            height=dp(14),
        )
        summary.add_widget(power)
        summary.add_widget(status)
        content.add_widget(summary)

        boot_button = Button(
            text='BOOT SERVER' if not self.server_online else 'SHUTDOWN SERVER',
            font_name=get_game_font(),
            font_size=sp(13),
            bold=True,
            size_hint_y=None,
            height=dp(28),
            background_normal='',
            background_down='',
            background_color=(0.12, 0.62, 0.55, 1),
        )
        if not self.is_server_build_compatible():
            boot_button.disabled = True
            boot_button.opacity = 0.5
            boot_button.text = 'BUILD INCOMPLETE'
        boot_button.bind(on_press=self.toggle_server_boot)
        content.add_widget(boot_button)

        categories = ['CPU', 'Motherboard', 'RAM', 'GPU', 'PSU', 'Case']
        position_map = {
            'CPU': {'center_x': 0.5, 'center_y': 0.82},
            'Motherboard': {'center_x': 0.5, 'center_y': 0.5},
            'RAM': {'center_x': 0.28, 'center_y': 0.5},
            'GPU': {'center_x': 0.72, 'center_y': 0.5},
            'PSU': {'center_x': 0.3, 'center_y': 0.18},
            'Case': {'center_x': 0.7, 'center_y': 0.18},
        }
        selected_category = {'name': 'CPU'}

        tree = RelativeLayout(size_hint_y=0.58)
        tree_board = InstructionGroup()
        tree.canvas.before.add(tree_board)

        tree_tap = Button(
            text='',
            size_hint=(1, 1),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            background_normal='',
            background_down='',
            background_color=(0, 0, 0, 0),
        )
        tree_tap.bind(on_press=lambda instance: refresh_catalog())
        tree.add_widget(tree_tap)

        def set_selected_category(category):
            selected_category['name'] = category
            refresh_tree()
            refresh_catalog()

        def refresh_tree():
            for child in list(tree.children):
                if child is not tree_tap:
                    tree.remove_widget(child)

            target_points = {}
            for category in categories:
                if category == 'Motherboard':
                    continue
                part = self.server_build.get(category)
                slot = Button(
                    text=(part['name'] if part else category)[:13],
                    font_name=get_game_font(),
                    font_size=sp(10),
                    bold=True,
                    halign='center',
                    valign='middle',
                    size_hint=(None, None),
                    size=(dp(104), dp(42)),
                    pos_hint=position_map[category],
                    background_normal='',
                    background_down='',
                    background_color=(0.20, 0.28, 0.40, 1) if category != selected_category['name'] else (0.22, 0.60, 0.80, 1),
                )
                if part is not None:
                    slot.background_color = (0.18, 0.52, 0.42, 1)
                slot.bind(on_press=lambda instance, cat=category: set_selected_category(cat))
                tree.add_widget(slot)
                target_points[category] = slot.center_x, slot.center_y

            motherboard_slot = Button(
                text='Motherboard',
                font_name=get_game_font(),
                font_size=sp(12),
                bold=True,
                halign='center',
                valign='middle',
                size_hint=(None, None),
                size=(dp(150), dp(60)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5},
                background_normal='',
                background_down='',
                background_color=(0.19, 0.27, 0.38, 1),
            )
            motherboard_part = self.server_build.get('Motherboard')
            if motherboard_part is not None:
                motherboard_slot.text = motherboard_part['name']
                motherboard_slot.background_color = (0.18, 0.52, 0.42, 1)
            motherboard_slot.bind(on_press=lambda instance: set_selected_category('Motherboard'))
            tree.add_widget(motherboard_slot)

            tree_board.clear()
            tree_board.add(Color(0.18, 0.23, 0.31, 1))
            tree_board.add(Rectangle(pos=tree.pos, size=tree.size))
            tree_board.add(Color(0.42, 0.64, 0.82, 0.8))
            tree_board.add(Line(rectangle=(tree.x + 8, tree.y + 8, tree.width - 16, tree.height - 16), width=1.5))
            tree_board.add(Color(0.52, 0.82, 0.96, 0.7))
            for category, point in target_points.items():
                target_x, target_y = point
                board_x = motherboard_slot.center_x
                board_y = motherboard_slot.center_y
                tree_board.add(Line(points=[board_x, board_y, target_x, target_y], width=dp(2)))

        def refresh_catalog():
            for child in list(catalog.children):
                catalog.remove_widget(child)

            header_label = Label(
                text=f'{selected_category["name"]} PARTS',
                font_name=get_game_font(),
                font_size=sp(14),
                bold=True,
                color=(0.9, 0.97, 1, 1),
                size_hint_y=None,
                height=dp(22),
            )
            catalog.add_widget(header_label)

            for part in self.server_parts[selected_category['name']]:
                details = part['name']
                if selected_category['name'] == 'CPU':
                    details = f"{part['name']} | {part['socket']} | {part['tdp']}W"
                elif selected_category['name'] == 'Motherboard':
                    details = f"{part['name']} | {part['socket']} | {part['memory_generation']} | {part['form_factor']}"
                elif selected_category['name'] == 'RAM':
                    details = f"{part['name']} | {part['generation']} | {part['speed']}MHz"
                elif selected_category['name'] == 'GPU':
                    details = f"{part['name']} | {part['vram']}GB | {part['power_draw']}W"
                elif selected_category['name'] == 'PSU':
                    details = f"{part['name']} | {part['watts']}W"
                elif selected_category['name'] == 'Case':
                    details = f"{part['name']} | {part['gpu_max_length']}mm GPU"

                row = Button(
                    text=f'{details}\n{format_number(part["cost"])} clicks',
                    font_name=get_game_font(),
                    font_size=sp(9),
                    bold=True,
                    size_hint_y=None,
                    height=dp(46),
                    background_normal='',
                    background_down='',
                    background_color=(0.14, 0.20, 0.28, 1),
                )
                if self.server_build.get(selected_category['name']) == part:
                    row.background_color = (0.18, 0.58, 0.42, 1)

                def purchase(instance, p=part, c=selected_category['name']):
                    if self.click_count < p['cost']:
                        status.text = f'Need {format_number(p["cost"] - self.click_count)} more clicks'
                        return
                    self.click_count -= p['cost']
                    self.server_build[c] = p
                    self.refresh_click_label()
                    self.save_progress()
                    status.text = self.get_server_status_text()
                    power.text = f'Power Score: {self.get_server_power_score()}'
                    if self.is_server_build_compatible():
                        boot_button.disabled = False
                        boot_button.opacity = 1
                        boot_button.text = 'BOOT SERVER' if not self.server_online else 'SHUTDOWN SERVER'
                    else:
                        boot_button.disabled = True
                        boot_button.opacity = 0.5
                        boot_button.text = 'BUILD INCOMPLETE'
                    self.play_ui_sound('upgrade')
                    set_selected_category(c)

                row.bind(on_press=purchase)
                catalog.add_widget(row)

        content.add_widget(tree)

        catalog = BoxLayout(orientation='vertical', spacing=dp(6), size_hint_y=None)
        catalog.bind(minimum_height=catalog.setter('height'))

        scroll = ScrollView(do_scroll_x=False, size_hint=(1, 1), bar_width=3)
        scroll.add_widget(catalog)
        content.add_widget(scroll)

        refresh_tree()
        refresh_catalog()

        actions = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(8))
        close_btn = Button(
            text='CLOSE',
            font_name=get_game_font(),
            font_size=sp(13),
            bold=True,
            background_normal='',
            background_down='',
            background_color=(0.12, 0.18, 0.25, 1),
        )
        close_btn.bind(on_press=modal.dismiss)
        actions.add_widget(close_btn)
        content.add_widget(actions)

        modal.add_widget(content)
        modal.open()

    def toggle_server_boot(self, instance):
        if not self.is_server_build_compatible():
            return
        self.server_online = not self.server_online
        self.play_ui_sound('server')
        self.save_progress()
        if hasattr(instance, 'text'):
            instance.text = 'BOOT SERVER' if not self.server_online else 'SHUTDOWN SERVER'

    def show_upgrades(self, instance):
        modal = ModalView(size_hint=(0.9, None), height=dp(470), auto_dismiss=True)
        container = BoxLayout(orientation='vertical', padding=[dp(14), dp(14), dp(14), dp(14)], spacing=dp(8))
        self._bind_rect_to_widget(container, 'upgrade_modal_container_bg_rect', (0.12, 0.15, 0.20, 1))

        header = Label(
            text='UPGRADES',
            font_name=get_game_font(),
            font_size=sp(20),
            bold=True,
            color=(0.78, 0.92, 1, 1),
            size_hint_y=None,
            height=dp(28),
        )
        container.add_widget(header)

        upgrade_rows = [
            {'name': 'Clicks +1', 'level_attr': 'upgrade_level', 'cost_func': self.get_click_upgrade_cost, 'kind': 'click'},
            {'name': 'Auto Click +1', 'level_attr': 'auto_click_level', 'cost_func': self.get_auto_click_cost, 'kind': 'auto'},
            {'name': 'Mining Rig +1', 'level_attr': 'server_mining_level', 'cost_func': self.get_server_mining_cost, 'kind': 'mining'},
            {'name': 'Mining Eff +1', 'level_attr': 'mining_efficiency', 'cost_func': self.get_mining_efficiency_cost, 'kind': 'efficiency'},
            {'name': 'Overclock +1', 'level_attr': 'overclock_level', 'cost_func': self.get_overclock_cost, 'kind': 'overclock'},
            {'name': 'Cooling +1', 'level_attr': 'cooling_level', 'cost_func': self.get_cooling_cost, 'kind': 'cooling'},
            {'name': 'PSU Boost +1', 'level_attr': 'psu_boost_level', 'cost_func': self.get_psu_boost_cost, 'kind': 'psu'},
            {'name': 'RAM Boost +1', 'level_attr': 'ram_boost_level', 'cost_func': self.get_ram_boost_cost, 'kind': 'ram'},
            {'name': 'GPU Boost +1', 'level_attr': 'gpu_boost_level', 'cost_func': self.get_gpu_boost_cost, 'kind': 'gpu'},
            {'name': 'Network +1', 'level_attr': 'network_level', 'cost_func': self.get_network_cost, 'kind': 'network'},
            {'name': 'Cache +1', 'level_attr': 'cache_level', 'cost_func': self.get_cache_cost, 'kind': 'cache'},
            {'name': 'Core +1', 'level_attr': 'core_level', 'cost_func': self.get_core_cost, 'kind': 'core'},
        ]

        rows = BoxLayout(orientation='vertical', spacing=dp(6), size_hint_y=None)
        rows.bind(minimum_height=rows.setter('height'))

        def make_handler(kind_name):
            def handler(instance):
                if kind_name == 'click':
                    self.buy_click_upgrade(instance)
                elif kind_name == 'auto':
                    self.buy_auto_click_upgrade(instance)
                elif kind_name == 'mining':
                    self.buy_server_mining_upgrade(instance)
                elif kind_name == 'efficiency':
                    self.buy_mining_efficiency_upgrade(instance)
                elif kind_name == 'overclock':
                    self.buy_overclock_upgrade(instance)
                elif kind_name == 'cooling':
                    self.buy_cooling_upgrade(instance)
                elif kind_name == 'psu':
                    self.buy_psu_boost_upgrade(instance)
                elif kind_name == 'ram':
                    self.buy_ram_boost_upgrade(instance)
                elif kind_name == 'gpu':
                    self.buy_gpu_boost_upgrade(instance)
                elif kind_name == 'network':
                    self.buy_network_upgrade(instance)
                elif kind_name == 'cache':
                    self.buy_cache_upgrade(instance)
                elif kind_name == 'core':
                    self.buy_core_upgrade(instance)
                self.play_ui_sound('upgrade')
                modal.dismiss()
            return handler

        for upgrade in upgrade_rows:
            level_value = getattr(self, upgrade['level_attr'])
            cost = upgrade['cost_func']()
            row = BoxLayout(orientation='horizontal', spacing=dp(8), size_hint_y=None, height=dp(42), padding=[dp(6), dp(0), dp(6), dp(0)])
            self._bind_rect_to_widget(row, f'upgrade_row_bg_{len(rows.children)}', (0.10, 0.13, 0.17, 1))

            info = BoxLayout(orientation='vertical', size_hint_x=0.72)
            name_label = Label(
                text=upgrade['name'],
                font_name=get_game_font(),
                font_size=sp(12),
                bold=True,
                color=(0.93, 0.97, 1, 1),
                halign='left',
                valign='middle',
                size_hint_y=0.6,
            )
            cost_label = Label(
                text=f'Lvl {level_value} • {format_number(cost)} clicks',
                font_name=get_game_font(),
                font_size=sp(10),
                color=(0.75, 0.84, 0.98, 1),
                halign='left',
                valign='middle',
                size_hint_y=0.4,
            )
            info.add_widget(name_label)
            info.add_widget(cost_label)

            buy_btn = Button(
                text='BUY',
                font_name=get_game_font(),
                font_size=sp(12),
                bold=True,
                size_hint_x=0.28,
                background_normal='',
                background_down='',
                background_color=(0.12, 0.22, 0.38, 1),
            )
            if self.click_count < cost:
                buy_btn.disabled = True
                buy_btn.opacity = 0.5
            buy_btn.bind(on_press=make_handler(upgrade['kind']))
            row.add_widget(info)
            row.add_widget(buy_btn)
            rows.add_widget(row)

        scroll = ScrollView(do_scroll_x=False, size_hint=(1, 1), bar_width=3)
        scroll.add_widget(rows)
        container.add_widget(scroll)

        close_btn = Button(
            text='CLOSE',
            font_name=get_game_font(),
            font_size=sp(15),
            bold=True,
            size_hint_y=None,
            height=dp(30),
            background_normal='',
            background_down='',
            background_color=(0, 0, 0, 0),
        )
        self._bind_rect_to_widget(close_btn, 'upgrade_close_button_bg_rect', (0.10, 0.14, 0.20, 1))
        close_btn.bind(on_press=modal.dismiss)
        container.add_widget(close_btn)
        modal.add_widget(container)
        modal.open()

    def buy_click_upgrade(self, instance):
        cost = self.get_click_upgrade_cost()
        if self.click_count < cost:
            return

        self.click_count -= cost
        self.upgrade_level += 1
        self.clicks_per_tap += 1
        self.refresh_click_label()
        self.save_progress()

    def buy_auto_click_upgrade(self, instance):
        cost = self.get_auto_click_cost()
        if self.click_count < cost:
            return

        self.click_count -= cost
        self.auto_click_level += 1
        self.auto_click_rate += 1
        self.refresh_click_label()
        self.save_progress()

    def buy_server_mining_upgrade(self, instance):
        cost = self.get_server_mining_cost()
        if self.click_count < cost:
            return

        self.click_count -= cost
        self.server_mining_level += 1
        self.refresh_click_label()
        self.save_progress()

    def buy_mining_efficiency_upgrade(self, instance):
        cost = self.get_mining_efficiency_cost()
        if self.click_count < cost:
            return

        self.click_count -= cost
        self.mining_efficiency += 1
        self.refresh_click_label()
        self.save_progress()

    def buy_overclock_upgrade(self, instance):
        cost = self.get_overclock_cost()
        if self.click_count < cost:
            return
        self.click_count -= cost
        self.overclock_level += 1
        self.clicks_per_tap += 1
        self.refresh_click_label()
        self.save_progress()

    def buy_cooling_upgrade(self, instance):
        cost = self.get_cooling_cost()
        if self.click_count < cost:
            return
        self.click_count -= cost
        self.cooling_level += 1
        self.refresh_click_label()
        self.save_progress()

    def buy_psu_boost_upgrade(self, instance):
        cost = self.get_psu_boost_cost()
        if self.click_count < cost:
            return
        self.click_count -= cost
        self.psu_boost_level += 1
        self.auto_click_rate += 1
        self.refresh_click_label()
        self.save_progress()

    def buy_ram_boost_upgrade(self, instance):
        cost = self.get_ram_boost_cost()
        if self.click_count < cost:
            return
        self.click_count -= cost
        self.ram_boost_level += 1
        self.clicks_per_tap += 1
        self.refresh_click_label()
        self.save_progress()

    def buy_gpu_boost_upgrade(self, instance):
        cost = self.get_gpu_boost_cost()
        if self.click_count < cost:
            return
        self.click_count -= cost
        self.gpu_boost_level += 1
        self.server_mining_level += 1
        self.refresh_click_label()
        self.save_progress()

    def buy_network_upgrade(self, instance):
        cost = self.get_network_cost()
        if self.click_count < cost:
            return
        self.click_count -= cost
        self.network_level += 1
        self.auto_click_rate += 1
        self.refresh_click_label()
        self.save_progress()

    def buy_cache_upgrade(self, instance):
        cost = self.get_cache_cost()
        if self.click_count < cost:
            return
        self.click_count -= cost
        self.cache_level += 1
        self.mining_efficiency += 1
        self.refresh_click_label()
        self.save_progress()

    def buy_core_upgrade(self, instance):
        cost = self.get_core_cost()
        if self.click_count < cost:
            return
        self.click_count -= cost
        self.core_level += 1
        self.clicks_per_tap += 1
        self.server_mining_level += 1
        self.refresh_click_label()
        self.save_progress()

    def on_click(self, instance):
        combo_mult = self.get_combo_multiplier() if self.combo_boost_level > 0 else 1.0
        tap_gain = int(self.clicks_per_tap * combo_mult * self.get_rank_multiplier())
        tap_gain += self.get_extra_click_gain()
        self.click_count += tap_gain
        self.refresh_click_label()
        self.update_rank_progress()
        self.check_milestones()
        self.show_click_feedback(instance, tap_gain)
        if random.random() < self.hack_event_chance_per_click:
            self.trigger_hacked_event()
        self.save_progress()
        # Pop out then settle back to the resting size - previously this
        # animation grew the button and never shrank it back, so it got
        # permanently bigger after the very first tap.
        anim = (
            Animation(size=(dp(184), dp(184)), duration=0.05)
            + Animation(size=(dp(200), dp(200)), duration=0.08)
        )
        anim.start(instance)

    def show_click_feedback(self, instance, amount):
        # A little floating "+N" that pops off the click button and fades
        # away - purely cosmetic feedback so taps feel like they landed.
        if amount <= 0:
            return
        offset_x = random.uniform(-30, 30)
        popup = Label(
            text=f'+{format_number(amount)}',
            font_name=get_game_font(),
            font_size=sp(16),
            bold=True,
            color=(0.85, 0.95, 1, 1),
            size_hint=(None, None),
            size=(dp(80), dp(24)),
            pos=(instance.center_x - dp(40) + offset_x, instance.center_y + dp(60)),
        )
        self.add_widget(popup)
        anim = (
            Animation(pos=(popup.x, popup.y + dp(46)), opacity=1, duration=0.15)
            + Animation(pos=(popup.x, popup.y + dp(90)), opacity=0, duration=0.55)
        )
        popup.opacity = 0
        anim.bind(on_complete=lambda *_: self.remove_widget(popup))
        anim.start(popup)

    def add_auto_clicks(self, dt):
        self.total_playtime_seconds += 1
        rank_mult = self.get_rank_multiplier()
        if self.auto_click_rate > 0:
            self.click_count += int((self.auto_click_rate + self.get_extra_click_gain()) * rank_mult)
            self.refresh_click_label()
            self.update_rank_progress()
            self.check_milestones()

        mining_gain = self.get_server_mining_reward()
        if mining_gain > 0:
            self.click_count += int(mining_gain * rank_mult)
            self.refresh_click_label()
            self.update_rank_progress()
            self.check_milestones()

        if self.server_online and self.is_server_build_compatible() and random.random() < self.hack_event_chance_per_tick:
            self.trigger_hacked_event()

        self.save_progress()

    def on_enter(self):
        # Show the "while you were away" toast once, the first time the
        # player actually reaches the game screen (not on every re-enter).
        if not getattr(self, '_offline_popup_shown', False):
            self._offline_popup_shown = True
            if self.offline_bonus_total > 0:
                Clock.schedule_once(lambda dt: self.show_welcome_back(self.offline_bonus_total), 0.5)


class ClickerApp(App):
    # icon.jpg should sit in the same folder as main.py. This sets the
    # desktop window icon; for the actual Android app icon (home screen,
    # launcher), buildozer.spec's icon.filename also needs to point here -
    # see the note below the App if you're packaging with buildozer.
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.jpg')

    def build(self):
        self.title = 'a normal clicker game'
        Window.set_icon(self.icon)
        sm = ScreenManager(transition=FadeTransition())
        game_screen = GameScreen(name='game')
        sm.add_widget(IntroScreen(name='intro'))
        sm.add_widget(game_screen)
        Clock.schedule_interval(game_screen.add_auto_clicks, 1.0)
        return sm


if __name__ == '__main__':
    ClickerApp().run()
