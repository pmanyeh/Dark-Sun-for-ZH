#!/usr/bin/env python3
"""Bring existing translations in line with the glossary (docs/名詞權威對照表.md).

The 2026-09-26 consistency audit (docs/名稱一致性檢查.md) found proper nouns
rendered several ways across dialogue, NAME-1, SPIN and the fixed UI labels.
Each rule below rewrites the stray renderings to the glossary's single form.

A rule applies to a unit only when the unit's English contains the term
(``english``), because words such as 衛兵 or 先知 are also ordinary Chinese.
Renderings that can only be a stray translation of the term (``anywhere``)
are rewritten in every unit, which also catches lines where the English uses
a pronoun or the name sits in the neighbouring sentence fragment.

The dialogue unit is updated in all four catalog files in lockstep; NAME-1
names also in localization/NAME_objects_translated.json, which the name
record build reads. Run with --write to save; without it, print the changes.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "localization/catalog"
NAME_TRANSLATIONS = ROOT / "localization/NAME_objects_translated.json"

# (English pattern, [(Chinese pattern, replacement)], anywhere)
RULES: list[tuple[str, list[tuple[str, str]], bool]] = [
    (r"Balkazar", [("巴卡扎", "巴爾卡札")], True),
    (r"Chahl", [("恰爾", "查爾")], True),
    (r"Kwerin", [("克維林", "奎林")], True),
    (r"(?i)psurlon", [("索倫怪", "蘇隆蟲人")], True),
    (r"(?i)skull elder", [("頭骨長者", "頭骨長老")], True),
    (r"(?i)templar", [("聖職官", "聖堂武士")], True),
    (r"(?i)visionar", [("先知", "預言者")], False),
    (r"(?i)psionicist", [("心靈師", "靈能師"), ("靈法師", "靈能師")], True),
    (r"(?i)dark spider", [("幽暗蜘蛛", "暗黑蜘蛛")], True),
    (r"\bScar\b", [("刀疤", "疤面")], False),
    # "ratman" (what others call them, often as an insult) stays 鼠人.
    (r"\bTari\b", [(r"(?<!塔里)鼠人", "塔里鼠人")], False),
    (r"(?i)folk of undermountain|undermountain folk",
     [("地底山脈的部族民", "山下遺民"), ("地底山脈的族人", "山下遺民")], False),
    (r"Tristram", [("崔斯特蘭", "崔絲特蘭"), ("崔斯特姆", "崔絲特蘭"), ("崔斯特朗", "崔絲特蘭")], True),
    (r"(?i)defiler", [("滅絕者", "荒蕪術士"), ("毀滅巫師", "荒蕪術士")], False),
    (r"(?i)guard", [("衛兵", "守衛")], False),
    (r"Shadow King", [("暗影之王", "陰影之王"), (r"(?<!陰)影王", "陰影之王")], False),
    (r"(?i)shadow", [("幽影", "陰影"), (r"暗影(?![堡之])", "陰影")], False),
    (r"(?i)announcer", [("司儀", "主持人"), ("報幕官", "主持人")], False),
    (r"(?i)genie", [("鎮尼", "巨靈")], True),
    (r"(?i)mastyrial", [("馬斯泰里", "巨蠍獸")], True),
    (r"Dagolar", [(r"達哥拉(?!爾)", "達戈拉爾")], True),
    (r"(?i)silt horror", [("淤泥恐魔", "淤泥巨怪")], True),
    (r"(?i)dagolar slime", [("達戈拉爾軟泥怪", "達戈軟泥怪")], True),
    (r"(?i)thri-kreen", [("螳螂戰士", "螳螂人")], True),
    (r"(?i)wyvern master", [("雙足飛龍大師", "威弗恩大師")], True),
    (r"(?i)wyvern hook", [(r"(?<!雙足)飛龍騎?鉤", "雙足飛龍鉤")], False),
    (r"Churr-te-tunk", [("楚爾-特-通克", "楚爾特通克")], True),
    (r"Cli(?:c)?kk?-tunk", [("克利克-通克", "克利克通克")], True),
    (r"(?i)lesser (?:air|water|earth|fire) elemental", [(r"次級(?=[風水土火]元素)", "小型")], False),
    (r"(?i)trustee", [(r"(?<!特權)管事", "特權管事")], False),
    (r"(?i)\branger", [("巡林客", "遊俠")], True),
    # 2026-09-27: names found in the second SEGOBJEX pass.
    (r"(?i)tanelyv", [("塔奈利夫", "泰內利夫"), ("塔內利夫", "泰內利夫")], True),
    (r"(?i)\bslig", [("蛇蜥", "斯拉格人"), ("斯利格怪", "斯拉格人")], False),
    (r"(?i)rampager", [("暴虐獸", "狂暴獸")], True),
    # Thri-kreen lines that do not also mention the tohr-kreen.
    (r"(?i)^(?!.*tohr-kreen).*thri-kreen", [("托爾螳螂人", "螳螂人"), ("塞庫獵手", "螳螂人")], False),
    (r"Cheee-smak-tunk", [("琪-斯瑪克-通克", "琪斯瑪通克")], True),
    (r"(?i)magera", [(r"(?:瑪格拉|馬吉拉)(?:巨怪|人|獸|族)?", "瑪格拉族")], False),
]
COMPILED = [(re.compile(english), [(re.compile(old), new) for old, new in pairs], anywhere)
            for english, pairs, anywhere in RULES]


def unify(english: str, chinese: str) -> tuple[str, list[str]]:
    applied = []
    for english_pattern, pairs, anywhere in COMPILED:
        if not (anywhere or english_pattern.search(english)):
            continue
        for old, new in pairs:
            chinese, count = old.subn(new, chinese)
            if count:
                applied.append(f"{old.pattern}->{new}")
    return chinese, applied


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--report", type=Path, help="write the change list here (UTF-8)")
    args = parser.parse_args()

    manifest_json = CATALOG / "localization_manifest.json"
    manifest = json.loads(manifest_json.read_text(encoding="utf-8"))
    changes: dict[str, str] = {}
    lines = []
    for unit in manifest["units"]:
        chinese = unit.get("translation_zh_tw") or ""
        if not chinese:
            continue
        new, applied = unify(unit["original"], chinese)
        if new != chinese:
            changes[unit["unit_id"]] = new
            lines.append(f"[{unit['category']}] {unit['unit_id']} {'; '.join(applied)}\n"
                         f"    EN {unit['original']}\n    舊 {chinese}\n    新 {new}")
    labels_path = CATALOG / "fixed_ui_labels.csv"
    label_fields, labels = load_csv(labels_path)
    for label in labels:
        new, applied = unify(label["original"], label["translation_zh_tw"])
        if new != label["translation_zh_tw"]:
            lines.append(f"[fixed_ui] {label['unit_id']} {'; '.join(applied)}\n"
                         f"    舊 {label['translation_zh_tw']}\n    新 {new}")
            label["translation_zh_tw"] = new
    report = "\n".join(lines) + f"\n\n{len(lines)} unit(s) changed\n"
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    else:
        print(report)
    if not args.write:
        return 0

    for unit in manifest["units"]:
        if unit["unit_id"] in changes:
            unit["translation_zh_tw"] = changes[unit["unit_id"]]
    manifest_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    units_json = CATALOG / "dialogue_units.json"
    dialogue = json.loads(units_json.read_text(encoding="utf-8"))
    for unit in dialogue["units"]:
        if unit["unit_id"] in changes:
            unit["translation_zh_tw"] = changes[unit["unit_id"]]
    units_json.write_text(json.dumps(dialogue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in (CATALOG / "localization_manifest.csv", CATALOG / "dialogue_units.csv"):
        fields, rows = load_csv(path)
        for row in rows:
            if row["unit_id"] in changes:
                row["translation_zh_tw"] = changes[row["unit_id"]]
        write_csv(path, fields, rows)
    write_csv(labels_path, label_fields, labels)
    names = json.loads(NAME_TRANSLATIONS.read_text(encoding="utf-8"))
    for entry in names["entries"]:
        new, _ = unify(entry["en"], entry["zh"])
        entry["zh"] = new
    NAME_TRANSLATIONS.write_text(json.dumps(names, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
