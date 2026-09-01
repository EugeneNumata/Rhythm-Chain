#!/usr/bin/env python3
"""Generate relative low/mid/high contours from macOS Japanese TTS.

This is a development-time generator. It never runs in the PWA. For every
Japanese entry in public/data/db.json it synthesizes the reading with `say`,
estimates F0 by autocorrelation, divides the voiced region into mora slots, and
quantizes the per-mora median pitch to 0/1/2 within that word.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import subprocess
import tempfile
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


SMALL_KANA = set("ゃゅょぁぃぅぇぉゎゕゖ")
SKIP_CHARS = set(" 　、。・,.!?！？()（）[]「」『』")


@dataclass
class PitchResult:
    word_id: str
    word: str
    reading: str
    morae: list[str]
    f0_hz: list[float]
    semitones: list[float]
    rhythm_shape: list[int]
    pitch_span_semitones: float
    voiced_frame_ratio: float
    confidence: float


def katakana_to_hiragana(text: str) -> str:
    converted: list[str] = []
    for char in text:
        code = ord(char)
        if 0x30A1 <= code <= 0x30F6:
            converted.append(chr(code - 0x60))
        else:
            converted.append(char)
    return "".join(converted)


def split_morae(reading: str) -> list[str]:
    morae: list[str] = []
    for char in katakana_to_hiragana(reading):
        if char in SKIP_CHARS:
            continue
        if char in SMALL_KANA and morae:
            morae[-1] += char
        else:
            morae.append(char)
    return morae


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def synthesize(reading: str, output_wav: Path, voice: str, rate: int) -> None:
    with tempfile.TemporaryDirectory(prefix="rhythm-chain-tts-") as directory:
        aiff_path = Path(directory) / "speech.aiff"
        run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff_path), reading])
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(aiff_path), "-ac", "1", "-ar", "22050",
            "-c:a", "pcm_s16le", str(output_wav),
        ])


def read_wav(path: Path) -> tuple[int, np.ndarray]:
    with wave.open(str(path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        frames = wav_file.readframes(wav_file.getnframes())
    if channels != 1 or sample_width != 2:
        raise ValueError("Expected mono 16-bit PCM WAV")
    signal = np.frombuffer(frames, dtype="<i2").astype(np.float64) / 32768.0
    return sample_rate, signal


def estimate_pitch(signal: np.ndarray, sample_rate: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frame_length = int(sample_rate * 0.04)
    hop_length = int(sample_rate * 0.01)
    minimum_lag = max(1, int(sample_rate / 480))
    maximum_lag = int(sample_rate / 65)
    window = np.hanning(frame_length)

    times: list[float] = []
    pitches: list[float] = []
    rms_values: list[float] = []

    for start in range(0, max(1, len(signal) - frame_length), hop_length):
        frame = signal[start : start + frame_length]
        if len(frame) < frame_length:
            break
        frame = frame - np.mean(frame)
        rms = float(np.sqrt(np.mean(frame * frame)))
        rms_values.append(rms)
        times.append((start + frame_length / 2) / sample_rate)

        weighted = frame * window
        autocorrelation = np.correlate(weighted, weighted, mode="full")[frame_length - 1 :]
        zero_lag = autocorrelation[0]
        if zero_lag <= 1e-10:
            pitches.append(float("nan"))
            continue

        search = autocorrelation[minimum_lag : maximum_lag + 1]
        peak_offset = int(np.argmax(search))
        lag = minimum_lag + peak_offset
        normalized_peak = float(autocorrelation[lag] / zero_lag)
        if normalized_peak < 0.3:
            pitches.append(float("nan"))
            continue

        if 1 <= lag < len(autocorrelation) - 1:
            left, center, right = autocorrelation[lag - 1 : lag + 2]
            denominator = left - 2 * center + right
            if abs(denominator) > 1e-10:
                lag += float(0.5 * (left - right) / denominator)
        pitches.append(float(sample_rate / lag))

    return np.asarray(times), np.asarray(pitches), np.asarray(rms_values)


def fill_missing(values: np.ndarray) -> np.ndarray:
    valid = np.isfinite(values)
    if not np.any(valid):
        raise ValueError("No voiced pitch could be estimated")
    indices = np.arange(len(values))
    return np.interp(indices, indices[valid], values[valid])


def quantize_word(signal: np.ndarray, sample_rate: int, mora_count: int) -> tuple[list[float], list[float], list[int], float, float, float]:
    times, pitches, rms = estimate_pitch(signal, sample_rate)
    if len(times) == 0:
        raise ValueError("Audio was too short")

    loud = rms >= max(float(np.max(rms)) * 0.1, 0.002)
    voiced = np.isfinite(pitches) & loud
    if not np.any(voiced):
        raise ValueError("No voiced frames remained after silence filtering")

    active_indices = np.flatnonzero(loud)
    start_time = max(0.0, float(times[active_indices[0]] - 0.025))
    end_time = float(times[active_indices[-1]] + 0.025)
    boundaries = np.linspace(start_time, end_time, mora_count + 1)

    slot_f0: list[float] = []
    for index in range(mora_count):
        in_slot = (times >= boundaries[index]) & (times < boundaries[index + 1]) & voiced
        slot_f0.append(float(np.median(pitches[in_slot])) if np.any(in_slot) else float("nan"))

    f0 = fill_missing(np.asarray(slot_f0, dtype=np.float64))
    reference = float(np.median(f0))
    semitones = 12 * np.log2(f0 / reference)
    low = float(np.min(semitones))
    high = float(np.max(semitones))
    span = high - low

    if span < 0.8:
        shape = np.ones(mora_count, dtype=np.int64)
    else:
        # Relative note classification by balanced ordinal rank. Using equal
        # slices of the absolute range overreacts to a phrase-final fall, while
        # raw quantiles can leave no middle notes in a four-mora word. Average
        # ranks keep ties together and distribute a real contour across 0/1/2.
        order = np.argsort(semitones)
        ranks = np.empty(mora_count, dtype=np.float64)
        sorted_values = semitones[order]
        cursor = 0
        while cursor < mora_count:
            end = cursor + 1
            while end < mora_count and abs(sorted_values[end] - sorted_values[cursor]) < 0.05:
                end += 1
            average_rank = (cursor + end - 1) / 2
            ranks[order[cursor:end]] = average_rank
            cursor = end
        normalized_ranks = ranks / max(1, mora_count - 1)
        shape = np.floor(normalized_ranks * 2 + 0.5).astype(np.int64)

    voiced_ratio = float(np.count_nonzero(voiced) / max(1, np.count_nonzero(loud)))
    coverage = float(np.count_nonzero(np.isfinite(slot_f0)) / mora_count)
    span_score = min(1.0, span / 3.0)
    confidence = max(0.0, min(0.8, 0.45 * voiced_ratio + 0.35 * coverage + 0.20 * span_score))

    return (
        [round(float(value), 2) for value in f0],
        [round(float(value), 2) for value in semitones],
        [int(value) for value in shape],
        round(span, 2),
        round(voiced_ratio, 3),
        round(confidence, 3),
    )


def analyze_word(word: dict, voice: str, rate: int) -> PitchResult:
    reading = str(word.get("reading") or word["word"])
    morae = split_morae(reading)
    if not morae:
        raise ValueError(f"No morae found for {word['word']}")

    with tempfile.TemporaryDirectory(prefix="rhythm-chain-word-") as directory:
        wav_path = Path(directory) / "word.wav"
        synthesize(reading, wav_path, voice, rate)
        sample_rate, signal = read_wav(wav_path)
        f0, semitones, shape, span, voiced_ratio, confidence = quantize_word(
            signal, sample_rate, len(morae)
        )

    return PitchResult(
        word_id=word["id"],
        word=word["word"],
        reading=reading,
        morae=morae,
        f0_hz=f0,
        semitones=semitones,
        rhythm_shape=shape,
        pitch_span_semitones=span,
        voiced_frame_ratio=voiced_ratio,
        confidence=confidence,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("public/data/db.json"))
    parser.add_argument("--report", type=Path, default=Path("artifacts/pitch-report.json"))
    parser.add_argument("--voice", default="Kyoko")
    parser.add_argument("--rate", type=int, default=170)
    parser.add_argument("--write", action="store_true", help="Write generated contours back to db.json")
    args = parser.parse_args()

    database = json.loads(args.db.read_text(encoding="utf-8"))
    japanese_words = [word for word in database["words"] if word.get("language") == "ja"]
    results: list[PitchResult] = []

    for word in japanese_words:
        result = analyze_word(word, args.voice, args.rate)
        results.append(result)
        print(
            f"{result.word:<8} {''.join(result.morae):<10} "
            f"{result.rhythm_shape} span={result.pitch_span_semitones:.2f}st "
            f"confidence={result.confidence:.2f}"
        )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(
            {
                "generator": "macos-say-autocorrelation-v1",
                "voice": args.voice,
                "rate": args.rate,
                "results": [asdict(result) for result in results],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    if args.write:
        by_id = {result.word_id: result for result in results}
        for word in database["words"]:
            result = by_id.get(word["id"])
            if not result:
                continue
            previous_shape = word.get("rhythmShape") or []
            word["rhythmShape"] = result.rhythm_shape
            variants: list[list[int]] = []
            for shape in [result.rhythm_shape, *(word.get("rhythmVariants") or []), previous_shape]:
                if shape and shape not in variants:
                    variants.append(shape)
            word["rhythmVariants"] = variants
            word["moraCount"] = len(result.morae)
            word["pitchSource"] = f"macos-say-{args.voice}-autocorrelation-v1"
            word["rhythmConfidence"] = result.confidence
            word["reviewStatus"] = "auto_generated"
        database["exportedAt"] = datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
        args.db.write_text(json.dumps(database, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
