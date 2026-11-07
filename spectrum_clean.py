import os
import sys
import time
import threading
import asyncio
import ctypes
import traceback
from ctypes import wintypes
from datetime import datetime
import numpy as np
from PyQt6 import QtWidgets, QtCore, QtGui, QtOpenGLWidgets
import pyaudiowpatch as pyaudio


def resource_path(rel):
    """通常実行・PyInstaller(onefile/onedir)の両方で同梱ファイルのパスを解決する。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)

# WinRT (GSMTC) 関連のインポート
try:
    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
    from winsdk.windows.storage.streams import DataReader
    WINSDK_AVAILABLE = True
except ImportError:
    WINSDK_AVAILABLE = False

# Windows Core Audio (音量・ミュート取得用)
try:
    import comtypes
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    PYCAW_AVAILABLE = True
except Exception:
    PYCAW_AVAILABLE = False


# ===== Win32 API (専用インスタンス: 他ライブラリの user32 に影響させない) =====
user32 = ctypes.WinDLL("user32", use_last_error=True)

user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    ctypes.c_void_p,  # hWndInsertAfter (64bitポインタ)
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]

try:
    GetWindowLongPtr = user32.GetWindowLongPtrW
except AttributeError:
    GetWindowLongPtr = user32.GetWindowLongW
GetWindowLongPtr.restype = ctypes.c_longlong
GetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int]

HWND_TOPMOST = ctypes.c_void_p(-1)
HWND_NOTOPMOST = ctypes.c_void_p(-2)
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008


# ===== パラメータ設定 =====
CFG_FFT_SIZE = 4096
CFG_SMOOTHING = 0.82
CFG_CORR_SMOOTHING = 0.85
CFG_FLOOR_DB = -140.0
CFG_PLOT_MIN_DB = -75.0
CFG_PLOT_MAX_DB = 0.0
CFG_SPECTROGRAM_HISTORY = 64
CFG_PEAK_DECAY_PER_SEC = 16.8
CFG_PEAK_GATE_DB = -90.0

SMOOTHING_REF_DT = 1.0 / 60.0
SILENCE_TIMEOUT = 0.15
RESCAN_AFTER = 3.0
RESCAN_INTERVAL = 5.0

BASE_W = 640
BASE_H = 360

PAD_L = 28
PAD_R = 10
PAD_T = 6
PAD_B = 16

BIN_COUNT = CFG_FFT_SIZE // 2
LOG_MIN = np.log10(20)
LOG_MAX = np.log10(20000)

GRID_DB = [0, -10, -20, -30, -40, -50, -60, -70]
GRID_HZ = [
    (30, '30'), (60, '60'), (125, '125'), (250, '250'),
    (500, '500'), (1000, '1k'), (2000, '2k'), (4000, '4k'),
    (8000, '8k'), (16000, '16k')
]

# ===== カラーテーマ定義 =====
COLOR_THEMES = [
    {
        "name": "Cyberpunk Cyan",
        "primary": QtGui.QColor("#00ffcc"),
        "secondary": QtGui.QColor("#1db954"),
        "grad_mid": QtGui.QColor(29, 185, 84, 89),
        "grad_top": QtGui.QColor(0, 255, 204, 191),
        "lut_fn": lambda t: np.column_stack([
            np.clip(t * 255.0, 0, 255),
            np.clip(t * 180.0, 0, 255),
            np.clip((1.0 - t) * 200.0 * t, 0, 255)
        ]).astype(np.uint8)
    },
    {
        "name": "Neon Magenta",
        "primary": QtGui.QColor("#ff007f"),
        "secondary": QtGui.QColor("#9900ff"),
        "grad_mid": QtGui.QColor(153, 0, 255, 89),
        "grad_top": QtGui.QColor(255, 0, 127, 191),
        "lut_fn": lambda t: np.column_stack([
            np.clip(t * 255.0, 0, 255),
            np.clip((t ** 2) * 50.0, 0, 255),    # 無音時は0(黒)、大音量ピーク時だけほんのり白く光る
            np.clip(t * 220.0, 0, 255)
        ]).astype(np.uint8)
    },
    {
        "name": "Amber Gold",
        "primary": QtGui.QColor("#ffaa00"),
        "secondary": QtGui.QColor("#ff5500"),
        "grad_mid": QtGui.QColor(255, 85, 0, 89),
        "grad_top": QtGui.QColor(255, 170, 0, 191),
        "lut_fn": lambda t: np.column_stack([
            np.clip(t * 255.0, 0, 255),
            np.clip(t * 130.0, 0, 255),
            np.zeros_like(t)
        ]).astype(np.uint8)
    },
    {
        "name": "Matrix Green",
        "primary": QtGui.QColor("#00ff44"),
        "secondary": QtGui.QColor("#008822"),
        "grad_mid": QtGui.QColor(0, 136, 34, 89),
        "grad_top": QtGui.QColor(0, 255, 68, 191),
        "lut_fn": lambda t: np.column_stack([
            np.zeros_like(t),
            np.clip(t * 255.0, 0, 255),
            np.clip(t * 40.0, 0, 255)
        ]).astype(np.uint8)
    },
    {
        "name": "Ice White",
        "primary": QtGui.QColor("#ffffff"),
        "secondary": QtGui.QColor("#00aaff"),
        "grad_mid": QtGui.QColor(0, 170, 255, 89),
        "grad_top": QtGui.QColor(255, 255, 255, 191),
        "lut_fn": lambda t: np.column_stack([
            np.clip(t * 200.0, 0, 255),
            np.clip(t * 230.0, 0, 255),
            np.clip(t * 255.0, 0, 255)
        ]).astype(np.uint8)
    }
]


# ==============================================================================
# メディア監視 ＆ コントロールワーカー（GSMTC）
# ==============================================================================
class MediaWatcher(QtCore.QObject):
    media_changed = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._running = True
        self._thread = None
        self._last_track_id = ""
        self._cached_thumb_bytes = None
        self._cached_thumb_size = 0
        self._thumb_check_retries = 0
        self._loop = None
        self._manager = None
        self._session = None
        if WINSDK_AVAILABLE:
            self._thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._thread.start()

    def _worker_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        while self._running:
            try:
                if self._manager is None:
                    self._manager = self._loop.run_until_complete(MediaManager.request_async())
                data = self._loop.run_until_complete(self._fetch_media())
                self.media_changed.emit(data or {})
            except Exception:
                self._manager = None
                self._session = None
                self.media_changed.emit({})
            time.sleep(0.5)
        self._loop.close()

    async def _fetch_media(self):
        if not self._manager:
            return None
        session = self._manager.get_current_session()
        self._session = session
        if not session:
            self._last_track_id = ""
            self._cached_thumb_bytes = None
            self._cached_thumb_size = 0
            self._thumb_check_retries = 0
            return None

        source_app = ""
        try:
            app_id = session.source_app_user_model_id or ""
            if app_id:
                clean_name = app_id.split("!")[-1].split(".exe")[0].split("_")[0]
                source_app = clean_name.capitalize()
        except Exception:
            pass

        status_text = "PLAYING"
        try:
            playback_info = session.get_playback_info()
            if playback_info:
                if playback_info.playback_status == PlaybackStatus.PAUSED:
                    status_text = "PAUSED"
                elif playback_info.playback_status == PlaybackStatus.STOPPED:
                    status_text = "STOPPED"
        except Exception:
            pass

        pos_sec = 0.0
        end_sec = 0.0
        try:
            timeline = session.get_timeline_properties()
            if timeline:
                pos_sec = timeline.position.total_seconds()
                end_sec = timeline.end_time.total_seconds()
                if status_text == "PLAYING" and timeline.last_updated_time:
                    delta = (datetime.now(timeline.last_updated_time.tzinfo) - timeline.last_updated_time).total_seconds()
                    pos_sec = min(end_sec, pos_sec + max(0.0, delta))
        except Exception:
            pass

        props = await session.try_get_media_properties_async()
        if not props or not props.title:
            return None

        title = props.title or ""
        artist = props.artist or ""
        album_title = props.album_title or ""
        track_num = props.track_number or 0
        track_count = props.album_track_count or 0
        current_track_id = f"{title}_{artist}"

        if current_track_id != self._last_track_id:
            self._last_track_id = current_track_id
            self._cached_thumb_bytes = None
            self._cached_thumb_size = 0
            self._thumb_check_retries = 10

        if props.thumbnail and (self._cached_thumb_bytes is None or self._thumb_check_retries > 0):
            if self._thumb_check_retries > 0:
                self._thumb_check_retries -= 1
            try:
                stream = await props.thumbnail.open_read_async()
                size = stream.size
                if size > 0 and size != self._cached_thumb_size:
                    reader = DataReader(stream)
                    await reader.load_async(size)
                    buf = bytearray(size)
                    reader.read_bytes(buf)
                    self._cached_thumb_bytes = bytes(buf)
                    self._cached_thumb_size = size
            except Exception:
                pass

        return {
            "title": title,
            "artist": artist,
            "album_title": album_title,
            "track_number": track_num,
            "track_count": track_count,
            "status": status_text,
            "source_app": source_app or "Media",
            "thumb_bytes": self._cached_thumb_bytes,
            "pos_sec": pos_sec,
            "end_sec": end_sec,
        }

    def control(self, action):
        if not self._loop or not self._session:
            return
        async def _do():
            try:
                if action == "play_pause":
                    await self._session.try_toggle_play_pause_async()
                elif action == "next":
                    await self._session.try_skip_next_async()
                elif action == "prev":
                    await self._session.try_skip_previous_async()
            except Exception:
                pass
        asyncio.run_coroutine_threadsafe(_do(), self._loop)

    def stop(self):
        self._running = False


# ==============================================================================
# FFT ビンマッピング
# ==============================================================================
class PixelMap:
    def __init__(self, sample_rate, plot_w):
        self.bin_hz = sample_rate / CFG_FFT_SIZE
        cols = plot_w + 1
        max_f = min(20000.0, (sample_rate / 2.0) - 1.0)
        log_max = np.log10(max(max_f, 100.0))

        px = np.arange(cols)
        freq = 10.0 ** (LOG_MIN + (px / plot_w) * (log_max - LOG_MIN))
        exact = freq / self.bin_hz
        b0 = np.clip(np.floor(exact).astype(np.int64), 0, BIN_COUNT - 1)
        b1 = np.clip(b0 + 1, 0, BIN_COUNT - 1)
        self.b0 = b0
        self.b1 = b1
        self.frac = np.clip(exact - b0, 0.0, 1.0).astype(np.float32)

        edge_px = np.arange(cols + 1) - 0.5
        edge_freq = 10.0 ** (LOG_MIN + (edge_px / plot_w) * (log_max - LOG_MIN))
        edge_bins = np.clip(np.floor(edge_freq / self.bin_hz).astype(np.int64), 0, BIN_COUNT - 1)
        self.starts = edge_bins[:cols]
        self.end = min(BIN_COUNT, int(edge_bins[cols]) + 1)
        ends = edge_bins[1:].copy()
        ends[-1] = self.end
        self.use_range = (ends - self.starts) >= 2

    def apply(self, arr):
        interp = arr[self.b0] * (1.0 - self.frac) + arr[self.b1] * self.frac
        range_max = np.maximum.reduceat(arr[:self.end], self.starts)
        return np.where(self.use_range, range_max, interp).astype(np.float32)


# ==============================================================================
# メイン描画キャンバス
# ==============================================================================
class SpectrumCanvas(QtOpenGLWidgets.QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(BASE_W, BASE_H)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        # 1. 窓関数 (Blackman)
        n = np.arange(CFG_FFT_SIZE)
        self.fft_window = (
            0.42
            - 0.5 * np.cos(2.0 * np.pi * n / CFG_FFT_SIZE)
            + 0.08 * np.cos(4.0 * np.pi * n / CFG_FFT_SIZE)
        )
        self.window_sum = float(np.sum(self.fft_window))

        # 2. カラーテーマ初期化
        self.theme_idx = 0
        self.color_lut = None
        self._update_theme_lut()

        # 3. 最前面固定フラグ
        self.is_always_on_top = False

        # 4. バッファ初期化
        self.smoothed_mag = np.zeros(BIN_COUNT, dtype=np.float64)
        self.peak_data = np.full(BIN_COUNT, CFG_FLOOR_DB, dtype=np.float32)

        self.smoothed_corr = 1.0
        self.corr_is_silent = True
        self.is_mono = False

        self.smoothed_peak_db = -100.0
        self.smoothed_crest_db = 0.0
        self.smoothed_mid_pct = 50.0
        self.smoothed_centroid = 0.0

        self.ring_buffer = np.zeros((CFG_FFT_SIZE, 2), dtype=np.float32)
        self.write_pos = 0
        self.lock = threading.Lock()
        now = time.perf_counter()
        self.last_audio_time = now
        self.last_time = now

        self.gonio_samples = np.zeros((128, 2), dtype=np.float32)

        # アスペクト比維持レイアウト用
        self.ui_scale = 1.0
        self.draw_w = BASE_W
        self.draw_h = BASE_H
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.pad_l = PAD_L
        self.pad_r = PAD_R
        self.pad_t = PAD_T
        self.pad_b = PAD_B

        self.h_head = 176
        self.h_spec = 106
        self.h_water = 40
        self.h_meter = 38

        self.plot_w = 0
        self.plot_h = 0
        self.plot_bottom = 0
        self.water_data = None
        self.px_coords = []

        self.poly_peak = None
        self.poly_live = None
        self.poly_fill = None

        self.fonts = {}

        # メディア情報
        self.media_title = ""
        self.media_artist = ""
        self.media_album = ""
        self.media_track_str = ""
        self.media_status = ""
        self.media_source_app = ""
        self.media_pixmap = None
        self.media_aspect = 1.0
        self._raw_thumb_bytes = None
        self.media_pos_sec = 0.0
        self.media_end_sec = 0.0

        # ハードウェア・システム情報
        self.device_name = "Default Output"
        self.fps = 60.0
        self.volume_level = 50
        self.is_muted = False
        self.last_sys_check = 0.0
        self._cached_vol_obj = None
        self._cached_dev_id = None
        self._last_dev_check_time = 0.0

        # UI操作ボタン Rect
        self.btn_rects = {}

        self.dev_lock = threading.Lock()
        self.p = None
        self.stream = None
        self.sample_rate = 48000
        self.channels = 2
        self.pixel_map = None
        self._closing = False
        self._shutdown_done = False
        self._rescanning = False
        self.last_rescan = now

        self.media_watcher = MediaWatcher()
        self.media_watcher.media_changed.connect(self._on_media_changed)

        self._update_dimensions(960, 540)
        self._open_audio()

        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)

    def _update_theme_lut(self):
        t = np.linspace(0.0, 1.0, 256)
        lut_fn = COLOR_THEMES[self.theme_idx]["lut_fn"]
        self.color_lut = lut_fn(t)

    def next_theme(self):
        self.theme_idx = (self.theme_idx + 1) % len(COLOR_THEMES)
        self._update_theme_lut()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_C:
            self.next_theme()
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        pos = event.position()
        mx, my = pos.x() - self.offset_x, pos.y() - self.offset_y
        for action, rect in self.btn_rects.items():
            if rect.contains(mx, my):
                if action == "pin":
                    win = self.window()
                    if hasattr(win, "toggle_pin"):
                        self.is_always_on_top = win.toggle_pin()
                        self.update()
                else:
                    self.media_watcher.control(action)
                return
        super().mousePressEvent(event)

    def _build_font(self, families, size, bold=False):
        if isinstance(families, str):
            families = [families]
        f = QtGui.QFont()
        f.setFamilies(families)
        f.setPointSizeF(size * self.ui_scale)
        f.setBold(bold)
        return f

    def _update_font_cache(self):
        # 日本語用フォント優先順位 (BIZ UDPGothic を最優先)
        jp_font = ["BIZ UDPGothic", "Meiryo UI", "Segoe UI", "sans-serif"]
        # 英数・等幅用フォント優先順位
        mono_font = ["Consolas", "Segoe UI", "sans-serif"]

        self.fonts = {
            "title": self._build_font(jp_font, 10.5, bold=True),
            "artist": self._build_font(jp_font, 8.5),
            "album": self._build_font(jp_font, 7.2),
            "clock": self._build_font(mono_font, 7.2),
            "pin": self._build_font(mono_font, 7.5, bold=True),
            "time_pos": self._build_font(mono_font, 7.5, bold=True),
            "btn": self._build_font("Segoe UI Symbol", 12.5),
            "badge": self._build_font(mono_font, 6.5, bold=True),
            "device": self._build_font(jp_font, 6.5),  # デバイス名も日本語に対応
            "status": self._build_font(mono_font, 7.5, bold=True),
            "grid": self._build_font(mono_font, 8.0),
            "osd": self._build_font(mono_font, 6.5, bold=True),
            "meter_hdr": self._build_font(mono_font, 6.8, bold=True),
            "meter_val": self._build_font(mono_font, 6.8),
            "meter_scale": self._build_font(mono_font, 5.5),
            "icon_empty": self._build_font("Segoe UI Emoji", 24.0),
        }

    def _on_media_changed(self, data):
        self.media_title = data.get("title", "")
        self.media_artist = data.get("artist", "")
        self.media_album = data.get("album_title", "")
        t_num = data.get("track_number", 0)
        t_cnt = data.get("track_count", 0)
        self.media_track_str = f"TRK {t_num:02d}/{t_cnt:02d}" if (t_num > 0 and t_cnt > 0) else ""
        self.media_status = data.get("status", "")
        self.media_source_app = data.get("source_app", "")
        self.media_pos_sec = data.get("pos_sec", 0.0)
        self.media_end_sec = data.get("end_sec", 0.0)
        new_thumb = data.get("thumb_bytes")

        if new_thumb != self._raw_thumb_bytes:
            self._raw_thumb_bytes = new_thumb
            if new_thumb:
                pix = QtGui.QPixmap()
                if pix.loadFromData(new_thumb) and not pix.isNull():
                    self.media_pixmap = pix
                    w, h = pix.width(), pix.height()
                    self.media_aspect = max(1.0, min(16.0 / 9.0, w / float(max(1, h))))
                else:
                    self.media_pixmap = None
                    self.media_aspect = 1.0
            else:
                self.media_pixmap = None
                self.media_aspect = 1.0

    @staticmethod
    def _extract_device_id(dev):
        if hasattr(dev, "id"):
            return str(dev.id)
        if hasattr(dev, "GetId"):
            try:
                return str(dev.GetId())
            except Exception:
                pass
        if hasattr(dev, "_dev") and hasattr(dev._dev, "GetId"):
            try:
                return str(dev._dev.GetId())
            except Exception:
                pass
        return None

    def _update_system_audio_info(self, now):
        if not PYCAW_AVAILABLE:
            return
        if now - self.last_sys_check < 0.15:
            return
        self.last_sys_check = now

        try:
            check_device = (now - self._last_dev_check_time) > 0.8
            if check_device or self._cached_vol_obj is None:
                self._last_dev_check_time = now
                speakers = AudioUtilities.GetSpeakers()
                cur_dev_id = self._extract_device_id(speakers)

                if cur_dev_id != self._cached_dev_id or self._cached_vol_obj is None:
                    device_switched = (self._cached_dev_id is not None and cur_dev_id != self._cached_dev_id)
                    self._cached_dev_id = cur_dev_id

                    vol = None
                    try:
                        vol = speakers.EndpointVolume
                    except Exception:
                        pass
                    if not vol:
                        endpoint = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                        vol = endpoint.QueryInterface(IAudioEndpointVolume)
                    self._cached_vol_obj = vol

                    if device_switched:
                        with self.lock:
                            self.last_audio_time = 0.0

            if self._cached_vol_obj:
                scalar = self._cached_vol_obj.GetMasterVolumeLevelScalar()
                mute = self._cached_vol_obj.GetMute()
                self.volume_level = int(round(scalar * 100))
                self.is_muted = bool(mute)

        except Exception:
            self._cached_vol_obj = None
            self._cached_dev_id = None

    def _update_dimensions(self, win_w, win_h):
        scale = min(win_w / BASE_W, win_h / BASE_H)
        self.ui_scale = max(1.0, scale ** 0.5)
        s = self.ui_scale

        self.pad_l = int(PAD_L * s)
        self.pad_r = int(PAD_R * s)
        self.pad_t = int(PAD_T * s)
        self.pad_b = int(PAD_B * s)

        draw_w = max(BASE_W, int(BASE_W * scale))
        draw_h = max(BASE_H, int(BASE_H * scale))
        self.draw_w = draw_w
        self.draw_h = draw_h
        self.offset_x = (win_w - draw_w) / 2.0
        self.offset_y = (win_h - draw_h) / 2.0

        h_head = int(draw_h * (176.0 / BASE_H))
        h_spec = int(draw_h * (106.0 / BASE_H))
        h_water = int(draw_h * (40.0 / BASE_H))
        self.h_head = h_head
        self.h_spec = h_spec
        self.h_water = h_water
        self.h_meter = draw_h - h_head - h_spec - h_water

        plot_w = draw_w - self.pad_l - self.pad_r
        self.plot_h = h_spec - self.pad_t - self.pad_b
        self.plot_bottom = h_head + self.pad_t + self.plot_h

        if plot_w != self.plot_w:
            self.plot_w = plot_w
            if self.sample_rate:
                self.pixel_map = PixelMap(self.sample_rate, plot_w)
            self.water_data = np.zeros((CFG_SPECTROGRAM_HISTORY, plot_w, 4), dtype=np.uint8)
            self.water_data[:, :, 3] = 255
            self.px_coords = (self.pad_l + np.arange(plot_w + 1, dtype=np.float64)).tolist()

        self._update_font_cache()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_dimensions(event.size().width(), event.size().height())

    @staticmethod
    def _find_loopback(p):
        try:
            return p.get_default_wasapi_loopback()
        except Exception:
            for dev in p.get_loopback_device_info_generator():
                return dev
        return None

    def _open_audio(self):
        p = pyaudio.PyAudio()
        try:
            dev = self._find_loopback(p)
            if not dev:
                raise RuntimeError("WASAPIループバックデバイスが見つかりません。")

            sample_rate = int(dev["defaultSampleRate"])
            channels = int(dev["maxInputChannels"])
            self.device_name = dev.get("name", "Audio Device")

            with self.lock:
                self.ring_buffer.fill(0.0)
                self.write_pos = 0
                self.last_audio_time = time.perf_counter()
            self.channels = channels
            self.is_mono = (channels == 1)

            stream = p.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=dev["index"],
                frames_per_buffer=512,
                stream_callback=self.audio_callback,
            )
        except Exception:
            p.terminate()
            raise

        self.p = p
        self.stream = stream
        self.sample_rate = sample_rate
        self.pixel_map = PixelMap(sample_rate, self.plot_w)

    def _close_audio(self):
        stream, p = self.stream, self.p
        self.stream = None
        self.p = None
        try:
            if stream is not None:
                stream.stop_stream()
                stream.close()
        except Exception:
            pass
        try:
            if p is not None:
                p.terminate()
        except Exception:
            pass

    def _maybe_rescan(self, now):
        if self._closing or self._rescanning:
            return
        with self.lock:
            silent_for = now - self.last_audio_time
        if silent_for < RESCAN_AFTER or now - self.last_rescan < RESCAN_INTERVAL:
            return
        self._rescanning = True
        threading.Thread(target=self._rescan_worker, daemon=True).start()

    def _rescan_worker(self):
        try:
            with self.dev_lock:
                if self._closing:
                    return
                self._close_audio()
                try:
                    self._open_audio()
                except Exception:
                    pass
        finally:
            self.last_rescan = time.perf_counter()
            self._rescanning = False

    def shutdown(self):
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self._closing = True
        try:
            self.media_watcher.stop()
            self.timer.stop()
        except Exception:
            pass
        with self.dev_lock:
            self._close_audio()

    def audio_callback(self, in_data, frame_count, time_info, status):
        if in_data:
            data = np.frombuffer(in_data, dtype=np.float32)
            if self.channels >= 2:
                data_stereo = data.reshape(-1, self.channels)[:, :2]
            else:
                data_stereo = np.column_stack((data, data))

            n = len(data_stereo)
            if n > 0:
                with self.lock:
                    buf = self.ring_buffer
                    if n >= CFG_FFT_SIZE:
                        buf[:] = data_stereo[-CFG_FFT_SIZE:]
                        self.write_pos = 0
                    else:
                        pos = self.write_pos
                        end = pos + n
                        if end <= CFG_FFT_SIZE:
                            buf[pos:end, :] = data_stereo
                        else:
                            first = CFG_FFT_SIZE - pos
                            buf[pos:, :] = data_stereo[:first]
                            buf[:n - first, :] = data_stereo[first:]
                        self.write_pos = end % CFG_FFT_SIZE
                    self.last_audio_time = time.perf_counter()

        return (None, pyaudio.paContinue)

    def update_frame(self):
        now = time.perf_counter()
        dt = min(0.1, max(0.001, now - self.last_time))
        self.last_time = now

        inst_fps = 1.0 / dt
        self.fps = 0.9 * self.fps + 0.1 * inst_fps

        with self.lock:
            if now - self.last_audio_time > SILENCE_TIMEOUT:
                self.ring_buffer.fill(0.0)
            pos = self.write_pos
            samples = np.concatenate((self.ring_buffer[pos:], self.ring_buffer[:pos]), axis=0)

        self._maybe_rescan(now)
        self._update_system_audio_info(now)
        pixel_map = self.pixel_map
        if pixel_map is None or self.water_data is None:
            return

        self.gonio_samples = samples[-128:].copy()

        left, right = samples[:, 0], samples[:, 1]
        p_l = float(np.dot(left, left))
        p_r = float(np.dot(right, right))
        p_tot_raw = p_l + p_r
        silence_limit = 1e-6 * CFG_FFT_SIZE
        corr_tau = CFG_CORR_SMOOTHING ** (dt / SMOOTHING_REF_DT)

        # 1. ダイナミクス計算 (PEAK / CREST)
        is_rms_silent = (p_l < silence_limit and p_r < silence_limit)

        peak_lin = float(np.max(np.abs(samples)))
        raw_peak_db = 20.0 * np.log10(max(peak_lin, 1e-5))

        rms_lin = float(np.sqrt(p_tot_raw / (2.0 * CFG_FFT_SIZE)))
        raw_rms_db = 20.0 * np.log10(max(rms_lin, 1e-5))

        raw_crest_db = max(0.0, raw_peak_db - raw_rms_db)

        # --- PEAK ---
        peak_target_db = (
            raw_peak_db
            if raw_peak_db > CFG_PEAK_GATE_DB
            else -100.0
        )

        if peak_target_db > self.smoothed_peak_db:
            self.smoothed_peak_db = peak_target_db
        else:
            self.smoothed_peak_db = (
                corr_tau * self.smoothed_peak_db
                + (1.0 - corr_tau) * peak_target_db
            )

        # --- CREST ---
        if is_rms_silent:
            self.smoothed_crest_db = 0.0
        else:
            self.smoothed_crest_db = (
                corr_tau * self.smoothed_crest_db
                + (1.0 - corr_tau) * raw_crest_db
            )

        # 2. 相関 & M/S比計算
        if is_rms_silent:
            self.corr_is_silent = True
            raw_corr = 0.0
            raw_mid_pct = 50.0
        else:
            self.corr_is_silent = False
            l_c = left - np.mean(left)
            r_c = right - np.mean(right)
            cov = float(np.dot(l_c, r_c))
            denom = float(np.sqrt(np.dot(l_c, l_c) * np.dot(r_c, r_c)))
            raw_corr = float(np.clip(cov / denom, -1.0, 1.0)) if denom > 1e-9 else 0.0

            cov_lr = float(np.dot(left, right))
            p_mid = 0.25 * (p_l + p_r + 2.0 * cov_lr)
            p_tot_ms = 0.5 * p_tot_raw
            raw_mid_pct = (p_mid / p_tot_ms * 100.0) if p_tot_ms > 1e-9 else 50.0

        if self.corr_is_silent:
            self.smoothed_corr = corr_tau * self.smoothed_corr
            self.smoothed_mid_pct = 50.0
        else:
            self.smoothed_corr = corr_tau * self.smoothed_corr + (1.0 - corr_tau) * raw_corr
            self.smoothed_mid_pct = corr_tau * self.smoothed_mid_pct + (1.0 - corr_tau) * raw_mid_pct

        # 3. スペクトラム処理
        mono_samples = samples.mean(axis=1)
        windowed = mono_samples * self.fft_window
        mag = (np.abs(np.fft.rfft(windowed))[:BIN_COUNT] * 2.0) / self.window_sum

        tau = CFG_SMOOTHING ** (dt / SMOOTHING_REF_DT)
        self.smoothed_mag = tau * self.smoothed_mag + (1.0 - tau) * mag

        db = 20.0 * np.log10(np.maximum(self.smoothed_mag, 1e-7))
        freq_data = np.maximum(db, CFG_FLOOR_DB).astype(np.float32)

        decay = CFG_PEAK_DECAY_PER_SEC * dt
        self.peak_data = np.maximum(freq_data, self.peak_data - decay)
        self.peak_data = np.maximum(self.peak_data, CFG_FLOOR_DB)

        # スペクトル重心
        bin_hz = self.sample_rate / CFG_FFT_SIZE
        freqs = np.arange(BIN_COUNT) * bin_hz
        if not self.corr_is_silent:
            sum_m = float(np.sum(self.smoothed_mag))
            raw_centroid = float(np.sum(freqs * self.smoothed_mag) / sum_m) if sum_m > 1e-9 else 0.0
            self.smoothed_centroid = corr_tau * self.smoothed_centroid + (1.0 - corr_tau) * raw_centroid
        else:
            self.smoothed_centroid = 0.0

        range_db = CFG_PLOT_MAX_DB - CFG_PLOT_MIN_DB
        db_live = pixel_map.apply(freq_data)
        db_peak = pixel_map.apply(self.peak_data)
        norm_live = np.clip((db_live - CFG_PLOT_MIN_DB) / range_db, 0.0, 1.0)
        norm_peak = np.clip((db_peak - CFG_PLOT_MIN_DB) / range_db, 0.0, 1.0)

        plot_w, plot_h = self.plot_w, self.plot_h
        base_top = self.h_head + self.pad_t

        y_live = (base_top + plot_h * (1.0 - norm_live)).tolist()
        y_peak = (base_top + plot_h * (1.0 - norm_peak)).tolist()

        step = max(1, plot_w // 800)
        xs_sub = self.px_coords[::step]
        y_live_sub = y_live[::step]
        y_peak_sub = y_peak[::step]

        if xs_sub[-1] != self.px_coords[-1]:
            xs_sub.append(self.px_coords[-1])
            y_live_sub.append(y_live[-1])
            y_peak_sub.append(y_peak[-1])

        pts_live = [QtCore.QPointF(x, y) for x, y in zip(xs_sub, y_live_sub)]
        pts_peak = [QtCore.QPointF(x, y) for x, y in zip(xs_sub, y_peak_sub)]
        self.poly_live = QtGui.QPolygonF(pts_live)
        self.poly_peak = QtGui.QPolygonF(pts_peak)
        self.poly_fill = QtGui.QPolygonF(
            [QtCore.QPointF(self.pad_l, self.plot_bottom)]
            + pts_live
            + [QtCore.QPointF(self.pad_l + plot_w, self.plot_bottom)]
        )

        norm_row = norm_live[:plot_w]
        idx = np.clip((norm_row * 255.0).astype(np.int32), 0, 255)
        self.water_data = np.roll(self.water_data, 1, axis=0)
        self.water_data[0, :, :3] = self.color_lut[idx]

        self.update()

    def _get_corr_info(self):
        theme = COLOR_THEMES[self.theme_idx]
        if self.is_mono:
            return "+1.00", QtGui.QColor("#888888")
        if self.corr_is_silent:
            return "--", QtGui.QColor("#666666")

        c = self.smoothed_corr
        val_str = f"{c:+.2f}"
        if c >= 0.7:
            return val_str, theme["primary"]
        elif c >= 0.2:
            return val_str, theme["secondary"]
        elif c > -0.2:
            return val_str, QtGui.QColor("#bbbbbb")
        elif c > -0.7:
            return val_str, QtGui.QColor("#ffaa00")
        else:
            return val_str, QtGui.QColor("#ff4444")

    # ---------- 描画 ----------
    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)

        p.fillRect(0, 0, self.width(), self.height(), QtGui.QColor("#0a0b10"))
        p.translate(self.offset_x, self.offset_y)

        self._draw_header(p)
        self._draw_spectrum(p)
        self._draw_waterfall(p)
        self._draw_meters(p)

        p.end()

    def _draw_header(self, p):
        s = self.ui_scale
        icon_h = int(156 * s)
        icon_w = int(icon_h * self.media_aspect)
        icon_x = self.pad_l
        icon_y = int((self.h_head - icon_h) / 2.0)
        theme = COLOR_THEMES[self.theme_idx]

        # カバーアート
        if self.media_pixmap:
            path = QtGui.QPainterPath()
            path.addRoundedRect(QtCore.QRectF(icon_x, icon_y, icon_w, icon_h), 8 * s, 8 * s)
            p.save()
            p.setClipPath(path)
            p.drawPixmap(QtCore.QRect(icon_x, icon_y, icon_w, icon_h), self.media_pixmap)
            p.restore()
        else:
            p.fillRect(QtCore.QRectF(icon_x, icon_y, icon_w, icon_h), QtGui.QColor(255, 255, 255, 15))
            p.setFont(self.fonts["icon_empty"])
            p.setPen(QtGui.QColor("#555"))
            p.drawText(QtCore.QRectF(icon_x, icon_y, icon_w, icon_h), QtCore.Qt.AlignmentFlag.AlignCenter, "🎵")

        # --- [右上ゾーン: PINボタン / ステータス / タイムライン] ---
        right_edge = self.pad_l + self.plot_w

        # 0. PIN ボタン (最上段・最右端)
        pin_w = 40 * s
        pin_h = 19 * s
        pin_x = right_edge - pin_w
        pin_y = icon_y

        pin_rect = QtCore.QRectF(pin_x, pin_y, pin_w, pin_h)
        self.btn_rects["pin"] = pin_rect

        p.setFont(self.fonts["pin"])
        if self.is_always_on_top:
            c_bg = QtGui.QColor(theme["primary"])
            c_bg.setAlpha(38)
            p.setBrush(c_bg)
            p.setPen(QtGui.QPen(theme["primary"], 1.2))
            p.drawRoundedRect(pin_rect, 3.5 * s, 3.5 * s)
            p.setPen(theme["primary"])
        else:
            p.setBrush(QtGui.QColor(255, 255, 255, 12))
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 30), 1))
            p.drawRoundedRect(pin_rect, 3.5 * s, 3.5 * s)
            p.setPen(QtGui.QColor("#777777"))

        p.drawText(pin_rect, QtCore.Qt.AlignmentFlag.AlignCenter, "PIN")

        # 1. ステータス (PINの下に右揃え)
        status_text = self.media_status or ("READY" if WINSDK_AVAILABLE else "NO WINSDK")
        p.setFont(self.fonts["status"])
        status_color = theme["secondary"] if status_text == "PLAYING" else QtGui.QColor("#888888")
        p.setPen(status_color)
        p.drawText(QtCore.QRectF(right_edge - 70 * s, icon_y + 23 * s, 70 * s, 16 * s),
                   QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter, status_text)

        # 2. タイムライン (ステータスの下に右揃え)
        m_pos = int(self.media_pos_sec)
        m_end = int(self.media_end_sec)
        pos_str = f"{m_pos // 60:02d}:{m_pos % 60:02d} / {m_end // 60:02d}:{m_end % 60:02d}" if m_end > 0 else "--:-- / --:--"
        p.setFont(self.fonts["time_pos"])
        p.setPen(QtGui.QColor("#999999"))
        p.drawText(QtCore.QPointF(right_edge - p.fontMetrics().horizontalAdvance(pos_str), icon_y + 52 * s), pos_str)

        # --- [右下ゾーン: 時計 / 操作ボタン] ---
        # 3. 時計（ミリ秒付き）+ 日付
        now_dt = datetime.now()
        ms_digit = int(time.time() * 10) % 10
        clock_str = now_dt.strftime(f"%a %d %b  %H:%M:%S.{ms_digit}").upper()
        p.setFont(self.fonts["clock"])
        p.setPen(QtGui.QColor("#777777"))
        clock_adv = p.fontMetrics().horizontalAdvance(clock_str)
        clock_x = right_edge - clock_adv
        clock_y = icon_y + 104 * s
        p.drawText(QtCore.QPointF(clock_x, clock_y), clock_str)

        # 4. メディア操作ボタン (時計の下に配置)
        btn_size = 28 * s
        btn_gap = 6 * s
        btn_y = icon_y + 114 * s

        btn_next_x = right_edge - btn_size
        btn_play_x = btn_next_x - btn_gap - btn_size
        btn_prev_x = btn_play_x - btn_gap - btn_size

        self.btn_rects.update({
            "prev": QtCore.QRectF(btn_prev_x, btn_y, btn_size, btn_size),
            "play_pause": QtCore.QRectF(btn_play_x, btn_y, btn_size, btn_size),
            "next": QtCore.QRectF(btn_next_x, btn_y, btn_size, btn_size),
        })

        p.setFont(self.fonts["btn"])
        for act in ["prev", "play_pause", "next"]:
            r = self.btn_rects[act]
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 28), 1))
            p.setBrush(QtGui.QColor(255, 255, 255, 14))
            p.drawRoundedRect(r, 5 * s, 5 * s)

            sym = "⏮" if act == "prev" else ("⏯" if act == "play_pause" else "⏭")
            p.setPen(QtGui.QColor("#dddddd"))
            p.drawText(r, QtCore.Qt.AlignmentFlag.AlignCenter, sym)

        # --- [テキストエリア（曲名 / アーティスト / アルバム）] ---
        text_x = icon_x + icon_w + int(14 * s)
        avail_text_w = max(10, int(right_edge - 85 * s - text_x))

        if self.media_title:
            p.setFont(self.fonts["title"])
            p.setPen(QtGui.QColor("#ffffff"))
            title_elided = p.fontMetrics().elidedText(self.media_title, QtCore.Qt.TextElideMode.ElideRight, avail_text_w)
            p.drawText(QtCore.QPointF(text_x, icon_y + 24 * s), title_elided)

            p.setFont(self.fonts["artist"])
            p.setPen(QtGui.QColor("#aaaaaa"))
            artist_text = self.media_artist if self.media_artist else "Unknown Artist"
            artist_elided = p.fontMetrics().elidedText(artist_text, QtCore.Qt.TextElideMode.ElideRight, avail_text_w)
            p.drawText(QtCore.QPointF(text_x, icon_y + 44 * s), artist_elided)

            p.setFont(self.fonts["album"])
            p.setPen(QtGui.QColor("#777777"))
            album_full = self.media_album
            if self.media_track_str:
                album_full = f"{album_full}  [{self.media_track_str}]" if album_full else self.media_track_str
            if album_full:
                album_elided = p.fontMetrics().elidedText(f"ALBUM: {album_full}", QtCore.Qt.TextElideMode.ElideRight, avail_text_w)
                p.drawText(QtCore.QPointF(text_x, icon_y + 64 * s), album_elided)
        else:
            p.setFont(self.fonts["artist"])
            p.setPen(QtGui.QColor("#555555"))
            msg = "No media playing" if WINSDK_AVAILABLE else "Install winsdk for track info"
            p.drawText(QtCore.QPointF(text_x, icon_y + 40 * s), msg)

        # --- [HUDバッジ列] (実測できる項目のみ) ---
        sr_str = f"{self.sample_rate / 1000.0:.1f} kHz"
        vol_str = "MUTE" if self.is_muted else f"VOL: {self.volume_level}%"
        src_str = f"SRC: {self.media_source_app}" if self.media_source_app else "SRC: System"
        theme_str = f"THEME: {theme['name'][:5].upper()}"
        tech_badges = [src_str, sr_str, vol_str, theme_str, f"{self.fps:.1f} FPS"]

        badge_x = text_x
        badge_y = icon_y + 94 * s
        badge_h = 17 * s

        badge_limit_x = min(btn_prev_x, clock_x) - 10 * s

        p.setFont(self.fonts["badge"])
        for badge in tech_badges:
            bw = p.fontMetrics().horizontalAdvance(badge) + 10 * s
            if badge_x + bw > badge_limit_x:
                break

            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor(255, 255, 255, 12))
            p.drawRoundedRect(QtCore.QRectF(badge_x, badge_y, bw, badge_h), 3 * s, 3 * s)

            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 25), 1))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QtCore.QRectF(badge_x, badge_y, bw, badge_h), 3 * s, 3 * s)

            if "MUTE" in badge:
                b_col = QtGui.QColor("#ff4444")
            elif "kHz" in badge or "FPS" in badge:
                b_col = theme["primary"]
            else:
                b_col = QtGui.QColor("#aaaaaa")

            p.setPen(b_col)
            p.drawText(QtCore.QRectF(badge_x, badge_y, bw, badge_h), QtCore.Qt.AlignmentFlag.AlignCenter, badge)
            badge_x += bw + 5 * s

        # デバイス名
        p.setFont(self.fonts["device"])
        p.setPen(QtGui.QColor("#555555"))
        dev_str = f"DEVICE: {self.device_name}"
        dev_elided = p.fontMetrics().elidedText(dev_str, QtCore.Qt.TextElideMode.ElideRight, avail_text_w)
        p.drawText(QtCore.QPointF(text_x, icon_y + 140 * s), dev_elided)

        # 区切り線
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 20), 1))
        p.drawLine(QtCore.QPointF(self.pad_l, self.h_head), QtCore.QPointF(self.pad_l + self.plot_w, self.h_head))

    def _draw_spectrum(self, p):
        s = self.ui_scale
        plot_w, plot_h = self.plot_w, self.plot_h
        spec_top = self.h_head
        base_plot_top = spec_top + self.pad_t
        range_db = CFG_PLOT_MAX_DB - CFG_PLOT_MIN_DB
        theme = COLOR_THEMES[self.theme_idx]

        grid_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 20), 1)
        grid_pen.setStyle(QtCore.Qt.PenStyle.DashLine)
        p.setPen(grid_pen)
        p.setFont(self.fonts["grid"])

        for db in GRID_DB:
            y = base_plot_top + plot_h * (1.0 - (db - CFG_PLOT_MIN_DB) / range_db)
            p.drawLine(QtCore.QPointF(self.pad_l, y), QtCore.QPointF(self.pad_l + plot_w, y))
            p.setPen(QtGui.QColor("#666"))
            p.drawText(QtCore.QPointF(4 * s, y + 3 * s), f"{db}")
            p.setPen(grid_pen)

        for f, label in GRID_HZ:
            x = float(self.pad_l + ((np.log10(f) - LOG_MIN) / (LOG_MAX - LOG_MIN)) * plot_w)
            if self.pad_l <= x <= self.pad_l + plot_w:
                p.drawLine(QtCore.QPointF(x, base_plot_top), QtCore.QPointF(x, self.plot_bottom))
                p.setPen(QtGui.QColor("#666"))
                p.drawText(QtCore.QPointF(x - len(label) * 2.5 * s, spec_top + self.h_spec - 4 * s), label)
                p.setPen(grid_pen)

        if self.poly_live is not None:
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 90), 1))
            p.drawPolyline(self.poly_peak)

            grad = QtGui.QLinearGradient(0, base_plot_top, 0, self.plot_bottom)
            grad.setColorAt(0.0, theme["grad_top"])
            grad.setColorAt(0.5, theme["grad_mid"])
            grad.setColorAt(1.0, QtGui.QColor(29, 185, 84, 5))
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(grad)
            p.drawPolygon(self.poly_fill)

            p.setPen(QtGui.QPen(theme["primary"], 1.4))
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawPolyline(self.poly_live)

        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 38), 1))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawRect(QtCore.QRectF(self.pad_l, base_plot_top, plot_w, plot_h))

        # ゴニオメーター
        gonio_size = 46 * s
        gx = self.pad_l + 8 * s
        gy = base_plot_top + 6 * s

        p.fillRect(QtCore.QRectF(gx, gy, gonio_size, gonio_size), QtGui.QColor(10, 15, 20, 180))
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 30), 1))
        p.drawRect(QtCore.QRectF(gx, gy, gonio_size, gonio_size))
        cx, cy = gx + gonio_size / 2.0, gy + gonio_size / 2.0
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 20), 1, QtCore.Qt.PenStyle.DashLine))
        p.drawLine(QtCore.QPointF(gx, cy), QtCore.QPointF(gx + gonio_size, cy))
        p.drawLine(QtCore.QPointF(cx, gy), QtCore.QPointF(cx, gy + gonio_size))

        if not self.corr_is_silent:
            half = gonio_size / 2.0 * 0.85
            l_sam, r_sam = self.gonio_samples[:, 0], self.gonio_samples[:, 1]
            x_rot = cx + (l_sam - r_sam) * 0.7071 * half
            y_rot = cy - (l_sam + r_sam) * 0.7071 * half

            p.setPen(QtGui.QPen(theme["primary"], 1.2))
            for i in range(len(x_rot) - 1):
                p.drawLine(QtCore.QPointF(x_rot[i], y_rot[i]), QtCore.QPointF(x_rot[i + 1], y_rot[i + 1]))

        # OSDラック (スペクトル重心のみ)
        p.setFont(self.fonts["osd"])

        cen_val = f"{self.smoothed_centroid / 1000.0:4.2f}k" if self.smoothed_centroid > 20 else " --  "
        osd_full_text = f"CENTROID:{cen_val}"

        osd_w = int(110 * s)
        osd_h = 16 * s
        osd_x = self.pad_l + plot_w - osd_w - 8 * s
        osd_y = base_plot_top + 6 * s

        p.fillRect(QtCore.QRectF(osd_x, osd_y, osd_w, osd_h), QtGui.QColor(10, 15, 20, 180))
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 30), 1))
        p.drawRect(QtCore.QRectF(osd_x, osd_y, osd_w, osd_h))
        p.setPen(theme["primary"])
        p.drawText(QtCore.QRectF(osd_x, osd_y, osd_w, osd_h), QtCore.Qt.AlignmentFlag.AlignCenter, osd_full_text)

    def _draw_waterfall(self, p):
        water_top = self.h_head + self.h_spec
        if self.water_data is not None:
            water_buf = np.ascontiguousarray(self.water_data)
            water_img = QtGui.QImage(
                water_buf.data, self.plot_w, CFG_SPECTROGRAM_HISTORY, self.plot_w * 4,
                QtGui.QImage.Format.Format_RGBA8888
            )
            target_rect = QtCore.QRectF(self.pad_l, water_top + 2, self.plot_w, self.h_water - 4)
            source_rect = QtCore.QRectF(0, 0, self.plot_w, CFG_SPECTROGRAM_HISTORY)
            p.drawImage(target_rect, water_img, source_rect)

            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 25), 1))
            p.drawRect(target_rect)

    def _draw_meters(self, p):
        s = self.ui_scale
        meter_y = self.h_head + self.h_spec + self.h_water + int(4 * s)
        half_w = (self.plot_w - int(16 * s)) / 2.0
        bar_y = meter_y + 12 * s
        bar_h = 5.0 * s
        theme = COLOR_THEMES[self.theme_idx]

        # PEAK / CREST
        rack_l_x = self.pad_l
        peak_val = self.smoothed_peak_db
        peak_str = f"{peak_val:.1f} dBFS" if peak_val > -90 else "--"
        peak_color = QtGui.QColor("#ff4444") if peak_val >= -1.0 else (QtGui.QColor("#ffaa00") if peak_val >= -3.0 else theme["primary"])

        crest_val = self.smoothed_crest_db
        crest_str = f"CREST: {crest_val:.1f} dB" if peak_val > -90 else "CREST: --"

        p.setFont(self.fonts["meter_hdr"])
        p.setPen(QtGui.QColor("#777"))
        p.drawText(QtCore.QPointF(rack_l_x, meter_y + 8 * s), "PEAK")
        p.setPen(peak_color)
        p.drawText(QtCore.QPointF(rack_l_x + 36 * s, meter_y + 8 * s), peak_str)

        p.setPen(QtGui.QColor("#999"))
        p.drawText(QtCore.QPointF(rack_l_x + half_w - p.fontMetrics().horizontalAdvance(crest_str), meter_y + 8 * s), crest_str)

        p.fillRect(QtCore.QRectF(rack_l_x, bar_y, half_w, bar_h), QtGui.QColor(255, 255, 255, 15))
        if peak_val > -60.0:
            norm_pk = np.clip((peak_val + 60.0) / 60.0, 0.0, 1.0)
            p.fillRect(QtCore.QRectF(rack_l_x, bar_y, half_w * norm_pk, bar_h), peak_color)

        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 30), 1))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawRect(QtCore.QRectF(rack_l_x, bar_y, half_w, bar_h))

        p.setFont(self.fonts["meter_scale"])
        p.setPen(QtGui.QColor("#555"))
        p.drawText(QtCore.QPointF(rack_l_x, bar_y + bar_h + 6 * s), "-60")
        p.drawText(QtCore.QPointF(rack_l_x + half_w * (42.0 / 60.0) - 6 * s, bar_y + bar_h + 6 * s), "-18")
        p.drawText(QtCore.QPointF(rack_l_x + half_w - 6 * s, bar_y + bar_h + 6 * s), "0")

        # CORR / M/S
        rack_r_x = self.pad_l + half_w + int(16 * s)
        corr_val_str, status_color = self._get_corr_info()

        mid_pct = self.smoothed_mid_pct
        side_pct = 100.0 - mid_pct
        ms_str = f"M/S: {mid_pct:.0f}% / {side_pct:.0f}%" if not self.corr_is_silent and not self.is_mono else "M/S: --"

        p.setFont(self.fonts["meter_hdr"])
        p.setPen(QtGui.QColor("#777"))
        p.drawText(QtCore.QPointF(rack_r_x, meter_y + 8 * s), "CORR")
        p.setPen(status_color)
        p.drawText(QtCore.QPointF(rack_r_x + 36 * s, meter_y + 8 * s), corr_val_str)

        p.setFont(self.fonts["meter_val"])
        p.setPen(QtGui.QColor("#999"))
        p.drawText(QtCore.QPointF(rack_r_x + half_w - p.fontMetrics().horizontalAdvance(ms_str), meter_y + 8 * s), ms_str)

        cx = rack_r_x + half_w / 2.0
        p.fillRect(QtCore.QRectF(rack_r_x, bar_y, half_w, bar_h), QtGui.QColor(255, 255, 255, 15))

        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 60), 1))
        p.drawLine(QtCore.QPointF(cx, bar_y - 1), QtCore.QPointF(cx, bar_y + bar_h + 1))

        p.setFont(self.fonts["meter_scale"])
        p.setPen(QtGui.QColor("#555"))
        p.drawText(QtCore.QPointF(rack_r_x, bar_y + bar_h + 6 * s), "-1")
        p.drawText(QtCore.QPointF(cx - 2.5 * s, bar_y + bar_h + 6 * s), "0")
        p.drawText(QtCore.QPointF(rack_r_x + half_w - 9 * s, bar_y + bar_h + 6 * s), "+1")

        if not self.corr_is_silent and not self.is_mono:
            c = float(np.clip(self.smoothed_corr, -1.0, 1.0))
            bw = (half_w / 2.0) * abs(c)
            bar_rect = QtCore.QRectF(cx, bar_y, bw, bar_h) if c >= 0.0 else QtCore.QRectF(cx - bw, bar_y, bw, bar_h)
            p.fillRect(bar_rect, status_color)

            ptr_x = cx + (half_w / 2.0) * c
            p.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 1.5))
            p.drawLine(QtCore.QPointF(ptr_x, bar_y - 1.5), QtCore.QPointF(ptr_x, bar_y + bar_h + 1.5))

        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 30), 1))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawRect(QtCore.QRectF(rack_r_x, bar_y, half_w, bar_h))


# ==============================================================================
# メインウィンドウ
# ==============================================================================
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Audio Spectrum Pro v2")
        self.setWindowIcon(QtGui.QIcon(resource_path("app.ico")))  
        self.resize(960, 540)
        self.is_pinned = False
        self.canvas = SpectrumCanvas(self)
        self.setCentralWidget(self.canvas)

    def toggle_pin(self):
        """SetWindowPos だけで最前面 / 解除を切り替える。失敗時は状態を変えない。"""
        new_state = not self.is_pinned
        hwnd = int(self.winId())
        insert_after = HWND_TOPMOST if new_state else HWND_NOTOPMOST
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

        ok = user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags)
        if not ok:
            print(f"[PIN Error] SetWindowPos failed (WinError {ctypes.get_last_error()})")
            return self.is_pinned

        self.is_pinned = new_state
        has_topmost = bool(GetWindowLongPtr(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)
        print(f"[PIN] HWND: {hex(hwnd)} | Target: {'TOPMOST' if new_state else 'NOTOPMOST'} | OS TopMost: {has_topmost}")
        return self.is_pinned

    def closeEvent(self, event):
        self.canvas.shutdown()
        event.accept()


def _excepthook(exc_type, exc, tb):
    """PyQt6 はデフォルトだとイベント内の例外でプロセスごと落ちる。
    差し替えて、エラーを表示するだけで動き続けるようにする。"""
    traceback.print_exception(exc_type, exc, tb)


if __name__ == '__main__':
    # タスクバーで自作アイコンを正しく表示させるおまじない
    myappid = 'mycompany.spectrumpro.hud.v2'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    sys.excepthook = _excepthook
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon(resource_path("app.ico")))
    win = MainWindow()
    app.aboutToQuit.connect(win.canvas.shutdown)
    win.show()
    sys.exit(app.exec())