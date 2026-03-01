import os
import sys
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QSpinBox, QMessageBox, QTextEdit, QGroupBox,
    QFormLayout
)


def app_dir() -> Path:
    """実行ファイル(.exe)でも .py でも動くようにベースディレクトリを返す。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_ffmpeg() -> Path | None:
    """
    優先順位:
      1) アプリ同梱: <app>/bin/ffmpeg.exe
      2) PATH上の ffmpeg
    """
    bundled = app_dir() / "bin" / "ffmpeg.exe"
    if bundled.exists():
        return bundled

    # PATH検索（ffmpeg がインストール済みなら使える）
    from shutil import which
    p = which("ffmpeg")
    if p:
        return Path(p)
    return None


def build_ffmpeg_gif_command(
    ffmpeg_path: Path,
    input_mp4: Path,
    output_gif: Path,
    start_sec: int,
    duration_sec: int,
    width_px: int,
    fps: int,
) -> list[str]:
    """
    パレット生成→適用の2パスを 1コマンド内で完結させる（品質/サイズが良い定番）。
    """
    vf = (
        f"fps={fps},"
        f"scale={width_px}:-1:flags=lanczos,"
        f"split[s0][s1];"
        f"[s0]palettegen[p];"
        f"[s1][p]paletteuse=dither=bayer"
    )
    return [
        str(ffmpeg_path),
        "-y",
        "-ss", str(start_sec),
        "-t", str(duration_sec),
        "-i", str(input_mp4),
        "-vf", vf,
        str(output_gif),
    ]


class ConvertWorker(QThread):
    log = Signal(str)
    done = Signal(bool, str)

    def __init__(self, cmd: list[str], cwd: Path):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd

    def run(self) -> None:
        try:
            self.log.emit("Running:\n" + " ".join(self.cmd) + "\n")
            p = subprocess.Popen(
                self.cmd,
                cwd=str(self.cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert p.stdout is not None
            for line in p.stdout:
                self.log.emit(line.rstrip())

            rc = p.wait()
            if rc == 0:
                self.done.emit(True, "変換が完了しました。")
            else:
                self.done.emit(False, f"FFmpegがエラー終了しました（code={rc}）。ログを確認してください。")
        except Exception as e:
            self.done.emit(False, f"例外が発生しました: {e}")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP4 → GIF 変換ツール（ローカル完結）")
        self.resize(760, 520)

        self.ffmpeg_path = find_ffmpeg()

        # --- UI ---
        root = QVBoxLayout(self)

        # FFmpeg 状態
        self.ffmpeg_label = QLabel()
        self._update_ffmpeg_label()
        root.addWidget(self.ffmpeg_label)

        # 入力/出力
        io_box = QGroupBox("入出力")
        io_lay = QFormLayout(io_box)

        self.in_edit = QLineEdit()
        self.in_btn = QPushButton("MP4を選択…")
        self.in_btn.clicked.connect(self.pick_input)

        in_row = QHBoxLayout()
        in_row.addWidget(self.in_edit, 1)
        in_row.addWidget(self.in_btn)
        io_lay.addRow("入力MP4:", in_row)

        self.out_edit = QLineEdit()
        self.out_btn = QPushButton("保存先を選択…")
        self.out_btn.clicked.connect(self.pick_output)

        out_row = QHBoxLayout()
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(self.out_btn)
        io_lay.addRow("出力GIF:", out_row)

        root.addWidget(io_box)

        # 設定
        set_box = QGroupBox("変換設定")
        set_lay = QFormLayout(set_box)

        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 60 * 60)
        self.start_spin.setValue(0)

        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(1, 60 * 60)
        self.dur_spin.setValue(5)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(120, 3840)
        self.width_spin.setValue(480)

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(12)

        set_lay.addRow("開始秒（ss）:", self.start_spin)
        set_lay.addRow("長さ（t）秒:", self.dur_spin)
        set_lay.addRow("出力幅（px）:", self.width_spin)
        set_lay.addRow("FPS:", self.fps_spin)

        root.addWidget(set_box)

        # 実行ボタン
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("GIFに変換")
        self.run_btn.clicked.connect(self.run_convert)
        self.run_btn.setEnabled(self.ffmpeg_path is not None)
        btn_row.addStretch(1)
        btn_row.addWidget(self.run_btn)
        root.addLayout(btn_row)

        # ログ
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        root.addWidget(QLabel("ログ:"))
        root.addWidget(self.log, 1)

        self.worker: ConvertWorker | None = None

    def _update_ffmpeg_label(self):
        if self.ffmpeg_path:
            self.ffmpeg_label.setText(f"FFmpeg: OK  ({self.ffmpeg_path})")
        else:
            self.ffmpeg_label.setText(
                "FFmpeg: 見つかりません。bin/ffmpeg.exe を置くか、ffmpeg をPATHに通してください。"
            )
            self.ffmpeg_label.setStyleSheet("color: red;")

    def pick_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "MP4を選択", "", "Video Files (*.mp4 *.mov *.m4v *.mkv);;All Files (*.*)"
        )
        if path:
            self.in_edit.setText(path)
            # 出力先を未指定なら同フォルダに提案
            if not self.out_edit.text().strip():
                p = Path(path)
                self.out_edit.setText(str(p.with_suffix(".gif")))

    def pick_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "GIFの保存先", "", "GIF Files (*.gif);;All Files (*.*)"
        )
        if path:
            if not path.lower().endswith(".gif"):
                path += ".gif"
            self.out_edit.setText(path)

    def append_log(self, s: str):
        self.log.append(s)

    def run_convert(self):
        if not self.ffmpeg_path:
            QMessageBox.critical(self, "FFmpegが見つかりません", "bin/ffmpeg.exe を配置してください。")
            return

        in_path = Path(self.in_edit.text().strip().strip('"'))
        out_path = Path(self.out_edit.text().strip().strip('"'))

        if not in_path.exists():
            QMessageBox.warning(self, "入力エラー", "入力MP4が見つかりません。")
            return

        if not out_path.parent.exists():
            QMessageBox.warning(self, "出力エラー", "出力先フォルダが存在しません。")
            return

        cmd = build_ffmpeg_gif_command(
            ffmpeg_path=self.ffmpeg_path,
            input_mp4=in_path,
            output_gif=out_path,
            start_sec=int(self.start_spin.value()),
            duration_sec=int(self.dur_spin.value()),
            width_px=int(self.width_spin.value()),
            fps=int(self.fps_spin.value()),
        )

        self.log.clear()
        self.run_btn.setEnabled(False)
        self.append_log("開始します…")

        self.worker = ConvertWorker(cmd=cmd, cwd=app_dir())
        self.worker.log.connect(self.append_log)
        self.worker.done.connect(self.on_done)
        self.worker.start()

    def on_done(self, ok: bool, msg: str):
        self.run_btn.setEnabled(True)
        if ok:
            QMessageBox.information(self, "完了", msg)
        else:
            QMessageBox.critical(self, "失敗", msg)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()