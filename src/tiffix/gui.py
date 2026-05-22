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
from tiffix.save import SaveImagesWorker, preprocess_corrected_image
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
        self.params.crop_size_changed.connect(self.crop_image)
        self.params.fov_changed.connect(self.refresh_image)
        self.params.output_size_changed.connect(self.refresh_image)
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

    def _get_display_px_per_um(self, params: dict) -> float:
        width_um = params.get("fov_width_um")
        if width_um is None or width_um <= 0:
            return 1.0

        display_h, display_w = self.corrected_display_img.shape[:2]
        return display_w / width_um

    def _get_output_shape(self, params: dict) -> tuple[int, int] | None:
        output_width_px = params.get("output_width_px")
        output_height_px = params.get("output_height_px")

        if output_width_px is None or output_height_px is None:
            return None

        if output_width_px <= 0 or output_height_px <= 0:
            return None

        return int(output_width_px), int(output_height_px)

    def _resize_for_display(self, img: np.ndarray, params: dict) -> np.ndarray:
        output_shape = self._get_output_shape(params)

        if output_shape is None:
            return img

        new_width, new_height = output_shape

        if (new_height, new_width) == img.shape[:2]:
            return img

        return cv2.resize(
            img,
            (new_width, new_height),
            interpolation=cv2.INTER_LINEAR,
        )

    def crop_image(self):
        if not hasattr(self, "corrected_display_img"):
            return

        params = self.params.get_parameters()

        crop_x_px = params.get("crop_x_px")
        crop_y_px = params.get("crop_y_px")

        if crop_x_px is None or crop_y_px is None:
            return

        min_x, max_x = crop_x_px
        min_y, max_y = crop_y_px

        h, w = self.corrected_display_img.shape[:2]

        min_x = max(0, min(min_x, w - 1))
        max_x = max(1, min(max_x, w))
        min_y = max(0, min(min_y, h - 1))
        max_y = max(1, min(max_y, h))

        self.viewer.left_widget.show_crop_rect(min_x, max_x, min_y, max_y)
        self.viewer.right_widget.show_crop_rect(min_x, max_x, min_y, max_y)

    def _crop_um_to_display_px(
        self,
        crop_x_um: tuple[int, int],
        crop_y_um: tuple[int, int],
        params: dict,
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        px_per_um = self._get_display_px_per_um(params)

        min_x_um, max_x_um = crop_x_um
        min_y_um, max_y_um = crop_y_um

        min_x = int(round(min_x_um * px_per_um))
        max_x = int(round(max_x_um * px_per_um))
        min_y = int(round(min_y_um * px_per_um))
        max_y = int(round(max_y_um * px_per_um))

        h, w = self.corrected_display_img.shape[:2]

        min_x = max(0, min(min_x, w - 1))
        max_x = max(1, min(max_x, w))
        min_y = max(0, min(min_y, h - 1))
        max_y = max(1, min(max_y, h))

        return (min_x, max_x), (min_y, max_y)

    def _on_changed_onset(self):
        params = self.params.get_parameters()
        onset = params.get("onset", 0)
        nframe = params.get("nframe", 1)

        max_onset = max(0, self.n_files - nframe - 1)

        if onset > max_onset:
            self.params.onset_spin.setValue(max_onset)
            return

        new_nframe_limit = max(1, self.n_files - onset - 1)
        self.params.set_limit("nframe", 1, new_nframe_limit)

        if self.params.is_auto_reload_enabled():
            self._reload_timer.start(250)

    def _on_changed_nframe(self):
        params = self.params.get_parameters()
        nframe = params.get("nframe", 1)
        onset = params.get("onset", 0)

        max_nframe = max(1, self.n_files - onset - 1)

        if nframe > max_nframe:
            self.params.nframe_spin.setValue(max_nframe)
            return

        if self.params.is_auto_reload_enabled():
            self._reload_timer.start(250)

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
            self.reload_image(reset_geometry=True)

            h, w = self.corrected_img.shape

            self.params.set_limit("onset", 0, self.n_files - 1)
            self.params.set_limit("nframe", 1, self.n_files - 1)
            self.params.set_limit("hshift", -w//5, w//5)

            self.params.set_limit("save_start", 0, self.n_files - 1)
            self.params.set_limit("save_end", 0, self.n_files - 1)
            self.params.save_start_spin.setValue(0)
            self.params.save_end_spin.setValue(self.n_files - 1)

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

    def refresh_image(self, reset_crop: bool = False):
        params = self.params.get_parameters()

        self.corrected_img = sine_correction(
            align_img(self.original_img, params.get("hshift", 0))
        )

        self.uncorrected_display_img = self._resize_for_display(
            self.uncorrected_img,
            params,
        )
        self.corrected_display_img = self._resize_for_display(
            self.corrected_img,
            params,
        )

        self.viewer.set_images(
            self.uncorrected_display_img,
            self.corrected_display_img,
        )

        output_width_px = params.get("output_width_px")
        output_height_px = params.get("output_height_px")

        if output_width_px is not None and output_height_px is not None:
            self.params.set_limit("crop_x_min", 0, output_width_px - 1)
            self.params.set_limit("crop_x_max", 1, output_width_px)
            self.params.set_limit("crop_y_min", 0, output_height_px - 1)
            self.params.set_limit("crop_y_max", 1, output_height_px)

            if reset_crop:
                self.params.crop_x_min_spin.setValue(0)
                self.params.crop_x_max_spin.setValue(output_width_px)
                self.params.crop_y_min_spin.setValue(0)
                self.params.crop_y_max_spin.setValue(output_height_px)

        self.crop_image()

    def reload_image(self, reset_geometry: bool = False):
        params = self.params.get_parameters()
        onset = params.get("onset", 0)
        nframe = params.get("nframe", 1)
        self.params.set_limit("nframe", 1, self.n_files - onset - 1)

        self.original_img = load_mean_image(self.tif_files, onset, onset + nframe)
        self.uncorrected_img = sine_correction(self.original_img)

        if reset_geometry:
            preview_corrected_img = sine_correction(
                align_img(self.original_img, params.get("hshift", 0))
            )
            h, w = preview_corrected_img.shape

            self.params.set_fov_values(width=w, height=h)
            self.params.set_output_size_values(width=w, height=h)

        self.refresh_image(reset_crop=reset_geometry)

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

            save_start = params.get("save_start", 0)
            save_end = params.get("save_end", self.n_files - 1)

            if save_start > save_end:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Invalid save range",
                    "Save start index must be less than or equal to save end index.",
                )
                return

            selected_tif_files = self.tif_files[save_start:save_end + 1]

            if len(selected_tif_files) == 0:
                QtWidgets.QMessageBox.warning(
                    self,
                    "No images selected",
                    "No TIFF files are included in the selected save range.",
                )
                return

            if self.corrected_img is None:
                return

            if self.corrected_img is None:
                return

            output_shape = self._get_output_shape(params)
            if output_shape is None:
                return

            new_width, new_height = output_shape

            crop_x = params.get("crop_x_px")
            crop_y = params.get("crop_y_px")
            if crop_x is None or crop_y is None:
                return

            scaled_min_x, scaled_max_x = crop_x
            scaled_min_y, scaled_max_y = crop_y

            final_width = max(0, scaled_max_x - scaled_min_x)
            final_height = max(0, scaled_max_y - scaled_min_y)

            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm image correction",
                f"Apply horizontal shift correction of {hshift} px\n\n"
                f"Resized image size: {new_width} × {new_height} px\n"
                f"Crop range: "
                f"x={scaled_min_x}-{scaled_max_x} px, "
                f"y={scaled_min_y}-{scaled_max_y} px\n"
                f"Final saved image size: {final_width} × {final_height} px\n\n"
                f"Target directory:\n{self.image_dir}\n\n"
                f"Save corrected images to a 'corrected' subdirectory?",
                QtWidgets.QMessageBox.StandardButton.Yes,
                QtWidgets.QMessageBox.StandardButton.No,
            )

            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return

            output_dir = self.image_dir.joinpath("corrected")
            output_dir.mkdir(exist_ok=True)

            stat_files = selected_tif_files[:min(100, len(selected_tif_files))]

            stat_img = preprocess_corrected_image(
                tf_path=stat_files[0],
                hshift=hshift,
                new_width=new_width,
                new_height=new_height,
                scaled_min_x=scaled_min_x,
                scaled_max_x=scaled_max_x,
                scaled_min_y=scaled_min_y,
                scaled_max_y=scaled_max_y,
            )

            if stat_img.size == 0:
                raise ValueError("Crop range produced an empty image.")

            vmin, vmax = np.min(stat_img), np.max(stat_img)

            for tf_path in stat_files[1:]:
                stat_img = preprocess_corrected_image(
                    tf_path=tf_path,
                    hshift=hshift,
                    new_width=new_width,
                    new_height=new_height,
                    scaled_min_x=scaled_min_x,
                    scaled_max_x=scaled_max_x,
                    scaled_min_y=scaled_min_y,
                    scaled_max_y=scaled_max_y,
                )

                if stat_img.size == 0:
                    raise ValueError("Crop range produced an empty image.")

                _min, _max = np.min(stat_img), np.max(stat_img)
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
                tif_files=selected_tif_files,
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
                max_workers=worker_count,
            )

            self.save_worker.moveToThread(self.save_thread)

            self.save_progress_dialog = QtWidgets.QProgressDialog(
                "Saving corrected images...",
                "Cancel",
                0,
                len(selected_tif_files),
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
