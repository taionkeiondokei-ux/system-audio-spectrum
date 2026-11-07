# 🎵 System Audio Spectrum Pro v2

A cyberpunk-themed HUD-style real-time audio spectrum analyzer for Windows (WASAPI Loopback).  
Designed with both **aesthetic pleasure ("satisfying just to watch")** and **studio-grade audio analysis** in mind.

<img width="426" height="240" alt="Video Project" src="https://github.com/user-attachments/assets/7d42144d-36ac-47b0-b565-59765a38cdcf" />




---

## 🌐 Language
- [English](#-english)
- [日本語 (Japanese)](#-日本語-japanese)

---

## 🇺🇸 English

### 💡 Philosophy & Key Features

#### 1. "Visually Satisfying" Waveform Dynamics
Engineered for human visual comfort, not just a raw FFT output.
- **Fluid Response**: Combines high-speed sampling, frame-rate-independent exponential smoothing, and natural peak decay (16.8 dB/s) to capture the true energy and groove of your music.
- **Blackman Window**: Drastically suppresses side-lobe leakage for razor-sharp frequency peaks.

#### 2. Smart Scaling & Low CPU/GPU Load
- **Balanced Resizing**: Custom non-linear scaling (square-root scaling) prevents fonts and HUD elements from becoming comically oversized on large or 4K monitors.
- **Polygon Decimation**: Automatically decimates plot vertices based on window width to keep rendering lightweight and butter-smooth at any resolution.

#### 3. Album Art & Media Control Integration
- Seamlessly integrates with Windows Media (GSMTC). Displays **Album Art, Track Title, Artist, and Track Timeline** automatically from Spotify, browsers, etc.
- Built-in on-screen controls for [Play/Pause] and [Skip].

#### 4. Studio-Grade Precision Meters
- **Real-Time Spectrum & Waterfall**: High-resolution FFT plot with frequency history spectrogram.
- **Lissajous Goniometer**: Visualizes stereo field width and phase.
- **Stereo Correlation & Mid/Side Ratio**: Accurately tracks mono compatibility and stereo spread.
- **Peak Level & Crest Factor**: Real-time measurement of dynamic punch and loudness.
- **Spectral Centroid (OSD)**: Displays the perceptual "brightness" center of the audio.

### ⌨️ Shortcuts & Controls
| Control | Action |
| :--- | :--- |
| **`C` Key** | Cycle color themes (Cyan / Magenta / Gold / Green / White) |
| **Top-Right [PIN]** | Toggle Always-on-Top mode |
| **Top-Right Buttons** | Media control (Previous / Play & Pause / Next) |

### 📥 Download (Pre-built Executable)
No Python environment required.
1. Download the latest `.exe` from the **[Releases](releases)** section on the right.
2. Double-click to run.  
   *(Since this is an unsigned community app, Windows SmartScreen may show a warning. Click "More info" -> "Run anyway".)*

### 🛠️ Running from Source (Python 3.10+)
```bash
pip install -r requirements.txt
python spectrum_clean.py
```

---

## 🇯🇵 日本語 (Japanese)

### 💡 こだわりポイント

#### 1. 人が見て「気持ちいい」波形のアニメーション
単なるFFT表示ではなく、人間の視覚が心地よいと感じるレスポンスを追求しています。
- **滑らかな動特性**: 高速サンプリングと指数平滑化、自然なピーク減衰（Peak Decay）を組み合わせ、音楽のダイナミクスがダイレクトに伝わる挙動にチューニング。
- **Blackman窓関数の採用**: サイドローブのノイズを抑え、クリアでシャープな周波数ピークを描画。

#### 2. リサイズしても破綻しないスマートなレイアウト＆負荷対策
- **文字が巨大化しないスケーリング**: 画面をフルスクリーンや大画面に引き伸ばしても文字が野暮ったく肥大化しないよう、独自のスケーリング調整（平方根スケーリング）を導入。
- **計算量の最適化**: 解像度を上げても描画頂点を適切に間引く処理を行っており、4Kディスプレイ等の大画面環境でもCPU/GPU負荷を抑えて軽快に動作します。

#### 3. ジャケット写真＆メディアコントロール連携
- Windowsのメディア機能（GSMTC）と統合。Spotifyやブラウザ等で再生中の**楽曲ジャケット写真、曲名、アーティスト名、再生時間**を自動取得して表示。
- アプリ上から直接 [再生/一時停止] [スキップ] などのメディア操作も可能です。

#### 4. 眺めて楽しい、本格的なプロ仕様メーター群
- **リアルタイム・スペクトラム & ウォーターフォール**（帯域別履歴表示）
- **リサージュ・ゴニオメーター**: ステレオの広がりをグラフィカルに可視化
- **ステレオ相関度（CORR） & Mid/Side バランス比**
- **PEAK & クレストファクター（音圧感・ダイナミクス感の指標）**
- **スペクトル重心（CENTROID）**: 音色の明るさを数値化

### ⌨️ ショートカット & 操作
| 操作 | 内容 |
| :--- | :--- |
| **`C` キー** | カラーテーマの切り替え（Cyan / Magenta / Gold / Green / White） |
| **画面右上 [PIN]** | 最前面表示の固定 / 解除 |
| **右上の操作ボタン** | 楽曲のスキップ・再生・一時停止 |

### 📥 ダウンロード（exeで使う場合）
1. 画面右側の **[Releases](releases)** から最新版の `.exe` をダウンロードしてください。
2. そのままダブルクリックで起動します。  
   *(※個人開発の未署名アプリのため、Windows SmartScreenの警告が出た場合は「詳細情報」→「実行」を押してください)*

### 🛠️ ソースコードから動かす場合（Python 3.10以上推奨）
```bash
pip install -r requirements.txt
python spectrum_clean.py
```

---

## 📜 Credits
- Demo Music: Heuse - Pill [NCS Release]
