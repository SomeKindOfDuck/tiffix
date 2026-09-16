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
    fov_changed = QtCore.pyqtSignal()
    output_size_changed = QtCore.pyqtSignal()
    save_requested = QtCore.pyqtSignal()
    save_settings_requested = QtCore.pyqtSignal()
    load_settings_requested = QtCore.pyqtSignal()

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
        main_layout.addSpacing(10)

        #####################
        # Settings save/load #
        #####################
        self.save_settings_button = QtWidgets.QPushButton("Save settings")
        self.load_settings_button = QtWidgets.QPushButton("Load settings")

        settings_button_layout = QtWidgets.QHBoxLayout()
        settings_button_layout.addWidget(self.save_settings_button)
        settings_button_layout.addWidget(self.load_settings_button)

        main_layout.addLayout(settings_button_layout)
        main_layout.addSpacing(10)

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

        self.fov_width_um_spin = ClampSpinBox()
        self.fov_width_um_spin.setRange(1, 10000)
        self.fov_width_um_spin.setValue(1000)
        self.fov_width_um_spin.setWrapping(False)

        self.fov_height_um_spin = ClampSpinBox()
        self.fov_height_um_spin.setRange(1, 10000)
        self.fov_height_um_spin.setValue(1000)
        self.fov_height_um_spin.setWrapping(False)

        self.output_width_px_spin = ClampSpinBox()
        self.output_width_px_spin.setRange(1, 1000000)
        self.output_width_px_spin.setValue(1000)
        self.output_width_px_spin.setWrapping(False)

        self.output_height_px_spin = ClampSpinBox()
        self.output_height_px_spin.setRange(1, 1000000)
        self.output_height_px_spin.setValue(1000)
        self.output_height_px_spin.setWrapping(False)

        self._updating_output_size = False
        self._output_anchor_axis = "width"

        form_layout.addRow(QtWidgets.QLabel(""))
        fov_label = QtWidgets.QLabel("Field of view")
        form_layout.addRow(fov_label)
        form_layout.addRow("FOV width (µm)", self.fov_width_um_spin)
        form_layout.addRow("FOV height (µm)", self.fov_height_um_spin)

        form_layout.addRow(QtWidgets.QLabel(""))
        output_label = QtWidgets.QLabel("Output image size")
        form_layout.addRow(output_label)
        form_layout.addRow("Output width (px)", self.output_width_px_spin)
        form_layout.addRow("Output height (px)", self.output_height_px_spin)

        crop_widget = QtWidgets.QWidget()
        crop_layout = QtWidgets.QGridLayout(crop_widget)
        crop_layout.setContentsMargins(0, 0, 0, 0)
        crop_layout.setHorizontalSpacing(6)
        crop_layout.setVerticalSpacing(2)

        crop_layout.addWidget(QtWidgets.QLabel("Min (px)"), 0, 0)
        crop_layout.addWidget(QtWidgets.QLabel("Max (px)"), 0, 1)
        crop_layout.addWidget(self.crop_x_min_spin, 1, 0)
        crop_layout.addWidget(self.crop_x_max_spin, 1, 1)
        crop_layout.addWidget(self.crop_y_min_spin, 2, 0)
        crop_layout.addWidget(self.crop_y_max_spin, 2, 1)

        form_layout.addRow(QtWidgets.QLabel(""))
        crop_label = QtWidgets.QLabel("Cropping image")
        form_layout.addRow(crop_label)
        form_layout.addRow(crop_widget)

        form_layout.addRow(QtWidgets.QLabel(""))
        form_layout.addRow("Start frame for averaging", self.onset_spin)
        form_layout.addRow("Frames for averaging", self.nframe_spin)
        form_layout.addRow(self.auto_reload_checkbox)
        form_layout.addRow(self.load_button)
        form_layout.addRow("Horizontal shift (px)", self.hshift_spin)

        main_layout.addLayout(form_layout)
        main_layout.addStretch()


        ################
        # Bottom Panel #
        ################
        self.save_button = QtWidgets.QPushButton("Save corrected images")

        self._hshift_rows: list[dict[str, Any]] = []
        self._hshift_row_index_max = 1000000
        self._hshift_row_value_min = -1000000
        self._hshift_row_value_max = 1000000

        save_ranges_title = QtWidgets.QLabel("Save frame ranges")

        save_ranges_widget = QtWidgets.QWidget()
        self.save_ranges_layout = QtWidgets.QGridLayout(save_ranges_widget)
        self.save_ranges_layout.setContentsMargins(0, 0, 0, 0)
        self.save_ranges_layout.setHorizontalSpacing(6)
        self.save_ranges_layout.setVerticalSpacing(2)

        self.save_ranges_layout.addWidget(QtWidgets.QLabel("Start index"), 0, 0)
        self.save_ranges_layout.addWidget(QtWidgets.QLabel("End index"), 0, 1)
        self.save_ranges_layout.addWidget(QtWidgets.QLabel("Horizontal shift"), 0, 2)

        self.add_hshift_row_button = QtWidgets.QPushButton("+")
        self.add_hshift_row_button.setFixedWidth(28)
        self.add_hshift_row_button.setToolTip("Add another save frame range")
        self.add_hshift_row_button.clicked.connect(self._add_hshift_row)

        self._add_hshift_row()

        bottom_button_layout = QtWidgets.QVBoxLayout()
        bottom_button_layout.addWidget(save_ranges_title)
        bottom_button_layout.addWidget(save_ranges_widget)
        bottom_button_layout.addWidget(
            self.add_hshift_row_button, alignment=QtCore.Qt.AlignmentFlag.AlignLeft
        )
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
        self.fov_width_um_spin.valueChanged.connect(self._on_fov_changed)
        self.fov_height_um_spin.valueChanged.connect(self._on_fov_changed)
        self.output_width_px_spin.valueChanged.connect(self._on_output_width_px_changed)
        self.output_height_px_spin.valueChanged.connect(self._on_output_height_px_changed)

        self.select_dir_button.clicked.connect(self.select_dir_requested.emit)
        self.save_button.clicked.connect(self.save_requested.emit)
        self.save_settings_button.clicked.connect(self.save_settings_requested.emit)
        self.load_settings_button.clicked.connect(self.load_settings_requested.emit)

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
            "crop_x_px": (self.crop_x_min_spin.value(), self.crop_x_max_spin.value()),
            "crop_y_px": (self.crop_y_min_spin.value(), self.crop_y_max_spin.value()),
            "fov_width_um": self.fov_width_um_spin.value(),
            "fov_height_um": self.fov_height_um_spin.value(),
            "output_width_px": self.output_width_px_spin.value(),
            "output_height_px": self.output_height_px_spin.value(),
            "save_hshift_ranges": [
                {
                    "start": row["start_spin"].value(),
                    "end": row["end_spin"].value(),
                    "value": row["hshift_spin"].value(),
                }
                for row in self._hshift_rows
            ],
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
        else:
            raise ValueError(f"{param}というパラメータは存在しません")

        spinbox.setRange(vmin, vmax)
        spinbox.clamp_to_limit()

    def _make_hshift_row_index_spin(self) -> ClampSpinBox:
        spin = ClampSpinBox()
        spin.setRange(0, self._hshift_row_index_max)
        spin.setValue(0)
        spin.setWrapping(False)
        return spin

    def _make_hshift_row_value_spin(self) -> ClampSpinBox:
        spin = ClampSpinBox()
        spin.setRange(self._hshift_row_value_min, self._hshift_row_value_max)
        spin.setValue(0)
        return spin

    def _hshift_row_coverage(self) -> tuple[int, int] | None:
        """既存の全行の start/end から、カバーされている範囲の(最小, 最大)を返す。行がなければNone。"""
        if not self._hshift_rows:
            return None

        starts = [row["start_spin"].value() for row in self._hshift_rows]
        ends = [row["end_spin"].value() for row in self._hshift_rows]
        return min(starts), max(ends)

    def _next_hshift_row_range(self) -> tuple[int, int]:
        coverage = self._hshift_row_coverage()

        if coverage is None:
            return 0, self._hshift_row_index_max

        min_start, max_end = coverage

        if max_end < self._hshift_row_index_max:
            return max_end + 1, self._hshift_row_index_max

        if min_start > 0:
            return 0, min_start - 1

        return 0, self._hshift_row_index_max

    def _is_hshift_row_fully_covered(self) -> bool:
        coverage = self._hshift_row_coverage()
        if coverage is None:
            return False

        min_start, max_end = coverage
        return min_start <= 0 and max_end >= self._hshift_row_index_max

    def _update_add_hshift_row_button_state(self) -> None:
        self.add_hshift_row_button.setEnabled(not self._is_hshift_row_fully_covered())

    def _add_hshift_row(self) -> None:
        start_value, end_value = self._next_hshift_row_range()

        start_spin = self._make_hshift_row_index_spin()
        end_spin = self._make_hshift_row_index_spin()
        start_spin.setValue(start_value)
        end_spin.setValue(end_value)
        hshift_spin = self._make_hshift_row_value_spin()

        remove_button = QtWidgets.QPushButton("×")
        remove_button.setFixedWidth(24)
        remove_button.setToolTip("Remove this save frame range")

        row: dict[str, Any] = {
            "start_spin": start_spin,
            "end_spin": end_spin,
            "hshift_spin": hshift_spin,
            "remove_button": remove_button,
        }
        remove_button.clicked.connect(lambda: self._remove_hshift_row(row))
        start_spin.valueChanged.connect(self._update_add_hshift_row_button_state)
        end_spin.valueChanged.connect(self._update_add_hshift_row_button_state)

        self._hshift_rows.append(row)
        self._rebuild_hshift_rows_layout()
        self._update_add_hshift_row_button_state()

    def _remove_hshift_row(self, row: dict[str, Any]) -> None:
        if len(self._hshift_rows) <= 1:
            return

        self._hshift_rows.remove(row)

        for widget in row.values():
            widget.setParent(None)
            widget.deleteLater()

        self._rebuild_hshift_rows_layout()
        self._update_add_hshift_row_button_state()

    def _rebuild_hshift_rows_layout(self) -> None:
        for i in reversed(range(self.save_ranges_layout.count())):
            widget = self.save_ranges_layout.itemAt(i).widget()
            if widget is None:
                continue

            row_index, _col, _row_span, _col_span = self.save_ranges_layout.getItemPosition(i)
            if row_index == 0:
                continue

            self.save_ranges_layout.removeWidget(widget)

        can_remove = len(self._hshift_rows) > 1
        for i, row in enumerate(self._hshift_rows):
            grid_row = i + 1
            self.save_ranges_layout.addWidget(row["start_spin"], grid_row, 0)
            self.save_ranges_layout.addWidget(row["end_spin"], grid_row, 1)
            self.save_ranges_layout.addWidget(row["hshift_spin"], grid_row, 2)
            row["remove_button"].setEnabled(can_remove)
            self.save_ranges_layout.addWidget(row["remove_button"], grid_row, 3)

    def set_hshift_row_index_limit(self, max_index: int) -> None:
        self._hshift_row_index_max = max(0, int(max_index))
        for row in self._hshift_rows:
            row["start_spin"].setRange(0, self._hshift_row_index_max)
            row["end_spin"].setRange(0, self._hshift_row_index_max)
            row["start_spin"].clamp_to_limit()
            row["end_spin"].clamp_to_limit()

        self._update_add_hshift_row_button_state()

    def set_hshift_row_value_limit(self, vmin: int, vmax: int) -> None:
        self._hshift_row_value_min = int(vmin)
        self._hshift_row_value_max = int(vmax)
        for row in self._hshift_rows:
            row["hshift_spin"].setRange(self._hshift_row_value_min, self._hshift_row_value_max)
            row["hshift_spin"].clamp_to_limit()

    def reset_hshift_rows(self, default_end: int) -> None:
        for row in list(self._hshift_rows):
            for widget in row.values():
                widget.setParent(None)
                widget.deleteLater()

        self._hshift_rows = []
        self._add_hshift_row()
        self._hshift_rows[0]["start_spin"].setValue(0)
        self._hshift_rows[0]["end_spin"].setValue(default_end)

    def _apply_hshift_ranges(self, ranges: Any) -> None:
        if isinstance(ranges, bool):
            raise ValueError("hshift の形式が不正です。")

        if isinstance(ranges, (int, float)):
            ranges = [{"start": 0, "end": self._hshift_row_index_max, "value": int(ranges)}]

        for row in list(self._hshift_rows):
            for widget in row.values():
                widget.setParent(None)
                widget.deleteLater()

        self._hshift_rows = []

        if not ranges:
            self._add_hshift_row()
            return

        for entry in ranges:
            self._add_hshift_row()
            row = self._hshift_rows[-1]
            row["start_spin"].setValue(int(entry["start"]))
            row["end_spin"].setValue(int(entry["end"]))
            row["hshift_spin"].setValue(int(entry["value"]))

    def get_settings_for_save(self) -> dict[str, Any]:
        """
        入力中のパラメータをYAML保存用の形式で返す。
        トップレベルのキーは tiffix-cli の設定ファイルと共通（input_dir を除く）で、
        GUI専用のパラメータ（onset/nframe/表示用hshift/FOVなど、画像保存処理には
        使われないもの）は "gui" キー以下にまとめる。
        """
        params = self.get_parameters()
        crop_x_min, crop_x_max = params["crop_x_px"]
        crop_y_min, crop_y_max = params["crop_y_px"]

        return {
            "output_width": params["output_width_px"],
            "output_height": params["output_height_px"],
            "crop_x_min": crop_x_min,
            "crop_x_max": crop_x_max,
            "crop_y_min": crop_y_min,
            "crop_y_max": crop_y_max,
            "hshift": params["save_hshift_ranges"],
            "gui": {
                "onset": params["onset"],
                "nframe": params["nframe"],
                "hshift": params["hshift"],
                "fov_width_um": params["fov_width_um"],
                "fov_height_um": params["fov_height_um"],
            },
        }

    def apply_settings(self, settings: dict[str, Any]) -> None:
        """get_settings_for_save() で保存した設定（またはCLIと互換なYAML）を反映する。"""
        output_width = settings.get("output_width")
        output_height = settings.get("output_height")
        if output_width is not None and output_height is not None:
            self.set_output_size_values(int(output_width), int(output_height))

        gui_settings = settings.get("gui") or {}

        fov_width_um = gui_settings.get("fov_width_um")
        fov_height_um = gui_settings.get("fov_height_um")
        if fov_width_um is not None and fov_height_um is not None:
            self.set_fov_values(int(fov_width_um), int(fov_height_um))

        if settings.get("crop_x_min") is not None:
            self.crop_x_min_spin.setValue(int(settings["crop_x_min"]))
            self.crop_x_min_spin.clamp_to_limit()
        if settings.get("crop_x_max") is not None:
            self.crop_x_max_spin.setValue(int(settings["crop_x_max"]))
            self.crop_x_max_spin.clamp_to_limit()
        if settings.get("crop_y_min") is not None:
            self.crop_y_min_spin.setValue(int(settings["crop_y_min"]))
            self.crop_y_min_spin.clamp_to_limit()
        if settings.get("crop_y_max") is not None:
            self.crop_y_max_spin.setValue(int(settings["crop_y_max"]))
            self.crop_y_max_spin.clamp_to_limit()

        if settings.get("hshift") is not None:
            self._apply_hshift_ranges(settings["hshift"])

        if gui_settings.get("onset") is not None:
            self.onset_spin.setValue(int(gui_settings["onset"]))
            self.onset_spin.clamp_to_limit()
        if gui_settings.get("nframe") is not None:
            self.nframe_spin.setValue(int(gui_settings["nframe"]))
            self.nframe_spin.clamp_to_limit()
        if gui_settings.get("hshift") is not None:
            self.hshift_spin.setValue(int(gui_settings["hshift"]))
            self.hshift_spin.clamp_to_limit()

    def set_directory(self, directory: str) -> None:
        self.directory_label.setText(directory)

    def _output_height_from_width(self, width_px: int) -> int:
        fov_width = max(1, self.fov_width_um_spin.value())
        fov_height = max(1, self.fov_height_um_spin.value())
        return max(1, int(round(width_px * fov_height / fov_width)))

    def _output_width_from_height(self, height_px: int) -> int:
        fov_width = max(1, self.fov_width_um_spin.value())
        fov_height = max(1, self.fov_height_um_spin.value())
        return max(1, int(round(height_px * fov_width / fov_height)))

    def _set_output_size_blocked(self, width: int, height: int) -> None:
        old_width_block = self.output_width_px_spin.blockSignals(True)
        old_height_block = self.output_height_px_spin.blockSignals(True)

        self.output_width_px_spin.setValue(max(1, int(width)))
        self.output_height_px_spin.setValue(max(1, int(height)))

        self.output_width_px_spin.blockSignals(old_width_block)
        self.output_height_px_spin.blockSignals(old_height_block)

    def _sync_output_size_to_fov(self) -> None:
        if self._output_anchor_axis == "height":
            height = self.output_height_px_spin.value()
            width = self._output_width_from_height(height)
        else:
            width = self.output_width_px_spin.value()
            height = self._output_height_from_width(width)

        self._set_output_size_blocked(width, height)

    def _on_fov_changed(self, _value: int) -> None:
        self._sync_output_size_to_fov()
        self.fov_changed.emit()

    def _on_output_width_px_changed(self, width: int) -> None:
        if self._updating_output_size:
            return

        self._output_anchor_axis = "width"
        self._updating_output_size = True
        try:
            self.output_height_px_spin.setValue(self._output_height_from_width(width))
        finally:
            self._updating_output_size = False

        self.output_size_changed.emit()

    def _on_output_height_px_changed(self, height: int) -> None:
        if self._updating_output_size:
            return

        self._output_anchor_axis = "height"
        self._updating_output_size = True
        try:
            self.output_width_px_spin.setValue(self._output_width_from_height(height))
        finally:
            self._updating_output_size = False

        self.output_size_changed.emit()

    def set_fov_values(self, width: int, height: int) -> None:
        old_width_block = self.fov_width_um_spin.blockSignals(True)
        old_height_block = self.fov_height_um_spin.blockSignals(True)

        self.fov_width_um_spin.setValue(width)
        self.fov_height_um_spin.setValue(height)

        self.fov_width_um_spin.blockSignals(old_width_block)
        self.fov_height_um_spin.blockSignals(old_height_block)

    def set_output_size_values(self, width: int, height: int) -> None:
        self._set_output_size_blocked(width, height)
