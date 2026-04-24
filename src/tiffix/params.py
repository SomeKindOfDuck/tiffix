from typing import Any

from PyQt6 import QtCore, QtWidgets


class ParameterPanel(QtWidgets.QWidget):
    select_dir_requested = QtCore.pyqtSignal()
    onset_changed = QtCore.pyqtSignal()
    nframe_changed = QtCore.pyqtSignal()
    hshift_changed = QtCore.pyqtSignal()
    load_requested = QtCore.pyqtSignal()
    crop_size_changed = QtCore.pyqtSignal()
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

        self.onset_spin = QtWidgets.QSpinBox()
        self.onset_spin.setRange(0, 1000000)
        self.onset_spin.setValue(0)
        self.onset_spin.setWrapping(False)

        self.nframe_spin = QtWidgets.QSpinBox()
        self.nframe_spin.setRange(0, 1000000)
        self.nframe_spin.setValue(1)
        self.nframe_spin.setWrapping(False)

        self.auto_reload_checkbox = QtWidgets.QCheckBox("Auto reload")
        self.auto_reload_checkbox.setChecked(False)

        self.load_button = QtWidgets.QPushButton("Reload image")

        self.hshift_spin = QtWidgets.QSpinBox()
        self.hshift_spin.setRange(-1000000, 1000000)
        self.hshift_spin.setValue(0)

        self.crop_x_min_spin = QtWidgets.QSpinBox()
        self.crop_x_min_spin.setRange(0, 9999)
        self.crop_x_min_spin.setValue(0)

        self.crop_x_max_spin = QtWidgets.QSpinBox()
        self.crop_x_max_spin.setRange(1, 10000)
        self.crop_x_max_spin.setValue(10000)

        self.crop_y_min_spin = QtWidgets.QSpinBox()
        self.crop_y_min_spin.setRange(0, 9999)
        self.crop_y_min_spin.setValue(0)

        self.crop_y_max_spin = QtWidgets.QSpinBox()
        self.crop_y_max_spin.setRange(1, 10000)
        self.crop_y_max_spin.setValue(0)

        crop_widget = QtWidgets.QWidget()
        crop_layout = QtWidgets.QGridLayout(crop_widget)
        crop_layout.setContentsMargins(0, 0, 0, 0)
        crop_layout.setHorizontalSpacing(6)
        crop_layout.setVerticalSpacing(2)

        crop_layout.addWidget(QtWidgets.QLabel("Min"), 0, 0)
        crop_layout.addWidget(QtWidgets.QLabel("Max"), 0, 1)
        crop_layout.addWidget(self.crop_x_min_spin, 1, 0)
        crop_layout.addWidget(self.crop_x_max_spin, 1, 1)
        crop_layout.addWidget(self.crop_y_min_spin, 2, 0)
        crop_layout.addWidget(self.crop_y_max_spin, 2, 1)

        form_layout.addRow("Start frame for averaging", self.onset_spin)
        form_layout.addRow("Frames for averaging", self.nframe_spin)
        form_layout.addRow(self.auto_reload_checkbox)
        form_layout.addRow(self.load_button)
        form_layout.addRow("Horizontal shift (px)", self.hshift_spin)

        form_layout.addRow(QtWidgets.QLabel(""))
        crop_label = QtWidgets.QLabel("Cropping image")
        form_layout.addRow(crop_label)
        form_layout.addRow(crop_widget)

        main_layout.addLayout(form_layout)
        main_layout.addStretch()


        ################
        # Bottom Panel #
        ################
        self.save_button = QtWidgets.QPushButton("Save corrected images")

        bottom_button_layout = QtWidgets.QVBoxLayout()
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
            "crop_x": (self.crop_x_min_spin.value(), self.crop_x_max_spin.value()),
            "crop_y": (self.crop_y_min_spin.value(), self.crop_y_max_spin.value()),
        }

    def set_limit(self, param: str, vmin: int, vmax: int):
        if param == "onset":
            self.onset_spin.setRange(vmin, vmax)
        elif param == "nframe":
            self.nframe_spin.setRange(vmin, vmax)
        elif param == "hshift":
            self.hshift_spin.setRange(vmin, vmax)
        elif param == "crop_x_min":
            self.crop_x_min_spin.setRange(vmin, vmax)
        elif param == "crop_x_max":
            self.crop_x_max_spin.setRange(vmin, vmax)
        elif param == "crop_y_min":
            self.crop_y_min_spin.setRange(vmin, vmax)
        elif param == "crop_y_max":
            self.crop_y_max_spin.setRange(vmin, vmax)
        else:
            raise ValueError(f"{param}というパラメータは存在しません")

    def set_directory(self, directory: str) -> None:
        self.directory_label.setText(directory)
