# gif_maker
短い動画ファイルをgif化するツール

# GifMaker（MP4 → GIF 変換ツール / ローカル完結）

ローカルの MP4 動画から、指定区間を GIF に変換する Windows 向けツールです。  
外部アップロード不要で、オフライン環境でも利用できます。

## 特徴
- MP4 等の動画から GIF を生成
- 開始秒 / 長さ / 幅 / FPS を指定可能
- ローカル完結（外部通信なし）
- 変換エンジン：FFmpeg（同梱またはPATH）

## 動作環境
- Windows 10 / 11（64bit）

## 実行方法（Windows / 配布版）
1. GitHub の **Releases** から `GifMaker_win64_*.zip` をダウンロード
2. zip を解凍
3. `GifMaker.exe` を起動
4. MP4 を選択 → 出力GIFを指定 → 「GIFに変換」

> ※ 配布版は `GifMaker.exe` 単体では動きません。  
> 解凍したフォルダ一式（`_internal` や `bin` 含む）が必要です。

## ※注意　開発者向け：ソースから起動
### 1) フォルダ構成
プロジェクトのディレクトリ直下に `bin/ffmpeg.exe` を配置してください。
