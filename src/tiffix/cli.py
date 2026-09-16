"""
GUI (tiffix.gui) を起動せずに、コマンドライン引数またはYAML設定ファイルから
パラメータを読み込んで画像補正・保存だけを行うためのエントリポイント。

GUI上には表示専用のパラメータ（FOV幅/高さ [um] など）が存在するが、
それらは画像保存処理そのものには使われないため、ここでは扱わない。
実際に画像保存時に使用されるパラメータのみを設定対象とする。

hshift はGUIと異なり、フレーム区間ごとに異なる値を指定できる（YAML設定ファイルのみ）。
保存対象の範囲は hshift の区間指定から自動的に決まる
（区間の最小開始インデックス〜最大終了インデックス）。
"""

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
import yaml

from tiffix import align_img, reshape_img, sine_correction
from tiffix.hshift import resolve_hshift_map
from tiffix.save import preprocess_corrected_image, process_and_save_one

# GUI (MainWindow.save_image) が scale_min/scale_max の自動算出に使うサンプル枚数と同じ値。
STAT_SAMPLE_LIMIT = 100

# YAML設定ファイル / コマンドライン引数の両方で受け付けるキー。
# GUIの ParameterPanel.get_parameters() が返す値のうち、
# 実際に画像保存 (MainWindow.save_image) で使用されるものだけを対象にしている。
# save_start/save_end はGUIには存在するが、CLIでは hshift の区間指定から自動的に決まるため対象外。
CONFIG_KEYS = (
    "input_dir",
    "output_dir",
    "hshift",
    "output_width",
    "output_height",
    "crop_x_min",
    "crop_x_max",
    "crop_y_min",
    "crop_y_max",
    "workers",
)

# GUI がYAMLに保存する際、GUI専用パラメータ（onset/nframe/表示用hshift/FOVなど、
# 画像保存処理には使われないもの）をまとめて格納する予約キー。CLIでは無視する。
IGNORED_CONFIG_KEYS = ("gui",)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tiffix-cli",
        description=(
            "GUIを開かずにTIFF画像の補正・保存を行うCLI。"
            "--config で指定したYAMLファイルと個別のオプションを併用でき、"
            "個別のオプションが指定された場合はYAMLの値より優先される。"
        ),
    )

    parser.add_argument(
        "-c", "--config", type=Path, default=None,
        help="パラメータを記述したYAML設定ファイルのパス",
    )

    parser.add_argument(
        "-i", "--input-dir", dest="input_dir", type=str, default=None,
        help="*.tif / *.tiff が入っている入力ディレクトリ（必須）",
    )
    parser.add_argument(
        "-o", "--output-dir", dest="output_dir", type=str, default=None,
        help="出力先ディレクトリ。相対パスは input_dir 基準（デフォルト: corrected）",
    )
    parser.add_argument(
        "--hshift", type=int, default=None,
        help=(
            "水平方向のシフト量 [px]。全フレームに同一の値を適用する（デフォルト: 0）。"
            "フレーム区間ごとに異なる値を指定したい場合はYAML設定ファイルの hshift を"
            "リストで指定すること（このオプションを指定した場合はそちらを上書きする）。"
        ),
    )
    parser.add_argument(
        "--output-width", dest="output_width", type=int, default=None,
        help="出力画像の幅 [px]（デフォルト: 補正後画像の幅）",
    )
    parser.add_argument(
        "--output-height", dest="output_height", type=int, default=None,
        help="出力画像の高さ [px]（デフォルト: 補正後画像の高さ）",
    )
    parser.add_argument(
        "--crop-x-min", dest="crop_x_min", type=int, default=None,
        help="クロップ範囲 x の最小値 [px]（デフォルト: 0）",
    )
    parser.add_argument(
        "--crop-x-max", dest="crop_x_max", type=int, default=None,
        help="クロップ範囲 x の最大値 [px]（デフォルト: output_width）",
    )
    parser.add_argument(
        "--crop-y-min", dest="crop_y_min", type=int, default=None,
        help="クロップ範囲 y の最小値 [px]（デフォルト: 0）",
    )
    parser.add_argument(
        "--crop-y-max", dest="crop_y_max", type=int, default=None,
        help="クロップ範囲 y の最大値 [px]（デフォルト: output_height）",
    )
    parser.add_argument(
        "--workers", type=int, default=None,
        help="並列処理数（デフォルト: CPUコア数 - 1）",
    )

    return parser


def load_config_file(path: Path) -> dict[str, Any]:
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"設定ファイルの形式が不正です: {path}")

    unknown_keys = set(data) - set(CONFIG_KEYS) - set(IGNORED_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(f"設定ファイルに不明なキーがあります: {sorted(unknown_keys)}")

    return {k: v for k, v in data.items() if k not in IGNORED_CONFIG_KEYS}


def resolve_config(args: argparse.Namespace) -> dict[str, Any]:
    config: dict[str, Any] = {}

    if args.config is not None:
        config.update(load_config_file(args.config))

    for key in CONFIG_KEYS:
        value = getattr(args, key, None)
        if value is not None:
            config[key] = value

    if not config.get("input_dir"):
        raise ValueError(
            "input_dir を指定してください（--input-dir オプション、または設定ファイル）。"
        )

    config.setdefault("output_dir", "corrected")
    config.setdefault("hshift", 0)

    return config


def collect_tif_files(input_dir: Path) -> list[Path]:
    tif_files = sorted(list(input_dir.glob("*.tif")) + list(input_dir.glob("*.tiff")))

    if not tif_files:
        raise ValueError(f"{input_dir} に .tif/.tiff ファイルが見つかりません。")

    return tif_files


def resolve_output_dir(output_dir: str, input_dir: Path) -> Path:
    path = Path(output_dir).expanduser()

    if path.is_absolute():
        return path

    return input_dir / path


def clamp(value: int, vmin: int, vmax: int) -> int:
    return max(vmin, min(value, vmax))


def compute_scale_range(
    tif_files: list[Path],
    hshifts: list[int],
    new_width: int,
    new_height: int,
    crop_x: tuple[int, int],
    crop_y: tuple[int, int],
) -> tuple[float, float]:
    scaled_min_x, scaled_max_x = crop_x
    scaled_min_y, scaled_max_y = crop_y

    sample_count = min(STAT_SAMPLE_LIMIT, len(tif_files))
    stat_files = tif_files[:sample_count]
    stat_hshifts = hshifts[:sample_count]

    stat_img = preprocess_corrected_image(
        tf_path=stat_files[0],
        hshift=stat_hshifts[0],
        new_width=new_width,
        new_height=new_height,
        scaled_min_x=scaled_min_x,
        scaled_max_x=scaled_max_x,
        scaled_min_y=scaled_min_y,
        scaled_max_y=scaled_max_y,
    )

    if stat_img.size == 0:
        raise ValueError("クロップ範囲が不正なため、画像が空になります。")

    vmin, vmax = np.min(stat_img), np.max(stat_img)

    for tf_path, hshift in zip(stat_files[1:], stat_hshifts[1:]):
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
            raise ValueError("クロップ範囲が不正なため、画像が空になります。")

        _min, _max = np.min(stat_img), np.max(stat_img)
        vmin = min(vmin, _min)
        vmax = max(vmax, _max)

    scale_min = vmin * 0.9
    scale_max = vmax * 1.1

    if scale_max <= scale_min:
        raise ValueError(
            f"スケーリング範囲が不正です: scale_min={scale_min}, scale_max={scale_max}"
        )

    return float(scale_min), float(scale_max)


def describe_hshift(hshift_config: Any) -> str:
    if isinstance(hshift_config, list):
        parts = [
            f"{entry['start']}〜{entry['end']}: hshift={entry['value']}"
            for entry in hshift_config
        ]
        return " / ".join(parts)

    return f"hshift={hshift_config} (全フレーム)"


def run(config: dict[str, Any]) -> None:
    input_dir = Path(config["input_dir"]).expanduser()

    if not input_dir.is_dir():
        raise ValueError(f"入力ディレクトリが存在しません: {input_dir}")

    tif_files = collect_tif_files(input_dir)
    n_files = len(tif_files)

    save_start, save_end, hshift_by_frame = resolve_hshift_map(config["hshift"], n_files)
    selected_tif_files = tif_files[save_start:save_end + 1]

    print(f"hshift 設定: {describe_hshift(config['hshift'])}")
    print(f"保存対象: {len(selected_tif_files)} 枚 (index {save_start}-{save_end})")

    output_width = config.get("output_width")
    output_height = config.get("output_height")

    if output_width is None or output_height is None:
        # 補正後の画像サイズはどのフレームでも同じなので、保存対象の先頭の1枚だけ読んで判定する。
        img = tifffile.imread(selected_tif_files[0])
        corrected_img = sine_correction(align_img(reshape_img(img), hshift_by_frame[0]))
        default_height, default_width = corrected_img.shape
        output_width = default_width if output_width is None else int(output_width)
        output_height = default_height if output_height is None else int(output_height)
    else:
        output_width = int(output_width)
        output_height = int(output_height)

    if output_width < 1 or output_height < 1:
        raise ValueError("output_width / output_height は 1 以上を指定してください。")

    crop_x_min = config.get("crop_x_min")
    crop_x_max = config.get("crop_x_max")
    crop_y_min = config.get("crop_y_min")
    crop_y_max = config.get("crop_y_max")

    crop_x_min = 0 if crop_x_min is None else int(crop_x_min)
    crop_x_max = output_width if crop_x_max is None else int(crop_x_max)
    crop_y_min = 0 if crop_y_min is None else int(crop_y_min)
    crop_y_max = output_height if crop_y_max is None else int(crop_y_max)

    crop_x_min = clamp(crop_x_min, 0, output_width - 1)
    crop_x_max = clamp(crop_x_max, 1, output_width)
    crop_y_min = clamp(crop_y_min, 0, output_height - 1)
    crop_y_max = clamp(crop_y_max, 1, output_height)

    if crop_x_min >= crop_x_max or crop_y_min >= crop_y_max:
        raise ValueError("クロップ範囲が不正です（min は max より小さくしてください）。")

    if not selected_tif_files:
        raise ValueError("保存対象の画像がありません。")

    output_dir = resolve_output_dir(config["output_dir"], input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"出力画像サイズ: {output_width}x{output_height}px, "
        f"クロップ範囲: x={crop_x_min}-{crop_x_max}, y={crop_y_min}-{crop_y_max}"
    )
    print(f"出力先: {output_dir}")

    print("スケーリング範囲を計算中...")
    scale_min, scale_max = compute_scale_range(
        selected_tif_files,
        hshifts=hshift_by_frame,
        new_width=output_width,
        new_height=output_height,
        crop_x=(crop_x_min, crop_x_max),
        crop_y=(crop_y_min, crop_y_max),
    )
    print(f"scale_min={scale_min:.2f}, scale_max={scale_max:.2f}")

    workers = config.get("workers")
    workers = max(1, (os.cpu_count() or 2) - 1) if workers is None else int(workers)
    workers = max(1, workers)

    total = len(selected_tif_files)
    print(f"{total} 枚の画像を {workers} 並列で保存します...")

    done = 0
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                process_and_save_one,
                str(tf),
                str(output_dir),
                hshift,
                output_width,
                output_height,
                crop_x_min,
                crop_x_max,
                crop_y_min,
                crop_y_max,
                scale_min,
                scale_max,
            )
            for tf, hshift in zip(selected_tif_files, hshift_by_frame)
        ]

        for future in as_completed(futures):
            future.result()
            done += 1
            print(f"\r{done}/{total} 完了", end="", flush=True)

    print()
    print(f"完了しました: {output_dir}")


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        config = resolve_config(args)
        run(config)
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
