import sys
from pathlib import Path

import cv2
import numpy as np
import pyqtgraph as pg
import tifffile
from PyQt6 import QtCore, QtWidgets

from tiffix import align_img, load_mean_image, reshape_img, sine_correction
from tiffix.params import ParameterPanel
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
        self.params.save_requested.connect(self.save_image)

        self._old_onset = 0

        layout.addWidget(self.viewer, 1)
        layout.addWidget(self.params)

        self.setCentralWidget(central)

        self._reload_timer = QtCore.QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._reload_image_debounced)

        # self._rsize_timer = QtCore.QTimer(self)
        # self._rsize_timer.setSingleShot(True)
        # self._rsize_timer.timeout.connect(self._resize_image_debouce)

    def _reload_image_debounced(self) -> None:
        self.reload_image()

    # def _resize_image_debouce(self) -> None:
    #     self.resize_img()

    def _init_autorange(self) -> None:
        self.viewer.left_widget.viewbox.autoRange()

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

            for tf in self.tif_files:
                output_path = output_dir / tf.name

                img = tifffile.imread(tf)
                reshaped_img = reshape_img(img)
                aligned_img = align_img(reshaped_img, hshift)
                corrected_img = sine_correction(aligned_img)
                corrected_img = cv2.resize(corrected_img, (new_width, new_height))

                corrected_img = np.clip(corrected_img, scale_min, scale_max)
                corrected_img = (corrected_img - scale_min) / (scale_max - scale_min)
                corrected_img = corrected_img * 65535.0
                corrected_img = corrected_img.astype(np.uint16)

                tifffile.imwrite(output_path, corrected_img)

            QtWidgets.QMessageBox.information(
                self,
                "Done",
                f"Corrected images were saved to:\n{output_dir}",
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to save corrected images:\n{e}",
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
