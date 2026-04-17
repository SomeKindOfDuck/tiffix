import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pyqtgraph as pg
import tifffile
from PyQt6 import QtCore, QtWidgets

from tiffix import align_img, load_mean_image, reshape_img, sine_correction
from tiffix.params import ParameterPanel
from tiffix.save import SaveImagesWorker
from tiffix.theme import ICEBERG_DARK, apply_colorscheme
from tiffix.viewer import ImageCompareWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tiffix")
        central = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.original_img = None
        self.corrected_img = None

        self.viewer = ImageCompareWidget()

        self.params = ParameterPanel()
        self.params.select_dir_requested.connect(self.select_directory)
        self.params.load_requested.connect(self.reload_image)
        self.params.onset_changed.connect(self._on_changed_onset)
        self.params.nframe_changed.connect(self._on_changed_nframe)
        self.params.hshift_changed.connect(self.refresh_image)
        self.params.size_changed.connect(self.resize_img)
        self.params.reset_size_requested.connect(self.reset_size)
        self.params.crop_size_changed.connect(self.crop_image)
        self.params.save_requested.connect(self.save_image)

        self._old_onset = 0

        layout.addWidget(self.viewer, 1)
        layout.addWidget(self.params)

        self.setCentralWidget(central)

        self._reload_timer = QtCore.QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._reload_image_debounced)

    def _reload_image_debounced(self) -> None:
        self.reload_image()

    def _init_autorange(self) -> None:
        self.viewer.left_widget.viewbox.autoRange()

    def crop_image(self):
        params = self.params.get_parameters()
        crop_x = params.get("crop_x")
        crop_y = params.get("crop_y")
        if crop_x is None or crop_y is None:
            return
        min_x, max_x = crop_x
        min_y, max_y = crop_y
        self.viewer.left_widget.show_crop_rect(min_x, max_x, min_y, max_y)
        self.viewer.right_widget.show_crop_rect(min_x, max_x, min_y, max_y)


    def _on_changed_onset(self):
        params = self.params.get_parameters()
        onset = params.get("onset", 0)
        new_nframe_limit = self.n_files - onset - 1

        nframe = params.get("nframe", 1)
        if onset + nframe >= self.n_files:
            self.params.onset_spin.setValue(self._old_onset)
            return

        self._old_onset = onset
        self.params.set_limit("nframe", 1, new_nframe_limit)
        if self.params.is_auto_reload_enabled():
            self._reload_timer.start(250)

    def _on_changed_nframe(self):
        params = self.params.get_parameters()
        nframe = params.get("nframe", 1)
        self.params.set_limit("onset", 0, self.n_files - nframe - 1)
        if self.params.is_auto_reload_enabled():
            self._reload_timer.start(250)

    def resize_img(self):
        params = self.params.get_parameters()
        if self.corrected_img is None:
            return
        ih, iw = self.corrected_img.shape
        width = params.get("width", iw)
        height = params.get("height", ih)
        sx, sy = width / iw, height / ih
        self.viewer.left_widget.set_display_scale(sx, sy)
        self.viewer.right_widget.set_display_scale(sx, sy)

    def reset_size(self):
        self.viewer.left_widget.set_display_scale(1., 1.)
        self.viewer.right_widget.set_display_scale(1., 1.)
        if self.corrected_img is None:
            return
        h, w = self.corrected_img.shape
        self.params.width_spin.setValue(w)
        self.params.height_spin.setValue(h)


    def select_directory(self) -> None:
        try:
            directory = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Select image directory",
                str(Path().cwd()),
                QtWidgets.QFileDialog.Option.DontUseNativeDialog,
            )

            if not directory:
                return

            self.tif_files = sorted(
                list(Path(directory).glob("*.tif")) + list(Path(directory).glob("*.tiff"))
            )
            self.n_files = len(self.tif_files)

            if self.n_files == 0:
                QtWidgets.QMessageBox.warning(
                    self,
                    "No TIFF files",
                    "No .tif or .tiff files found in the selected directory.",
                )
                return

            self.image_dir = Path(directory)
            self.params.set_directory(directory)
            self.reload_image()

            h, w = self.corrected_img.shape

            self.params.set_limit("onset", 0, self.n_files - 1)
            self.params.set_limit("nframe", 1, self.n_files - 1)
            self.params.set_limit("hshift", -w//5, w//5)
            self.params.width_spin.setValue(w)
            self.params.height_spin.setValue(h)

            QtCore.QTimer.singleShot(0, self._init_autorange)
            QtWidgets.QMessageBox.information(
                self,
                "Directory selected",
                f"Selected directory:\n{self.image_dir}",
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to select directory:\n{e}",
            )

    def refresh_image(self):
        params = self.params.get_parameters()
        self.corrected_img = sine_correction(align_img(self.original_img, params.get("hshift", 0)))
        self.viewer.set_images(self.uncorrected_img, self.corrected_img)
        h, w = self.corrected_img.shape
        self.params.width_spin.setValue(w)
        self.params.height_spin.setValue(h)
        self.params.set_limit("crop_x_min", 0, w - 1)
        self.params.set_limit("crop_x_max", 1, w)
        self.params.set_limit("crop_y_min", 0, h - 1)
        self.params.set_limit("crop_y_max", 1, h)
        self.params.crop_x_min_spin.setValue(0)
        self.params.crop_x_max_spin.setValue(w)
        self.params.crop_y_min_spin.setValue(0)
        self.params.crop_y_max_spin.setValue(h)

    def reload_image(self):
        params = self.params.get_parameters()
        onset = params.get("onset", 0)
        nframe = params.get("nframe", 1)
        self.params.set_limit("nframe", 1, self.n_files - onset - 1)
        self.original_img = load_mean_image(self.tif_files, onset, onset+nframe)
        self.uncorrected_img = sine_correction(self.original_img)
        self.refresh_image()

    def save_image(self) -> None:
        try:
            if not hasattr(self, "image_dir"):
                QtWidgets.QMessageBox.warning(
                    self,
                    "No directory selected",
                    "Please select an image directory first.",
                )
                return

            params = self.params.get_parameters()
            hshift = params.get("hshift", 0)
            if self.corrected_img is None:
                return
            h, w = self.corrected_img.shape
            new_width = params.get("width", w)
            new_height = params.get("height", h)

            params = self.params.get_parameters()
            crop_x = params.get("crop_x")
            crop_y = params.get("crop_y")
            if crop_x is None or crop_y is None:
                return
            min_x, max_x = crop_x
            min_y, max_y = crop_y

            scaled_min_x = int(round(min_x * new_width / w))
            scaled_max_x = int(round(max_x * new_width / w))
            scaled_min_y = int(round(min_y * new_height / h))
            scaled_max_y = int(round(max_y * new_height / h))

            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm image correction",
                f"Apply horizontal shift correction of {hshift} px\n\n"
                f"Output image size: {new_width} × {new_height}\n"
                f"(original: {w} × {h})\n"
                f"If this is not desired, please reset the size.\n\n"
                f"Target directory:\n{self.image_dir}\n\n"
                f"Save corrected images to a 'corrected' subdirectory?",
                QtWidgets.QMessageBox.StandardButton.Yes,
                QtWidgets.QMessageBox.StandardButton.No,
            )

            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return

            output_dir = self.image_dir.joinpath("corrected")
            output_dir.mkdir(exist_ok=True)

            img = tifffile.imread(self.tif_files[0])
            vmin, vmax = np.min(img), np.max(img)

            n_stat = min(100, len(self.tif_files))
            for i in range(1, n_stat):
                img = tifffile.imread(self.tif_files[i])
                _min, _max = np.min(img), np.max(img)
                vmin = min(vmin, _min)
                vmax = max(vmax, _max)

            scale_min = vmin * 0.9
            scale_max = vmax * 1.1

            if scale_max <= scale_min:
                raise ValueError(
                    f"Invalid scaling range: scale_min={scale_min}, scale_max={scale_max}"
                )

            max_workers_default = max(1, (os.cpu_count() or 2) - 1)

            worker_count, ok = QtWidgets.QInputDialog.getInt(
                self,
                "Worker count",
                "Number of workers:",
                value=max_workers_default,
                min=1,
                max=max_workers_default,
                step=1,
            )

            if not ok:
                return

            self.save_thread = QtCore.QThread(self)
            self.save_worker = SaveImagesWorker(
                tif_files=self.tif_files,
                output_dir=output_dir,
                hshift=hshift,
                new_width=new_width,
                new_height=new_height,
                scaled_min_x=scaled_min_x,
                scaled_max_x=scaled_max_x,
                scaled_min_y=scaled_min_y,
                scaled_max_y=scaled_max_y,
                scale_min=scale_min,
                scale_max=scale_max,
                max_workers = worker_count
            )

            self.save_worker.moveToThread(self.save_thread)

            self.save_progress_dialog = QtWidgets.QProgressDialog(
                "Saving corrected images...",
                "Cancel",
                0,
                len(self.tif_files),
                self,
            )
            self.save_progress_dialog.setWindowTitle("Saving images")
            self.save_progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
            self.save_progress_dialog.setMinimumDuration(0)
            self.save_progress_dialog.setValue(0)

            self.save_thread.started.connect(self.save_worker.run)
            self.save_worker.finished.connect(self._on_save_finished)
            self.save_worker.error.connect(self._on_save_error)
            self.save_worker.progress.connect(self._on_save_progress)

            self.save_worker.finished.connect(self.save_thread.quit)
            self.save_worker.finished.connect(self.save_worker.deleteLater)
            self.save_thread.finished.connect(self.save_thread.deleteLater)

            self.save_thread.start()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to save corrected images:\n{e}",
            )

    def _on_save_progress(self, done: int, total: int) -> None:
        if hasattr(self, "save_progress_dialog") and self.save_progress_dialog is not None:
            self.save_progress_dialog.setMaximum(total)
            self.save_progress_dialog.setValue(done)
            self.save_progress_dialog.setLabelText(
                f"Saving corrected images... ({done}/{total})"
            )

    def _on_save_finished(self) -> None:
        if hasattr(self, "save_progress_dialog") and self.save_progress_dialog is not None:
            self.save_progress_dialog.close()
            self.save_progress_dialog = None

        QtWidgets.QMessageBox.information(
            self,
            "Done",
            "Corrected images were saved successfully.",
        )

    def _on_save_error(self, message: str) -> None:
        if hasattr(self, "save_progress_dialog") and self.save_progress_dialog is not None:
            self.save_progress_dialog.close()
            self.save_progress_dialog = None

        QtWidgets.QMessageBox.critical(
            self,
            "Error",
            f"Failed to save corrected images:\n{message}",
        )

def main():
    app = QtWidgets.QApplication(sys.argv)
    apply_colorscheme(app, ICEBERG_DARK)
    pg.setConfigOptions(imageAxisOrder="row-major")

    window = MainWindow()
    window.resize(1200, 600)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
