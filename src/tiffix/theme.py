import pyqtgraph as pg
from PyQt6 import QtGui, QtWidgets

ICEBERG_DARK = {
    "bg":         "#1e2132",
    "fg":         "#c6c8d1",
    "fg_dim":     "#9fa2b0",
    "grid":       "#2e3244",
    "axis":       "#c6c8d1",
    "threshold":  "#e2a478",
    "event":      "#84a0c6",
    "highlight":  "#ffffff",

    "red":        "#e27878",
    "green":      "#b4be82",
    "yellow":     "#e2a478",
    "blue":       "#84a0c6",
    "purple":     "#a093c7",
    "cyan":       "#89b8c2",

    "dim_red":    "#e98989",
    "dim_green":  "#c0ca8e",
    "dim_yellow": "#e9b189",
    "dim_blue":   "#91acd1",
    "dim_purple": "#ada0d3",
    "dim_cyan":   "#95c4ce",
}

ICEBERG_DARK_SERIES = [
    ICEBERG_DARK["blue"],
    ICEBERG_DARK["red"],
    ICEBERG_DARK["green"],
    ICEBERG_DARK["purple"],
    ICEBERG_DARK["cyan"],
    ICEBERG_DARK["yellow"],
    ICEBERG_DARK["dim_blue"],
    ICEBERG_DARK["dim_red"],
    ICEBERG_DARK["dim_green"],
    ICEBERG_DARK["dim_purple"],
    ICEBERG_DARK["dim_cyan"],
    ICEBERG_DARK["dim_yellow"],
]


def apply_colorscheme(app: QtWidgets.QApplication, colorscheme: dict):
    pg.setConfigOption("background", colorscheme["bg"])
    pg.setConfigOption("foreground", colorscheme["fg"])

    pal = QtGui.QPalette()

    bg      = QtGui.QColor(colorscheme["bg"])
    bg_soft = QtGui.QColor(colorscheme.get("bg_soft", colorscheme["bg"]))
    fg      = QtGui.QColor(colorscheme["fg"])
    fg_dim  = QtGui.QColor(colorscheme.get("fg_dim", colorscheme["fg"]))
    grid    = QtGui.QColor(colorscheme.get("grid", "#2e3244"))

    pal.setColor(QtGui.QPalette.ColorRole.Window, bg)
    pal.setColor(QtGui.QPalette.ColorRole.WindowText, fg)
    pal.setColor(QtGui.QPalette.ColorRole.Base, bg_soft)
    pal.setColor(QtGui.QPalette.ColorRole.AlternateBase, bg)
    pal.setColor(QtGui.QPalette.ColorRole.Text, fg)
    pal.setColor(QtGui.QPalette.ColorRole.Button, bg_soft)
    pal.setColor(QtGui.QPalette.ColorRole.ButtonText, fg)
    pal.setColor(QtGui.QPalette.ColorRole.ToolTipBase, bg_soft)
    pal.setColor(QtGui.QPalette.ColorRole.ToolTipText, fg)

    pal.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(colorscheme["blue"]))
    pal.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(colorscheme["bg"]))

    pal.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText, fg_dim)
    pal.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, fg_dim)
    pal.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText, fg_dim)

    app.setPalette(pal)

    app.setStyleSheet(f"""
        QWidget {{
            background-color: {colorscheme["bg"]};
            color: {colorscheme["fg"]};
        }}

        QGroupBox {{
            border: 1px solid {colorscheme.get("grid", "#2e3244")};
            margin-top: 8px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: {colorscheme.get("fg_dim", colorscheme["fg"])};
        }}

        QCheckBox::indicator {{
            width: 12px;
            height: 12px;
            border: 1px solid {colorscheme.get("fg_dim", colorscheme["fg"])};
            border-radius: 2px;
            background: transparent;
        }}

        QCheckBox::indicator:checked {{
            background: {colorscheme.get("fg_dim", colorscheme["fg"])};
            border: 1px solid {colorscheme.get("fg_dim", colorscheme["fg"])};
        }}

        QCheckBox::indicator:disabled {{
            border: 1px solid {colorscheme.get("fg_muted", colorscheme.get("fg_dim", colorscheme["fg"]))};
            background: transparent;
        }}

        QAbstractSpinBox:disabled {{
            color: {colorscheme.get("fg_dim", "#9fa2b0")};
        }}

        QAbstractSpinBox::up-button:disabled,
        QAbstractSpinBox::down-button:disabled {{
            background-color: {colorscheme.get("grid", "#2e3244")};
        }}

        QSlider::groove:horizontal {{
            height: 6px;
            background: {colorscheme.get("grid", "#2e3244")};
            border-radius: 3px;
        }}

        QSlider::handle:horizontal {{
            width: 14px;
            margin: -6px 0;
            border-radius: 7px;
            background: {colorscheme["blue"]};
        }}

        QSlider::handle:horizontal:hover {{
            background: {colorscheme["cyan"]};
        }}
    """)
