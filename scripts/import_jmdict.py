#!/usr/bin/env python3
"""Build a larger Japanese rhythm lexicon from JMdict and UniDic Lite.

JMdict supplies common headwords, readings, parts of speech, and short English
glosses. UniDic Lite supplies lexical pitch-accent types. Accent types are
rendered as stylized 0/1/2 contours for the app's low/mid/high input grid.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

from fugashi import Tagger


JMDICT_URL = "https://www.edrdg.org/pub/Nihongo/JMdict_e.gz"
JMDICT_PROJECT_URL = "https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project"
JMDICT_LICENSE_URL = "https://www.edrdg.org/edrdg/licence.html"
UNIDIC_URL = "https://clrd.ninjal.ac.jp/unidic/en/"
PITCH_SOURCE = "unidic-lite-2.1.2-accent-3level-v1"
JAPANESE_WORD = re.compile(r"^[\u3040-\u30ff\u3400-\u9fff々〆ヶー・]+$")
KANA_READING = re.compile(r"^[ぁ-ゖー]+$")
SMALL_KANA = set("ゃゅょぁぃぅぇぉゎゕゖ")
SKIP_POS = ("particle", "auxiliary verb", "copula", "prefix", "suffix", "counter")

VOWEL_GROUPS = {
    "a": set("あかさたなはまやらわがざだばぱぁゃゎゕ"),
    "i": set("いきしちにひみりゐぎじぢびぴぃ"),
    "u": set("うくすつぬふむゆるぐずづぶぷぅゅゔ"),
    "e": set("えけせてねへめれゑげぜでべぺぇ"),
    "o": set("おこそとのほもよろをごぞどぼぽぉょゖ"),
}

SEMANTIC_RULES = {
    "音楽": ("music", "song", "sing", "sound", "rhythm", "voice", "melody", "rap"),
    "感情": ("emotion", "feeling", "love", "anger", "sad", "happy", "fear", "joy", "hate"),
    "人間": ("person", "human", "people", "man", "woman", "child", "friend", "family"),
    "身体": ("body", "heart", "head", "hand", "eye", "blood", "face", "mouth"),
    "自然": ("nature", "sky", "sea", "ocean", "mountain", "river", "wind", "rain", "snow", "fire"),
    "時間": ("time", "day", "night", "morning", "future", "past", "year", "moment"),
    "場所": ("place", "room", "house", "city", "country", "street", "world"),
    "行動": ("action", "act", "move", "walk", "run", "make", "do", "go", "come"),
    "思考": ("think", "thought", "mind", "idea", "know", "meaning", "memory", "dream"),
    "社会": ("society", "government", "money", "work", "law", "war", "power", "school"),
    "物質": ("thing", "object", "material", "metal", "stone", "water", "air"),
    "食": ("food", "eat", "drink", "taste", "meal", "fruit"),
    "光": ("light", "bright", "shine", "sun", "star", "white"),
    "闇": ("dark", "shadow", "black", "death", "nightmare"),
}

TEXTURE_RULES = {
    "硬い": ("hard", "solid", "stiff"),
    "柔らかい": ("soft", "gentle", "smooth"),
    "冷たい": ("cold", "cool", "ice", "frozen"),
    "熱い": ("hot", "heat", "warm", "burning"),
    "速い": ("fast", "quick", "rapid", "speed"),
    "重い": ("heavy", "weight"),
    "軽い": ("lightweight", "lightness"),
    "鋭い": ("sharp", "keen"),
}


def katakana_to_hiragana(text: str) -> str:
    converted: list[str] = []
    for char in text:
        code = ord(char)
        converted.append(chr(code - 0x60) if 0x30A1 <= code <= 0x30F6 else char)
    return "".join(converted)


def split_morae(reading: str) -> list[str]:
    morae: list[str] = []
    for char in katakana_to_hiragana(reading):
        if char in SMALL_KANA and morae:
            morae[-1] += char
        else:
            morae.append(char)
    return morae


def vowel_pattern(reading: str) -> str:
    vowels: list[str] = []
    for char in katakana_to_hiragana(reading):
        if char == "ー":
            if vowels:
                vowels.append(vowels[-1])
            continue
        if char == "ん":
            vowels.append("N")
            continue
        if char == "っ":
            vowels.append("Q")
            continue
        for vowel, chars in VOWEL_GROUPS.items():
            if char in chars:
                if char in SMALL_KANA and vowels:
                    vowels[-1] = vowel
                else:
                    vowels.append(vowel)
                break
    return "".join(vowels)


def priority_score(tags: list[str]) -> int:
    score = 0
    weights = {
        "ichi1": 1000,
        "news1": 900,
        "spec1": 720,
        "gai1": 680,
        "ichi2": 520,
        "news2": 460,
        "spec2": 380,
        "gai2": 340,
    }
    for tag in tags:
        score += weights.get(tag, 0)
        if tag.startswith("nf") and tag[2:].isdigit():
            score += max(1, 800 - int(tag[2:]) * 12)
    return score


def first_texts(element: ET.Element, path: str) -> list[str]:
    return [node.text for node in element.findall(path) if node.text]


def choose_headword(entry: ET.Element) -> tuple[str, str, list[str]] | None:
    kanji = []
    for node in entry.findall("k_ele"):
        word = node.findtext("keb")
        if word:
            tags = first_texts(node, "ke_pri")
            kanji.append((priority_score(tags), word, tags))
    kanji.sort(key=lambda item: (-item[0], item[1]))
    chosen_word = kanji[0][1] if kanji else ""

    readings = []
    for node in entry.findall("r_ele"):
        reading = node.findtext("reb")
        if not reading:
            continue
        restrictions = set(first_texts(node, "re_restr"))
        if restrictions and chosen_word and chosen_word not in restrictions:
            continue
        tags = first_texts(node, "re_pri")
        readings.append((priority_score(tags), reading, tags))
    if not readings:
        return None
    readings.sort(key=lambda item: (-item[0], item[1]))
    _, reading, reading_tags = readings[0]
    if not chosen_word:
        chosen_word = reading
    chosen_tags = (kanji[0][2] if kanji else []) + reading_tags
    return chosen_word, katakana_to_hiragana(reading), chosen_tags


def pos_label(pos: str) -> str:
    lowered = pos.lower()
    if "noun" in lowered:
        return "名詞"
    if "adjective" in lowered or "adjectival" in lowered:
        return "形容"
    if "verb" in lowered:
        return "動詞"
    if "adverb" in lowered:
        return "副詞"
    if "interjection" in lowered:
        return "感動詞"
    if "pronoun" in lowered:
        return "代名詞"
    if "conjunction" in lowered:
        return "接続詞"
    if "expression" in lowered:
        return "表現"
    return "語彙"


def extract_tags(glosses: list[str], pos: str) -> tuple[list[str], list[str]]:
    text = " ".join(glosses).lower()
    semantic = [pos_label(pos)]
    for label, keywords in SEMANTIC_RULES.items():
        if any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in keywords):
            semantic.append(label)
    texture = [
        label
        for label, keywords in TEXTURE_RULES.items()
        if any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in keywords)
    ]
    return semantic[:4], texture[:3]


def accent_contour(mora_count: int, accent: int) -> list[int]:
    if mora_count <= 0:
        return []
    if mora_count == 1:
        return [2 if accent == 1 else 1]
    accent = max(0, min(accent, mora_count))
    if accent == 0:
        return [0, 1, *([2] * (mora_count - 2))]
    if accent == 1:
        return [2, 1, *([0] * (mora_count - 2))]
    if accent >= mora_count:
        return [0, *([1] * (mora_count - 2)), 2]
    return [0, *([1] * (accent - 2)), 2, *([0] * (mora_count - accent))]


def parse_accents(value: str | None, mora_count: int) -> list[int]:
    accents: list[int] = []
    for raw in re.findall(r"\d+", value or ""):
        accent = min(int(raw), mora_count)
        if accent not in accents:
            accents.append(accent)
    return accents or [0]


def resample(shape: list[int], target_length: int) -> list[int]:
    if len(shape) == target_length:
        return shape
    if not shape:
        return accent_contour(target_length, 0)
    if target_length == 1:
        return [shape[0]]
    return [shape[round(index * (len(shape) - 1) / (target_length - 1))] for index in range(target_length)]


def accent_shapes(tagger: Tagger, word: str, reading: str) -> tuple[list[list[int]], float]:
    target_length = len(split_morae(reading))
    tokens = list(tagger(word))
    if not tokens:
        return [accent_contour(target_length, 0)], 0.5

    token_shapes: list[list[list[int]]] = []
    exact = len(tokens) == 1
    for token in tokens:
        pronunciation = token.feature.pron or token.surface
        count = len(split_morae(pronunciation))
        accents = parse_accents(token.feature.aType, count)
        token_shapes.append([accent_contour(count, accent) for accent in accents[:3]])

    primary = [value for options in token_shapes for value in options[0]]
    variants = [resample(primary, target_length)]
    for token_index, options in enumerate(token_shapes):
        for alternative in options[1:]:
            combined: list[int] = []
            for index, candidate_options in enumerate(token_shapes):
                combined.extend(alternative if index == token_index else candidate_options[0])
            candidate = resample(combined, target_length)
            if candidate not in variants:
                variants.append(candidate)
    return variants[:4], 0.92 if exact else 0.78


def parse_candidates(source: Path) -> list[dict]:
    candidates: list[dict] = []
    with gzip.open(source, "rb") as stream:
        for _, entry in ET.iterparse(stream, events=("end",)):
            if entry.tag != "entry":
                continue
            chosen = choose_headword(entry)
            if chosen:
                word, reading, priority_tags = chosen
                morae = split_morae(reading)
                pos_values = first_texts(entry, "./sense/pos")
                pos = pos_values[0] if pos_values else ""
                glosses = first_texts(entry, "./sense/gloss")[:4]
                score = priority_score(priority_tags)
                if (
                    score > 0
                    and 1 <= len(morae) <= 10
                    and JAPANESE_WORD.fullmatch(word)
                    and KANA_READING.fullmatch(reading)
                    and not any(blocked in pos.lower() for blocked in SKIP_POS)
                ):
                    candidates.append({
                        "seq": entry.findtext("ent_seq") or "0",
                        "word": word,
                        "reading": reading,
                        "score": score,
                        "pos": pos,
                        "glosses": glosses,
                    })
            entry.clear()
    candidates.sort(key=lambda item: (-item["score"], int(item["seq"]), item["word"]))
    return candidates


def build_word(tagger: Tagger, candidate: dict) -> dict:
    reading = candidate["reading"]
    variants, confidence = accent_shapes(tagger, candidate["word"], reading)
    vowels = vowel_pattern(reading)
    semantic, texture = extract_tags(candidate["glosses"], candidate["pos"])
    return {
        "id": f"jmdict-{candidate['seq']}",
        "word": candidate["word"],
        "reading": reading,
        "language": "ja",
        "rhythmShape": variants[0],
        "rhythmVariants": variants,
        "moraCount": len(split_morae(reading)),
        "vowelPattern": vowels,
        "rhymeFamily": f"-{vowels[-3:]}" if vowels else "",
        "partOfSpeech": pos_label(candidate["pos"]),
        "semanticTags": semantic,
        "associationTags": semantic[1:],
        "textureTags": texture,
        "reviewStatus": "auto_generated",
        "pitchSource": PITCH_SOURCE,
        "rhythmConfidence": confidence,
        "metadataConfidence": 0.82,
        "sourceId": "jmdict",
        "sourceUrl": JMDICT_PROJECT_URL,
        "license": "CC BY-SA 4.0",
        "glosses": candidate["glosses"],
    }


def refresh_source(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".download")
    urllib.request.urlretrieve(JMDICT_URL, temporary)
    temporary.replace(destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("public/data/db.json"))
    parser.add_argument("--input", type=Path, default=Path("artifacts/JMdict_e.xml.gz"))
    parser.add_argument("--limit", type=int, default=2000, help="target Japanese word count")
    parser.add_argument("--refresh", action="store_true", help="download the latest official JMdict first")
    parser.add_argument("--write", action="store_true", help="replace generated JMdict rows in db.json")
    args = parser.parse_args()

    if args.refresh:
        refresh_source(args.input)
    if not args.input.exists():
        parser.error(f"JMdict file not found: {args.input}. Use --refresh first.")

    database = json.loads(args.db.read_text(encoding="utf-8"))
    preserved = [word for word in database["words"] if word.get("sourceId") != "jmdict" and not word["id"].startswith("jmdict-")]
    preserved_japanese = [word for word in preserved if word["language"] == "ja"]
    needed = max(0, args.limit - len(preserved_japanese))
    existing_words = {word["word"] for word in preserved}

    selected: list[dict] = []
    for candidate in parse_candidates(args.input):
        if candidate["word"] in existing_words:
            continue
        existing_words.add(candidate["word"])
        selected.append(candidate)
        if len(selected) >= needed:
            break

    tagger = Tagger()
    generated = [build_word(tagger, candidate) for candidate in selected]
    summary = {
        "targetJapaneseWords": args.limit,
        "preservedJapaneseWords": len(preserved_japanese),
        "generatedWords": len(generated),
        "finalJapaneseWords": len(preserved_japanese) + len(generated),
        "pitchSource": PITCH_SOURCE,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.write:
        database["version"] = "0.3.0"
        database.pop("sourceSpreadsheet", None)
        database["exportedAt"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        database["words"] = preserved + generated
        database["dataSources"] = [
            {
                "id": "jmdict",
                "name": "JMdict Japanese-Multilingual Dictionary",
                "url": JMDICT_PROJECT_URL,
                "license": "CC BY-SA 4.0",
                "licenseUrl": JMDICT_LICENSE_URL,
            },
            {
                "id": "unidic-lite",
                "name": "UniDic Lite 2.1.2",
                "url": UNIDIC_URL,
                "license": "New BSD",
            },
        ]
        args.db.write_text(json.dumps(database, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
