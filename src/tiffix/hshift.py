"""
hshift（水平方向シフト量）をフレーム区間ごとに指定するための共通ロジック。
CLI (YAML設定) と GUI (複数区間の入力欄) の両方から利用される。
"""

from typing import Any


def normalize_frame_index(index: int, n_files: int) -> int:
    return index if index >= 0 else n_files + index


def resolve_hshift_map(hshift_config: Any, n_files: int) -> tuple[int, int, list[int]]:
    """
    hshift の設定値を解釈し、(save_start, save_end, hshift_by_frame) を返す。

    hshift_config は以下のいずれか:
    - int/float: 全フレームに同じ値を適用する。
    - list[dict]: 各要素は {"start": int, "end": int, "value": int}。
      start/end は0始まりのフレームインデックス（両端を含む）で、
      負の値はPythonのインデックスと同様に末尾からの相対位置を表す（-1が最後）。

    区間指定 (list) の場合、区間の和集合の最小開始インデックスが save_start、
    最大終了インデックスが save_end になる。区間同士の重複や、
    save_start〜save_end の範囲内に指定されていないフレーム（隙間）があればエラー。

    戻り値の hshift_by_frame は save_start 〜 save_end (両端含む) の
    各フレームに対応する hshift 値のリスト。
    """
    if isinstance(hshift_config, bool):
        raise ValueError("hshift は整数、または {start, end, value} のリストで指定してください。")

    if isinstance(hshift_config, (int, float)):
        value = int(hshift_config)
        return 0, n_files - 1, [value] * n_files

    if not isinstance(hshift_config, list):
        raise ValueError("hshift は整数、または {start, end, value} のリストで指定してください。")

    if not hshift_config:
        raise ValueError("hshift の区間が1つも指定されていません。")

    hshift_by_index: list[int | None] = [None] * n_files

    for i, entry in enumerate(hshift_config):
        if not isinstance(entry, dict) or not {"start", "end", "value"} <= set(entry):
            raise ValueError(
                f"hshift の {i} 番目の要素が不正です。"
                f"start/end/value を指定してください: {entry}"
            )

        raw_start = int(entry["start"])
        raw_end = int(entry["end"])
        value = int(entry["value"])

        start_idx = normalize_frame_index(raw_start, n_files)
        end_idx = normalize_frame_index(raw_end, n_files)

        if not (0 <= start_idx <= end_idx <= n_files - 1):
            raise ValueError(
                f"hshift の{i}番目の区間の範囲が不正です"
                f"（start={raw_start}, end={raw_end}, n_files={n_files}）。"
            )

        for idx in range(start_idx, end_idx + 1):
            if hshift_by_index[idx] is not None:
                raise ValueError(f"hshift の範囲が重複しています（フレーム {idx}）。")
            hshift_by_index[idx] = value

    covered = [idx for idx, v in enumerate(hshift_by_index) if v is not None]
    save_start = min(covered)
    save_end = max(covered)

    for idx in range(save_start, save_end + 1):
        if hshift_by_index[idx] is None:
            raise ValueError(f"hshift の範囲に隙間があります（フレーム {idx} が未指定です）。")

    hshift_by_frame = hshift_by_index[save_start:save_end + 1]
    return save_start, save_end, hshift_by_frame  # type: ignore[return-value]
