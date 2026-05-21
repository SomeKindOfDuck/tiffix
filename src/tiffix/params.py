from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets


class ClampSpinBox(QtWidgets.QSpinBox):
    HARD_MIN = -2_000_000_000
    HARD_MAX = 2_000_000_000

    def __init__(self, parent=None):
        super().__init__(parent)

        self._limit_min = self.HARD_MIN
        self._limit_max = self.HARD_MAX

        super().setRange(self.HARD_MIN, self.HARD_MAX)

        self.setKeyboardTracking(False)
        self.editingFinished.connect(self.clamp_to_limit)

    def setRange(self, vmin: int, vmax: int) -> None:
        """
        通常のQSpinBox.setRangeではなく、
        アプリ側の論理的なlimitとして扱う。
        """
        self._limit_min = int(vmin)
        self._limit_max = int(vmax)

        super().setRange(self.HARD_MIN, self.HARD_MAX)

        self.clamp_to_limit()

    def minimum(self) -> int:
        return self._limit_min

    def maximum(self) -> int:
        return self._limit_max

    def validate(self, text: str, pos: int):
        text = text.strip()

        if text in ("", "+", "-"):
            return (QtGui.QValidator.State.Intermediate, text, pos)

        try:
            int(text)
        except ValueError:
            return (QtGui.QValidator.State.Invalid, text, pos)

        return (QtGui.QValidator.State.Acceptable, text, pos)

    def clamp_to_limit(self) -> None:
        text = self.lineEdit().text().strip()

        try:
            value = int(text)
        except ValueError:
            value = self.value()

        if value < self._limit_min:
            value = self._limit_min
        elif value > self._limit_max:
            value = self._limit_max

        self.setValue(value)


class ParameterPanel(QtWidgets.QWidget):
    select_dir_requested = QtCore.pyqtSignal()
    onset_changed = QtCore.pyqtSignal()
    nframe_changed = QtCore.pyqtSignal()
    hshift_changed = QtCore.pyqtSignal()
    load_requested = QtCore.pyqtSignal()
    crop_size_changed = QtCore.pyqtSignal()
    resize_changed = QtCore.pyqtSignal()
    save_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QtWidgets.QVBoxLayout(self)

        #####################
        # Directory display #
        #####################
        dir_title_label = QtWidgets.QLabel("Current directory")
        main_layout.addWidget(dir_title_label)

        self.directory_label = QtWidgets.QLabel("No directory selected")
        self.directory_label.setContentsMargins(8, 4, 8, 4)
        self.directory_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.directory_label.setWordWrap(False)

        self.directory_scroll = QtWidgets.QScrollArea()
        self.directory_scroll.setWidgetResizable(True)
        self.directory_scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.directory_scroll.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.directory_scroll.setWidget(self.directory_label)
        self.directory_scroll.setFixedHeight(40)

        self.select_dir_button = QtWidgets.QPushButton("Select image directory")

        main_layout.addWidget(self.select_dir_button)
        main_layout.addWidget(self.directory_scroll)
        main_layout.addSpacing(20)

        ###################
        # Parameter panel #
        ###################
        title_label = QtWidgets.QLabel("Parameter settings")
        main_layout.addWidget(title_label)

        form_layout = QtWidgets.QFormLayout()

        self.onset_spin = ClampSpinBox()
        self.onset_spin.setRange(0, 1000000)
        self.onset_spin.setValue(0)
        self.onset_spin.setWrapping(False)

        self.nframe_spin = ClampSpinBox()
        self.nframe_spin.setRange(0, 1000000)
        self.nframe_spin.setValue(1)
        self.nframe_spin.setWrapping(False)

        self.auto_reload_checkbox = QtWidgets.QCheckBox("Auto reload")
        self.auto_reload_checkbox.setChecked(False)

        self.load_button = QtWidgets.QPushButton("Reload image")

        self.hshift_spin = ClampSpinBox()
        self.hshift_spin.setRange(-1000000, 1000000)
        self.hshift_spin.setValue(0)

        self.crop_x_min_spin = ClampSpinBox()
        self.crop_x_min_spin.setRange(0, 9999)
        self.crop_x_min_spin.setValue(0)

        self.crop_x_max_spin = ClampSpinBox()
        self.crop_x_max_spin.setRange(1, 10000)
        self.crop_x_max_spin.setValue(10000)

        self.crop_y_min_spin = ClampSpinBox()
        self.crop_y_min_spin.setRange(0, 9999)
        self.crop_y_min_spin.setValue(0)

        self.crop_y_max_spin = ClampSpinBox()
        self.crop_y_max_spin.setRange(1, 10000)
        self.crop_y_max_spin.setValue(0)

        crop_widget = QtWidgets.QWidget()
        crop_layout = QtWidgets.QGridLayout(crop_widget)
        crop_layout.setContentsMargins(0, 0, 0, 0)
        crop_layout.setHorizontalSpacing(6)
        crop_layout.setVerticalSpacing(2)

        crop_layout.addWidget(QtWidgets.QLabel("Min (um)"), 0, 0)
        crop_layout.addWidget(QtWidgets.QLabel("Max (um)"), 0, 1)
        crop_layout.addWidget(self.crop_x_min_spin, 1, 0)
        crop_layout.addWidget(self.crop_x_max_spin, 1, 1)
        crop_layout.addWidget(self.crop_y_min_spin, 2, 0)
        crop_layout.addWidget(self.crop_y_max_spin, 2, 1)

        self.resize_width_um_spin = ClampSpinBox()
        self.resize_width_um_spin.setRange(1, 10000)
        self.resize_width_um_spin.setValue(1000)
        self.resize_width_um_spin.setWrapping(False)

        self.resize_height_um_spin = ClampSpinBox()
        self.resize_height_um_spin.setRange(1, 10000)
        self.resize_height_um_spin.setValue(1000)
        self.resize_height_um_spin.setWrapping(False)

        form_layout.addRow("Start frame for averaging", self.onset_spin)
        form_layout.addRow("Frames for averaging", self.nframe_spin)
        form_layout.addRow(self.auto_reload_checkbox)
        form_layout.addRow(self.load_button)
        form_layout.addRow("Horizontal shift (px)", self.hshift_spin)

        form_layout.addRow(QtWidgets.QLabel(""))
        crop_label = QtWidgets.QLabel("Cropping image")
        form_layout.addRow(crop_label)
        form_layout.addRow(crop_widget)

        form_layout.addRow(QtWidgets.QLabel(""))
        resize_label = QtWidgets.QLabel("Resize image")
        form_layout.addRow(resize_label)
        form_layout.addRow("Width (µm)", self.resize_width_um_spin)
        form_layout.addRow("Height (µm)", self.resize_height_um_spin)

        main_layout.addLayout(form_layout)
        main_layout.addStretch()


        ################
        # Bottom Panel #
        ################
        self.save_start_spin = ClampSpinBox()
        self.save_start_spin.setRange(0, 1000000)
        self.save_start_spin.setValue(0)
        self.save_start_spin.setWrapping(False)

        self.save_end_spin = ClampSpinBox()
        self.save_end_spin.setRange(0, 1000000)
        self.save_end_spin.setValue(0)
        self.save_end_spin.setWrapping(False)

        self.save_button = QtWidgets.QPushButton("Save corrected images")

        save_range_widget = QtWidgets.QWidget()
        save_range_layout = QtWidgets.QFormLayout(save_range_widget)
        save_range_layout.setContentsMargins(0, 0, 0, 0)
        save_range_layout.addRow("Save start index", self.save_start_spin)
        save_range_layout.addRow("Save end index", self.save_end_spin)

        bottom_button_layout = QtWidgets.QVBoxLayout()
        bottom_button_layout.addWidget(save_range_widget)
        bottom_button_layout.addWidget(self.save_button)

        main_layout.addLayout(bottom_button_layout)

        ##################
        # connect envent #
        ##################
        self.onset_spin.valueChanged.connect(self.onset_changed)
        self.nframe_spin.valueChanged.connect(self.nframe_changed)
        self.auto_reload_checkbox.toggled.connect(self._on_auto_reload_toggled)
        self.load_button.clicked.connect(self.load_requested.emit)
        self.hshift_spin.valueChanged.connect(self.hshift_changed)
        self.crop_x_min_spin.valueChanged.connect(self.crop_size_changed)
        self.crop_x_max_spin.valueChanged.connect(self.crop_size_changed)
        self.crop_y_min_spin.valueChanged.connect(self.crop_size_changed)
        self.crop_y_max_spin.valueChanged.connect(self.crop_size_changed)
        self.resize_width_um_spin.valueChanged.connect(self.resize_changed)
        self.resize_height_um_spin.valueChanged.connect(self.resize_changed)

        self.select_dir_button.clicked.connect(self.select_dir_requested.emit)
        self.save_button.clicked.connect(self.save_requested.emit)

    def is_auto_reload_enabled(self) -> bool:
        return self.auto_reload_checkbox.isChecked()

    def _on_auto_reload_toggled(self, checked: bool) -> None:
        self.load_button.setEnabled(not checked)
        if checked:
            self.load_button.setStyleSheet(
                "QPushButton { color: gray; background-color: #444; }"
            )
        else:
            self.load_button.setStyleSheet("")

    def get_parameters(self) -> dict[str, Any]:
        return {
            "onset": self.onset_spin.value(),
            "nframe": self.nframe_spin.value(),
            "hshift": self.hshift_spin.value(),
            "crop_x_um": (self.crop_x_min_spin.value(), self.crop_x_max_spin.value()),
            "crop_y_um": (self.crop_y_min_spin.value(), self.crop_y_max_spin.value()),
            "resize_width_um": self.resize_width_um_spin.value(),
            "resize_height_um": self.resize_height_um_spin.value(),
        }

    def set_limit(self, param: str, vmin: int, vmax: int):
        if param == "onset":
            spinbox = self.onset_spin
        elif param == "nframe":
            spinbox = self.nframe_spin
        elif param == "hshift":
            spinbox = self.hshift_spin
        elif param == "crop_x_min":
            spinbox = self.crop_x_min_spin
        elif param == "crop_x_max":
            spinbox = self.crop_x_max_spin
        elif param == "crop_y_min":
            spinbox = self.crop_y_min_spin
        elif param == "crop_y_max":
            spinbox = self.crop_y_max_spin
        elif param == "save_start":
            spinbox = self.save_start_spin
        elif param == "save_end":
            spinbox = self.save_end_spin
        else:
            raise ValueError(f"{param}というパラメータは存在しません")

        spinbox.setRange(vmin, vmax)
        spinbox.clamp_to_limit()

    def set_directory(self, directory: str) -> None:
        self.directory_label.setText(directory)

    def set_resize_values(self, width: int, height: int) -> None:
        old_width_block = self.resize_width_um_spin.blockSignals(True)
        old_height_block = self.resize_height_um_spin.blockSignals(True)

        self.resize_width_um_spin.setValue(width)
        self.resize_height_um_spin.setValue(height)

        self.resize_width_um_spin.blockSignals(old_width_block)
        self.resize_height_um_spin.blockSignals(old_height_block)
