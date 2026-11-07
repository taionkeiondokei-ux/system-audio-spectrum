# 🎵 System Audio Spectrum Pro v2

A cyberpunk-themed HUD-style real-time audio spectrum analyzer for Windows (WASAPI Loopback).  
It visualizes whatever your PC is playing: spectrum, waterfall, stereo field, peak / crest, and now-playing info, all in one resizable window.

<img width="426" height="240" alt="Video Project" src="https://github.com/user-attachments/assets/83610b82-b066-44ca-8efb-e12ca6dcad88" />


---

## 🌐 Language
- [English](#-english)
- [日本語 (Japanese)](#-日本語-japanese)

---

## 🇺🇸 English

### 💡 Features

#### 1. Spectrum that is pleasant to watch
Tuned for visual comfort, not just a raw FFT dump.
- **FFT**: 4096-point FFT with a **Blackman window** for low side-lobe leakage. Log frequency axis from 20 Hz to 20 kHz, level range −75 dB to 0 dB.
- **Fluid response**: Frame-rate-independent exponential smoothing, plus a peak-hold line that decays at **16.8 dB/s**.
- **Waterfall**: A 64-frame history strip under the spectrum, colored by the current theme.

#### 2. Layout that scales cleanly
- **Aspect-ratio-preserving layout**: The HUD keeps its 16:9 proportions and stays centered when you resize or go full screen (minimum 640×360).
- **Balanced text scaling**: Fonts and HUD elements grow with square-root scaling, so they do not become oversized on large or 4K displays.
- **Light plotting**: The spectrum polyline is decimated to roughly 800 vertices on wide windows to keep rendering light.
- **Auto-reconnect**: Follows the default playback device. If the output device is switched, or the audio stays silent for about 3 seconds, the loopback capture is reopened automatically.

#### 3. Now Playing & media control (Windows Media / GSMTC)
- Shows **album art, title, artist, album, track number, play state, and a position / duration timeline** for whatever is playing in Spotify, browsers, etc.
- On-screen buttons for **Previous / Play-Pause / Next**.
- Also shows the source app, sample rate, system volume (or MUTE), current theme, FPS, the capture device name, and a clock with date.

#### 4. Meters
- **Spectrum & Waterfall**: Live spectrum with peak-hold, plus frequency history.
- **Lissajous goniometer**: Stereo width and phase, drawn from the latest 128 samples of L/R.
- **CORR**: Left/right correlation, −1 to +1, color-coded. A mono source shows +1.00.
- **M/S**: Energy ratio of the Mid (L+R) and Side (L−R) components, in %.
- **PEAK**: Sample peak in dBFS, with instant attack and a smoothed release. Turns amber at −3 dBFS or higher and red at −1 dBFS or higher.
- **CREST**: Crest factor (peak minus RMS, in dB), an indicator of how dynamic the signal is.
- **CENTROID**: Spectral centroid in kHz, an indicator of the "brightness" of the sound.

### ⚠️ Specifications & Limitations
- **Spectrum, waterfall, and centroid are computed from a mono mix.** The left and right channels are summed and averaged, `(L + R) / 2`, before the FFT. A perfectly out-of-phase signal (L = −R) therefore cancels out and shows **zero** there. PEAK, CREST, the goniometer, CORR, and M/S use the left and right channels separately, so out-of-phase material still shows up in those meters (CORR goes to −1.00).
- **PEAK is a sample peak, not a true peak.** There is no oversampling.
- **Only the first two channels are used.** With multichannel output (e.g. 5.1), only the first two channels (front L/R) are analyzed.
- **Windows only.** Capture relies on WASAPI loopback, and the media/volume features rely on Windows APIs. Track info needs `winsdk`, and volume/mute display needs `pycaw`. Without them the app still runs, but those items are not shown.

### ⌨️ Controls
| Control | Action |
| :--- | :--- |
| **`C` key** | Cycle color themes (Cyberpunk Cyan / Neon Magenta / Amber Gold / Matrix Green / Ice White) |
| **Top-right [PIN]** | Toggle Always-on-Top mode |
| **Bottom-right buttons (⏮ ⏯ ⏭)** | Previous / Play-Pause / Next |

### 📥 Download (Pre-built Executable)
No Python environment required. Download either of the following from the **[Releases](https://github.com/taionkeiondokei-ux/system-audio-spectrum/releases)** page:

- **Standalone EXE (`SystemAudioSpectrumPro.exe`)**: Easiest option. Just download and run (no extraction needed).
- **Portable ZIP (`SystemAudioSpectrumPro_v2.0.0_portable.zip`)**: Faster startup. Extract the zip and run `SystemAudioSpectrumPro.exe` inside the folder (keep all files together).

*(Since this is an unsigned community app, Windows SmartScreen may show a warning. Click "More info" -> "Run anyway".)*


### 🛠️ Running from Source (Python 3.10+)
```bash
pip install -r requirements.txt
python spectrum_clean.py
```
Main libraries: PyQt6, NumPy, PyAudioWPatch, plus `winsdk` (track info) and `pycaw` / `comtypes` (volume) as optional features. Place `app.ico` next to the script to show the window icon.

### 📦 Building the Executable (PyInstaller)
```bash
pip install pyinstaller
pyinstaller --noconsole --onedir --clean --icon=app.ico --add-data "app.ico;." spectrum_clean.py
```
The result is in `dist/spectrum_clean/`. `--onedir` starts much faster than `--onefile`; distribute the whole folder as a zip.

---

## 🇯🇵 日本語 (Japanese)

### 💡 特長

#### 1. 見ていて気持ちいいスペクトラム
単なるFFTの垂れ流しではなく、見た目の心地よさを重視してチューニングしています。
- **FFT**: 4096点FFTに**Blackman窓**を適用し、サイドローブの漏れを抑制。周波数軸は20 Hz〜20 kHzの対数軸、レベル表示は−75 dB〜0 dBです。
- **滑らかな動き**: フレームレートに依存しない指数平滑化と、**16.8 dB/s**で減衰するピークホールド線。
- **ウォーターフォール**: スペクトラム下に64フレーム分の履歴を表示。色は選択中のテーマに連動します。

#### 2. リサイズしても崩れないレイアウト
- **アスペクト比維持**: ウィンドウを拡大・フルスクリーンにしても16:9の比率を保って中央に表示します（最小サイズ 640×360）。
- **文字が巨大化しないスケーリング**: 平方根スケーリングで、大画面や4Kでも文字やHUDが肥大化しません。
- **描画の軽量化**: 横幅が広いときはスペクトラム線の頂点を約800点に間引いて負荷を抑えます。
- **自動再接続**: 既定の再生デバイスに追従します。出力デバイスを切り替えたとき、または約3秒無音が続いたときに、ループバックキャプチャを自動で開き直します。

#### 3. 再生中情報 & メディア操作（Windowsメディア / GSMTC）
- Spotifyやブラウザなどで再生中の**ジャケット写真、曲名、アーティスト名、アルバム名、トラック番号、再生状態、再生位置／曲の長さ**を表示します。
- 画面上のボタンで**前の曲 / 再生・一時停止 / 次の曲**を操作できます。
- そのほか、再生元アプリ、サンプルレート、システム音量（またはMUTE）、現在のテーマ、FPS、キャプチャ中のデバイス名、日付付きの時計も表示します。

#### 4. メーター群
- **スペクトラム & ウォーターフォール**: ピークホールド付きのリアルタイム表示と周波数履歴。
- **リサージュ・ゴニオメーター**: 直近128サンプルのL/Rから、ステレオの広がりと位相を表示。
- **CORR**: 左右の相関度（−1〜+1）を色分けして表示。モノラル音源では+1.00になります。
- **M/S**: Mid（L+R）とSide（L−R）のエネルギー比（％）。
- **PEAK**: サンプルピークをdBFSで表示。立ち上がりは即時で、減衰は平滑化されます。−3 dBFS以上でオレンジ、−1 dBFS以上で赤になります。
- **CREST**: クレストファクター（ピーク − RMS、dB）。音のダイナミクス感の目安です。
- **CENTROID**: スペクトル重心（kHz）。音の明るさの目安です。

### ⚠️ 仕様・制限事項
- **スペクトラム、ウォーターフォール、CENTROIDはモノラルミックスから計算しています。** FFTの前に左右を足して平均（`(L + R) / 2`）しているため、完全な逆位相の音（L = −R）は打ち消し合って、これらの表示では**ゼロ**になります。PEAK、CREST、ゴニオメーター、CORR、M/Sは左右を別々に使うので、逆位相の音もこれらには表示されます（CORRは−1.00になります）。
- **PEAKはサンプルピークで、トゥルーピークではありません。** オーバーサンプリングは行っていません。
- **解析に使うのは先頭の2チャンネルだけです。** 5.1chなどのマルチチャンネル出力では、先頭の2チャンネル（フロントL/R）のみを解析します。
- **Windows専用です。** キャプチャはWASAPIループバック、メディア・音量機能はWindows APIに依存します。曲情報には `winsdk`、音量・ミュート表示には `pycaw` が必要で、無くても起動はしますが、その項目は表示されません。

### ⌨️ 操作
| 操作 | 内容 |
| :--- | :--- |
| **`C` キー** | カラーテーマの切り替え（Cyberpunk Cyan / Neon Magenta / Amber Gold / Matrix Green / Ice White） |
| **画面右上 [PIN]** | 最前面表示の固定 / 解除 |
| **右下のボタン（⏮ ⏯ ⏭）** | 前の曲 / 再生・一時停止 / 次の曲 |

### 📥 ダウンロード（exeで使う場合）
Python環境は不要です。**[Releases](https://github.com/taionkeiondokei-ux/system-audio-spectrum/releases)** ページから以下のいずれか1つをダウンロードしてください：

- **Standalone EXE (`SystemAudioSpectrumPro.exe`)**: 一番手軽。解凍不要でそのままダブルクリックで起動できます。
- **Portable ZIP (`SystemAudioSpectrumPro_v2.0.0_portable.zip`)**: 起動が高速。zipを展開し、フォルダ内の `SystemAudioSpectrumPro.exe` を実行してください（中身のファイル一式は同じ場所に置いておいてください）。

*(※個人開発の未署名アプリのため、Windows SmartScreenの警告が出た場合は「詳細情報」→「実行」を押してください)*

### 🛠️ ソースコードから動かす場合（Python 3.10以上推奨）
```bash
pip install -r requirements.txt
python spectrum_clean.py
```
主なライブラリ: PyQt6、NumPy、PyAudioWPatch。オプション機能として `winsdk`（曲情報）と `pycaw` / `comtypes`（音量表示）。ウィンドウアイコンを表示するには、スクリプトと同じ場所に `app.ico` を置いてください。

### 📦 exeのビルド方法（PyInstaller）
```bash
pip install pyinstaller
pyinstaller --noconsole --onedir --clean --icon=app.ico --add-data "app.ico;." spectrum_clean.py
```
出力は `dist/spectrum_clean/` に作られます。`--onedir` は `--onefile` より起動がかなり速くなります。配布するときはフォルダごとzipにしてください。

---

## 📄 License / ライセンス

This project is licensed under the **GNU General Public License v3.0** (see [LICENSE](LICENSE)).
It uses PyQt6, which is also available under the GPL v3. The source code for the distributed executable is available in this repository.

本プロジェクトは **GNU General Public License v3.0** のもとで公開しています（[LICENSE](LICENSE) を参照）。
PyQt6（GPL v3）を使用しているため、配布するexeに対応するソースコードは、このリポジトリで公開しています。

## 📜 Credits
- Demo Music: Heuse - Pill [NCS Release]
