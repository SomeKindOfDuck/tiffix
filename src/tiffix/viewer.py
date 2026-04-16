import numpy as np
import pyqtgraph as pg
from PyQt6 import QtGui, QtWidgets


class SingleImageWidget(pg.GraphicsLayoutWidget):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        self.ci.layout.setContentsMargins(4, 4, 4, 4)
        self.ci.layout.setSpacing(0)

        self.plot = self.addPlot(title=title)
        self.plot.setContentsMargins(0, 0, 0, 0)
        self.plot.invertY(True)
        self.plot.setAspectLocked(True)
        self.plot.hideAxis("left")
        self.plot.hideAxis("bottom")

        self.image_item = pg.ImageItem()
        self.plot.addItem(self.image_item)

    @property
    def viewbox(self) -> pg.ViewBox:
        return self.plot.getViewBox()

    def get_view_range(self) -> tuple[list[float], list[float]]:
        x_range, y_range = self.viewbox.viewRange()
        return x_range, y_range

    def set_view_range(
        self,
        x_range: tuple[float, float] | list[float],
        y_range: tuple[float, float] | list[float],
    ) -> None:
        self.viewbox.setRange(xRange=x_range, yRange=y_range, padding=0)

    def reset_view(self, img: np.ndarray | None = None) -> None:
        if img is None:
            img = self.image_item.image

        if img is None:
            return

        h, w = img.shape[:2]
        self.viewbox.setRange(xRange=(0, w), yRange=(0, h), padding=0)

    def set_image(self, img: np.ndarray, auto_range: bool = False) -> None:
        if auto_range:
            self.image_item.setImage(img)
            self.reset_view(img)
            return

        x_range, y_range = self.get_view_range()
        self.image_item.setImage(img)
        self.set_view_range(x_range, y_range)

    def set_levels(self, vmin: float, vmax: float) -> None:
        self.image_item.setLevels((vmin, vmax))

    def set_display_scale(self, sx: float = 1.0, sy: float = 1.0) -> None:
        transform = QtGui.QTransform()
        transform.scale(sx, sy)
        self.image_item.setTransform(transform)



class ImageCompareWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.left_widget = SingleImageWidget("Before")
        self.right_widget = SingleImageWidget("After")

        self.separator = QtWidgets.QFrame()
        self.separator.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        self.separator.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        self.separator.setLineWidth(1)

        layout.addWidget(self.left_widget, 1)
        layout.addWidget(self.separator)
        layout.addWidget(self.right_widget, 1)

        self.left_widget.plot.setXLink(self.right_widget.plot)
        self.left_widget.plot.setYLink(self.right_widget.plot)

    def _compute_levels(
        self,
        left: np.ndarray,
        right: np.ndarray,
        lower_percentile: float = 1,
        upper_percentile: float = 99,
    ) -> tuple[float, float]:
        combined = np.concatenate([left.ravel(), right.ravel()])
        vmin = float(np.percentile(combined, lower_percentile))
        vmax = float(np.percentile(combined, upper_percentile))
        return vmin, vmax

    def set_images(
        self,
        left: np.ndarray,
        right: np.ndarray,
        auto_range: bool = False,
        match_levels: bool = True,
    ) -> None:
        self.left_widget.set_image(left, auto_range=auto_range)
        self.right_widget.set_image(right, auto_range=auto_range)

        if match_levels:
            vmin, vmax = self._compute_levels(left, right)
            self.left_widget.set_levels(vmin, vmax)
            self.right_widget.set_levels(vmin, vmax)

    def update_left_image(
        self,
        left: np.ndarray,
        match_to_right: bool = False,
    ) -> None:
        x_range, y_range = self.left_widget.get_view_range()
        self.left_widget.image_item.setImage(left)
        self.left_widget.set_view_range(x_range, y_range)

        if match_to_right and self.right_widget.image_item.image is not None:
            right = self.right_widget.image_item.image
            vmin, vmax = self._compute_levels(left, right)
            self.left_widget.set_levels(vmin, vmax)
            self.right_widget.set_levels(vmin, vmax)

    def update_right_image(
        self,
        right: np.ndarray,
        match_to_left: bool = False,
    ) -> None:
        x_range, y_range = self.left_widget.get_view_range()
        self.right_widget.image_item.setImage(right)
        self.left_widget.set_view_range(x_range, y_range)

        if match_to_left and self.left_widget.image_item.image is not None:
            left = self.left_widget.image_item.image
            vmin, vmax = self._compute_levels(left, right)
            self.left_widget.set_levels(vmin, vmax)
            self.right_widget.set_levels(vmin, vmax)

    def reset_views(self) -> None:
        self.left_widget.reset_view()
        self.right_widget.reset_view()
