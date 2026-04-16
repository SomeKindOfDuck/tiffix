from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
import tifffile
from PyQt6 import QtCore

from tiffix import align_img, reshape_img, sine_correction


def process_and_save_one(
    tf_path: str,
    output_dir: str,
    hshift: int,
    new_width: int,
    new_height: int,
    scaled_min_x: int,
    scaled_max_x: int,
    scaled_min_y: int,
    scaled_max_y: int,
    scale_min: float,
    scale_max: float,
) -> str:
    tf = Path(tf_path)
    output_path = Path(output_dir) / tf.name

    img = tifffile.imread(tf)
    reshaped_img = reshape_img(img)
    aligned_img = align_img(reshaped_img, hshift)
    corrected_img = sine_correction(aligned_img)
    corrected_img = cv2.resize(corrected_img, (new_width, new_height))
    corrected_img = corrected_img[scaled_min_y:scaled_max_y, scaled_min_x:scaled_max_x]

    corrected_img = np.clip(corrected_img, scale_min, scale_max)
    corrected_img = (corrected_img - scale_min) / (scale_max - scale_min)
    corrected_img = corrected_img * 65535.0
    corrected_img = corrected_img.astype(np.uint16)

    tifffile.imwrite(output_path, corrected_img)
    return str(output_path)

class SaveImagesWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(int, int)  # done, total

    def __init__(
        self,
        tif_files: list[Path],
        output_dir: Path,
        hshift: int,
        new_width: int,
        new_height: int,
        scaled_min_x: int,
        scaled_max_x: int,
        scaled_min_y: int,
        scaled_max_y: int,
        scale_min: float,
        scale_max: float,
        max_workers: int | None = None,
    ):
        super().__init__()
        self.tif_files = tif_files
        self.output_dir = output_dir
        self.hshift = hshift
        self.new_width = new_width
        self.new_height = new_height
        self.scaled_min_x = scaled_min_x
        self.scaled_max_x = scaled_max_x
        self.scaled_min_y = scaled_min_y
        self.scaled_max_y = scaled_max_y
        self.scale_min = scale_min
        self.scale_max = scale_max
        self.max_workers = max_workers

    @QtCore.pyqtSlot()
    def run(self) -> None:
        try:
            total = len(self.tif_files)
            done = 0

            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [
                    executor.submit(
                        process_and_save_one,
                        str(tf),
                        str(self.output_dir),
                        self.hshift,
                        self.new_width,
                        self.new_height,
                        self.scaled_min_x,
                        self.scaled_max_x,
                        self.scaled_min_y,
                        self.scaled_max_y,
                        self.scale_min,
                        self.scale_max,
                    )
                    for tf in self.tif_files
                ]

                for future in as_completed(futures):
                    future.result()
                    done += 1
                    self.progress.emit(done, total)

            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))
