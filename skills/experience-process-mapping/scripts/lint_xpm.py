#!/usr/bin/env python3
"""Read-only checks for a get_xpm JSON snapshot; never a proof of model quality."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys


VERBS = re.compile(r"^(Сравнить|Выбрать|Оплатить|Подготовиться|Пройти|Совершить|Добраться|Оценить|Проверить|Показать|Оформить|Подтвердить|Собрать|Остановить|Принять|Восстановить|Выполнить|Нажать|Открыть|Ввести)\b", re.I)
BRANCH = re.compile(r"\b(да|нет|если|выбран|выбрана|выбрано|отказ|замена|условие)\b", re.I)
WAIT = re.compile(r"ожидан|задерж|разрыв|необеспеч|может.*прерва|не.?достав|не.?проч|вне контроля", re.I)


def unwrap(value):
    """Accept raw get_xpm JSON or an MCP text-content wrapper."""
    if isinstance(value, dict) and isinstance(value.get("lanes"), list):
        return value
    if isinstance(value, dict) and isinstance(value.get("content"), list):
        for item in value["content"]:
            if item.get("type") == "text":
                try:
                    candidate = json.loads(item["text"])
                except (ValueError, KeyError):
                    continue
                if isinstance(candidate, dict) and isinstance(candidate.get("lanes"), list):
                    return candidate
    raise ValueError("Expected get_xpm JSON with lanes[] or its MCP text-content wrapper")


def inspect_map(value):
    model = unwrap(value)
    issues = []

    def add(level, code, message, *entities):
        issues.append({"level": level, "code": code, "message": message,
                       "entities": [e for e in entities if e is not None]})

    nodes, lane_of, first_on_lane = {}, {}, {}
    for lane in model["lanes"]:
        lane_id = lane.get("id")
        for row in lane.get("rows", []):
            for node in row.get("nodes", []):
                node_id = node.get("id")
                if not node_id:
                    add("error", "missing_node_id", "У точки отсутствует ID", lane_id)
                    continue
                if node_id in nodes:
                    add("error", "duplicate_node_id", "ID встречается более одного раза", node_id)
                nodes[node_id] = node
                lane_of[node_id] = lane_id
                first_on_lane.setdefault(lane_id, node_id)

    links = model.get("links", [])
    outgoing = defaultdict(list)
    pairs, interaction_pairs = set(), set()
    parent = {node_id: node_id for node_id in nodes}

    def find(node_id):
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    for link in links:
        source, target = link.get("sourceNodeId"), link.get("targetNodeId")
        kind, link_id = str(link.get("type", "")).lower(), link.get("id")
        if source not in nodes or target not in nodes:
            add("error", "broken_link", "Один из концов связи отсутствует", link_id, source, target)
            continue
        if (source, target) in pairs:
            add("error", "duplicate_pair", "В одном направлении создано несколько связей пары", link_id, source, target)
        pairs.add((source, target))
        if kind == "interaction":
            pair = frozenset((source, target))
            if pair in interaction_pairs:
                add("error", "reverse_interaction_duplicate", "Повтор одного взаимодействия", link_id, source, target)
            interaction_pairs.add(pair)
            if lane_of[source] == lane_of[target]:
                add("error", "interaction_same_lane", "Контакт содержит две стороны одной дорожки", link_id, source, target)
            parent[find(source)] = find(target)
        elif kind in ("sequencesolid", "sequencedashed"):
            outgoing[source].append(link)
            if lane_of[source] != lane_of[target]:
                add("review", "cross_lane_sequence", "Проверить смысл перехода между ролями: это следование или пропущенный контакт? Не менять тип автоматически.", link_id)
            label = link.get("label") or ""
            if kind == "sequencedashed" and BRANCH.search(label) and not WAIT.search(label):
                add("review", "conditional_dashed", "Пунктир выглядит обозначением условия. Проверить, есть ли реальный разрыв/необеспеченность; условие само по себе не требует пунктира.", link_id)
        else:
            add("review", "unknown_link_type", "Неизвестный тип связи: сверить актуальный runtime", link_id)

    components = defaultdict(list)
    for node_id in nodes:
        components[find(node_id)].append(node_id)
    for component in components.values():
        counts = Counter(lane_of[node_id] for node_id in component)
        if len(component) > 1 and any(count > 1 for count in counts.values()):
            add("error", "interaction_group_repeats_lane", "В связной группе interaction повторяется дорожка; проверяется вся группа, а не только соседняя пара.", *component)

    starts = [n for n in nodes.values() if n.get("isStart")]
    if not starts:
        add("review", "missing_start", "Нет отмеченного старта: проверить рамку и состояние заготовки")
    for node_id, node in nodes.items():
        kind = str(node.get("type", "")).lower()
        name = node.get("name") or ""
        layers = {str(l.get("type", "")).lower(): l for l in node.get("layers", [])}

        def filled(layer):
            data = layers.get(layer, {})
            return bool(data.get("isEnabled") and any(isinstance(v, str) and v.strip() for v in data.get("values", [])))

        if node.get("isStart") and (kind != "keypoint" or first_on_lane.get(lane_of[node_id]) != node_id):
            add("review", "start_type_or_position", "Проверить тип и положение стартовой точки по runtime", node_id)
        if kind == "keypoint":
            for layer in ("input", "output"):
                if not filled(layer):
                    add("review", "key_point_missing_io", f"Нет заполненного {layer}; выяснить содержание, не заполнять фиктивно", node_id)
        if kind == "trigger":
            if "?" not in name:
                add("review", "trigger_not_question", "Условие триггера не сформулировано вопросом", node_id)
            if len(outgoing[node_id]) < 2:
                add("review", "trigger_missing_outcome", "У развилки меньше двух исходов; проверить полноту", node_id)
            for link in outgoing[node_id]:
                if not (link.get("label") or "").strip():
                    add("review", "trigger_unlabelled_outcome", "Исход развилки не подписан", node_id, link.get("id"))
            if filled("input") or filled("condition"):
                add("review", "trigger_layer_support", "Input и Condition отклонялись сервером для Trigger 2026-11-06. Проверить текущий контракт; не считать общий enum доказательством поддержки.", node_id)
        elif VERBS.search(name):
            add("review", "operation_as_point", "Проверить ситуацию и масштаб: имя похоже на отдельное действие. Одной замены глагола существительным недостаточно.", node_id)
        if filled("barriers") and not filled("means"):
            add("review", "barrier_without_means", "Есть барьеры, но средства не раскрыты. Добавить подтверждённое средство, явный кандидат или исследовательский вопрос, если это входит в рамку.", node_id)

    counts = Counter(issue["level"] for issue in issues)
    return {"scope": "Read-only structural checks and review signals; not a methodological or empirical proof",
            "node_count": len(nodes), "link_count": len(links),
            "error_count": counts["error"], "review_count": counts["review"], "issues": issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="Local get_xpm JSON snapshot")
    args = parser.parse_args()
    try:
        report = inspect_map(json.loads(args.snapshot.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
