#!/usr/bin/env python3
"""Kokoro ONNX narration generator with English pronunciation rules.

Reads a ``script.json`` file, applies pronunciation normalization rules
(e.g., ``IP`` -> ``eye pee``, present-tense ``read`` -> ``reed``), synthesizes
WAV clips using ``kokoro_onnx`` (default voice ``am_michael``), and writes a
``manifest.json`` describing every generated clip.

Example usage:
    python tts/narrate.py --script script.json --out-dir out/tts
    python tts/narrate.py --script script.json --dry-run
    python tts/narrate.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

DEFAULT_SCRIPT = "script.json"
DEFAULT_OUT_DIR = "out/tts"
DEFAULT_MODEL_DIR = r"C:\Users\superuser\Downloads\NewsLessons\tts-remote"
DEFAULT_VOICE = "am_michael"
DEFAULT_SPEED = 1.0
DEFAULT_LANG = "en-us"

# ---------------------------------------------------------------------------
# Pronunciation rules
# ---------------------------------------------------------------------------

# 1. IP / IPs / IPv4 / IPv6 rules (word-boundary aware so words like "ship",
#    "tip", "tips", "script", "pipeline" are never modified).
_IP_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bIPv4\b", re.IGNORECASE), "eye pee vee four"),
    (re.compile(r"\bIPv6\b", re.IGNORECASE), "eye pee vee six"),
    (re.compile(r"\bIPs\b"), "eye pees"),
    (re.compile(r"\bIP\b"), "eye pee"),
]

# 2. Context-aware present-tense "read" -> "reed" heuristic.
#
# English "read" is a heteronym:
#   - Present / infinitive / imperative: /riːd/ ("reed")
#   - Simple past / past participle:     /rɛd/  ("red")
#
# Heuristic summary (evaluated in priority order per standalone \bread\b token):
#   1. Compound-hyphen overrides:
#      - "well-read", "widely-read", "much-read", "little-read" -> past ("read")
#      - "read-only", "read/write" -> present ("reed")
#   2. Past / passive-participle cues (keep "read"):
#      - Preceded (allowing intervening adverbs like "already", "just", "not",
#        "never", "previously", "successfully") by perfect or passive
#        auxiliaries: has/have/had/'ve/'d/haven't/hasn't/hadn't or
#        was/were/is/are/am/be/been/being/get/gets/got/gotten/wasn't/weren't/
#        isn't/aren't.
#      - Immediately preceded by a past-time adverb: already, just, previously,
#        earlier, recently, yesterday, once, formerly.
#      - Preceded by a 3rd-person singular pronoun ("he", "she", "it") without
#        an earlier modal/do-support auxiliary ("does he read" is present;
#        "he read" is past because present 3rd-person singular is "reads").
#      - Followed within the same clause by a past-time marker ("yesterday",
#        "last night", "last week", "ago", "earlier").
#   3. Present / infinitive / imperative cues (convert to "reed"):
#      - Preceded by infinitive "to" (with optional split adverb).
#      - Preceded by modal or do-support auxiliary (can/could/will/would/shall/
#        should/may/might/must/do/does/did and contractions/negations), with
#        optional intervening subject/adverb (passive/perfect forms like
#        "can be read" or "should have read" were already caught by rule 2).
#      - Preceded by hortative/imperative cues ("let's", "lets", "let us/me/
#        them/him/her", "please", "now", "next", "first", "then", "also",
#        "help", "helps") or appearing at the start of a sentence/clause.
#      - Preceded by non-3sg present subjects ("I", "we", "you", "they") when
#        no past cue applies.
#      - Followed by a technical noun ("access", "permission(s)", "operation(s)",
#        "latency", "throughput", "speed", "rate", "error(s)", "timeout",
#        "only") or a direct-object/preposition ("the", "a", "an", "this",
#        "that", "these", "those", "our", "your", "my", "its", "their", "all",
#        "every", "each", "more", "from", "through", "out", "back").
#   4. Default fallback: leave as "read" to avoid false positives in ambiguous
#      past-tense narratives.

_READ_WORD_RE = re.compile(r"\bread\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

_PAST_PARTICIPLE_AUX = frozenset({
    "has", "have", "had", "hasn't", "haven't", "hadn't",
    "was", "were", "is", "are", "am", "be", "been", "being",
    "wasn't", "weren't", "isn't", "aren't",
    "get", "gets", "got", "gotten",
})

_PAST_PARTICIPLE_CONTRACTION_SUFFIXES = ("'ve", "'d")

_PAST_ADVERBS = frozenset({
    "already", "just", "previously", "earlier", "recently",
    "yesterday", "once", "formerly",
})

_INTERVENING_ADVERBS = frozenset({
    "not", "never", "ever", "also", "still", "always", "often",
    "already", "just", "previously", "earlier", "recently", "once",
    "easily", "quickly", "carefully", "properly", "successfully",
    "correctly", "fully", "only", "even", "now", "then", "first",
    "directly", "automatically", "continuously", "safely", "cleanly",
})

_MODAL_OR_DO_AUX = frozenset({
    "can", "cannot", "can't", "could", "couldn't",
    "will", "won't", "would", "wouldn't",
    "shall", "shan't", "should", "shouldn't",
    "may", "might", "must", "mustn't",
    "do", "don't", "does", "doesn't", "did", "didn't",
})

_MODAL_CONTRACTION_SUFFIXES = ("'ll",)

_PRESENT_SUBJECTS = frozenset({"i", "we", "you", "they"})
_THIRD_PERSON_SINGULAR_PRONOUNS = frozenset({"he", "she", "it"})

_HORTATIVE_CUES = frozenset({
    "let's", "lets", "please", "help", "helps",
})

_PRESENT_FOLLOWING_WORDS = frozenset({
    "the", "a", "an", "this", "that", "these", "those",
    "our", "your", "my", "its", "their", "all", "every", "each", "more",
    "from", "through", "out", "back", "on",
    "only", "access", "permission", "permissions", "operation", "operations",
    "latency", "throughput", "speed", "rate", "error", "errors", "timeout",
})

_PAST_COMPOUND_PREFIXES = frozenset({"well", "widely", "much", "little", "best"})

_PAST_TIME_FOLLOW_RE = re.compile(
    r"\b(?:yesterday|last\s+(?:night|week|month|year|time)|ago|earlier)\b",
    re.IGNORECASE,
)


def _match_case(original: str, replacement: str) -> str:
    """Match capitalization of ``original`` (UPPER, Title, or lower)."""
    if original.isupper():
        return replacement.upper()
    if original[0].isupper():
        return replacement.capitalize()
    return replacement.lower()


def _is_present_tense_read(text: str, start: int, end: int) -> bool:
    """Return True if the ``read`` match at ``text[start:end]`` is present tense."""
    before_full = text[:start]
    after_full = text[end:]

    # 1. Compound-hyphen / slash checks right next to the word.
    if before_full.endswith("-"):
        prefix_tokens = _TOKEN_RE.findall(before_full[:-1])
        if prefix_tokens and prefix_tokens[-1].lower() in _PAST_COMPOUND_PREFIXES:
            return False
    if after_full.startswith("-only") or after_full.startswith("/write"):
        return True

    # Restrict context to the current clause (split on sentence/clause punctuation).
    clause_before = re.split(r"[.!?;:\n]", before_full)[-1]
    clause_after = re.split(r"[.!?;:\n]", after_full)[0]

    prev_tokens = [t.lower() for t in _TOKEN_RE.findall(clause_before)]
    next_tokens = [t.lower() for t in _TOKEN_RE.findall(clause_after)]

    # 2a. Past/passive auxiliary immediately before "read" (skipping adverbs).
    idx = len(prev_tokens) - 1
    while idx >= 0 and prev_tokens[idx] in _INTERVENING_ADVERBS:
        idx -= 1
    if idx >= 0:
        tok = prev_tokens[idx]
        if tok in _PAST_PARTICIPLE_AUX:
            return False
        if tok.endswith(_PAST_PARTICIPLE_CONTRACTION_SUFFIXES):
            return False

    # 2b. Past-time adverb immediately before "read" (e.g., "already read",
    #     "just read", "previously read"). Allow "to just read" as infinitive.
    if prev_tokens and prev_tokens[-1] in _PAST_ADVERBS:
        if not (len(prev_tokens) >= 2 and prev_tokens[-2] == "to"):
            return False

    # 2c. 3rd-person singular pronoun ("he read", "she read", "it read")
    #     without a preceding modal/do-support auxiliary ("does he read?").
    if prev_tokens and prev_tokens[-1] in _THIRD_PERSON_SINGULAR_PRONOUNS:
        has_modal_before = any(
            t in _MODAL_OR_DO_AUX or t.endswith(_MODAL_CONTRACTION_SUFFIXES)
            for t in prev_tokens[:-1]
        )
        if not has_modal_before:
            return False

    # 2d. Explicit past-time marker later in the same clause.
    if _PAST_TIME_FOLLOW_RE.search(clause_after):
        # Unless explicitly infinitive/modal (e.g., "to read yesterday's logs").
        if not (
            (idx >= 0 and prev_tokens[idx] == "to")
            or any(
                t in _MODAL_OR_DO_AUX or t.endswith(_MODAL_CONTRACTION_SUFFIXES)
                for t in prev_tokens[-4:]
            )
        ):
            return False

    # 3a. Infinitive "to" (+ optional adverbs).
    if idx >= 0 and prev_tokens[idx] == "to":
        return True

    # 3b. Modal or do-support auxiliary within recent clause tokens.
    window = prev_tokens[-4:]
    if any(
        t in _MODAL_OR_DO_AUX or t.endswith(_MODAL_CONTRACTION_SUFFIXES)
        for t in window
    ):
        return True

    # 3c. Hortative / imperative cues ("let's read", "let us read", "please read").
    if prev_tokens:
        if prev_tokens[-1] in _HORTATIVE_CUES:
            return True
        if len(prev_tokens) >= 2 and prev_tokens[-2] == "let" and prev_tokens[-1] in {
            "us", "me", "them", "him", "her", "you",
        }:
            return True

    # 3d. Present-tense subjects ("I read", "we read", "you read", "they read").
    if idx >= 0 and prev_tokens[idx] in _PRESENT_SUBJECTS:
        return True

    # 3e. Imperative at start of sentence/clause (optionally preceded by a
    #     transition adverb like "now", "next", "first", "then").
    if not prev_tokens or all(
        t in {"now", "next", "first", "then", "also", "please"} for t in prev_tokens
    ):
        return True

    # 3f. Followed by a present-tense object/preposition/tech collocation
    #     (e.g., "read the", "read from", "read latency") when no past cue matched.
    if next_tokens and next_tokens[0] in _PRESENT_FOLLOWING_WORDS:
        return True

    return False


def apply_pronunciation_rules(text: str) -> str:
    """Normalize narration text for clearer Kokoro TTS pronunciation.

    Rules applied:
    1. ``IPv4`` -> ``eye pee vee four``, ``IPv6`` -> ``eye pee vee six``,
       ``IPs`` -> ``eye pees``, ``IP`` -> ``eye pee`` (word-boundary aware).
    2. Present-tense / infinitive / imperative ``read`` -> ``reed`` while
       preserving past-tense / participle ``read`` and unrelated words
       (``ready``, ``reading``, ``reader``, ``spread``, ``thread``).
    """
    result = text

    for pattern, replacement in _IP_PATTERNS:
        result = pattern.sub(replacement, result)

    def _replace_read(match: re.Match[str]) -> str:
        if _is_present_tense_read(result, match.start(), match.end()):
            return _match_case(match.group(0), "reed")
        return match.group(0)

    result = _READ_WORD_RE.sub(_replace_read, result)
    return result


# ---------------------------------------------------------------------------
# Model & voices discovery
# ---------------------------------------------------------------------------

def discover_model_files(
    model_dir: Path,
    model_override: str | None = None,
    voices_override: str | None = None,
) -> tuple[Path, Path]:
    """Locate the Kokoro ``.onnx`` model and voices file inside ``model_dir``."""
    if model_override:
        model_path = Path(model_override)
    else:
        if not model_dir.exists():
            raise FileNotFoundError(f"Model directory does not exist: {model_dir}")
        preferred_model = model_dir / "kokoro-v1.0.onnx"
        if preferred_model.is_file():
            model_path = preferred_model
        else:
            candidates = sorted(model_dir.glob("kokoro*.onnx")) or sorted(
                model_dir.glob("*.onnx")
            )
            if not candidates:
                raise FileNotFoundError(
                    f"No .onnx model file found in {model_dir}"
                )
            model_path = candidates[0]

    if voices_override:
        voices_path = Path(voices_override)
    else:
        if not model_dir.exists():
            raise FileNotFoundError(f"Model directory does not exist: {model_dir}")
        preferred_voices = model_dir / "voices-v1.0.bin"
        if preferred_voices.is_file():
            voices_path = preferred_voices
        else:
            excluded_json = {"config.json", "manifest.json", "vocab.json"}
            candidates = (
                sorted(model_dir.glob("voices*.bin"))
                or sorted(model_dir.glob("voices*.json"))
                or sorted(model_dir.glob("*.bin"))
                or [
                    p
                    for p in sorted(model_dir.glob("*.json"))
                    if p.name.lower() not in excluded_json
                ]
            )
            if not candidates:
                raise FileNotFoundError(
                    f"No voices file (voices*.bin / voices*.json) found in {model_dir}"
                )
            voices_path = candidates[0]

    if not model_path.is_file():
        raise FileNotFoundError(f"ONNX model file not found: {model_path}")
    if not voices_path.is_file():
        raise FileNotFoundError(f"Voices file not found: {voices_path}")

    return model_path, voices_path


# ---------------------------------------------------------------------------
# Audio writing & synthesis
# ---------------------------------------------------------------------------

def _write_wav(wav_path: Path, samples: Any, sample_rate: int) -> None:
    """Write float32 mono samples to a 16-bit PCM WAV file."""
    try:
        import soundfile as sf  # type: ignore[import-not-found]

        sf.write(str(wav_path), samples, sample_rate, subtype="PCM_16")
        return
    except ImportError:
        pass

    import numpy as np  # type: ignore[import-not-found]

    clipped = np.clip(samples, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm16.tobytes())


def load_script(script_path: Path) -> dict[str, Any]:
    """Load and validate ``script.json``."""
    with script_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict) or not isinstance(data.get("lines"), list):
        raise ValueError(
            f"Invalid script schema in {script_path}: expected JSON object with 'lines' list."
        )

    for idx, line in enumerate(data["lines"]):
        if not isinstance(line, dict) or "id" not in line or "text" not in line:
            raise ValueError(
                f"Invalid line at index {idx} in {script_path}: expected 'id' and 'text'."
            )
    return data


def narrate(
    script_path: Path,
    out_dir: Path,
    model_dir: Path,
    voice: str | None = None,
    speed: float | None = None,
    lang: str = DEFAULT_LANG,
    model_override: str | None = None,
    voices_override: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Generate narration WAVs and ``manifest.json`` from ``script_path``."""
    script_data = load_script(script_path)

    effective_voice = voice if voice is not None else str(
        script_data.get("voice", DEFAULT_VOICE)
    )
    effective_speed = (
        float(speed)
        if speed is not None
        else float(script_data.get("speed", DEFAULT_SPEED))
    )
    lines: list[dict[str, Any]] = script_data["lines"]

    if dry_run:
        clips: list[dict[str, Any]] = []
        for line in lines:
            line_id = str(line["id"])
            original_text = str(line["text"])
            spoken_text = apply_pronunciation_rules(original_text)
            line_voice = str(line.get("voice") or effective_voice)
            line_speed = (
                float(line["speed"])
                if line.get("speed") is not None
                else effective_speed
            )
            print(f"[dry-run] {line_id} (voice={line_voice}, speed={line_speed}):")
            print(f"  original: {original_text}")
            print(f"  spoken:   {spoken_text}")
            clips.append({
                "id": line_id,
                "wav": str(out_dir / f"{line_id}.wav"),
                "duration_sec": 0.0,
                "sample_rate": 0,
                "voice": line_voice,
                "speed": line_speed,
                "original_text": original_text,
                "spoken_text": spoken_text,
            })
        return {
            "voice": effective_voice,
            "speed": effective_speed,
            "dry_run": True,
            "clips": clips,
        }

    model_path, voices_path = discover_model_files(
        model_dir=model_dir,
        model_override=model_override,
        voices_override=voices_override,
    )

    from kokoro_onnx import Kokoro  # type: ignore[import-not-found]

    out_dir.mkdir(parents=True, exist_ok=True)
    kokoro = Kokoro(str(model_path), str(voices_path))

    clips = []
    for line in lines:
        line_id = str(line["id"])
        original_text = str(line["text"])
        spoken_text = apply_pronunciation_rules(original_text)
        line_voice = str(line.get("voice") or effective_voice)
        line_speed = (
            float(line["speed"])
            if line.get("speed") is not None
            else effective_speed
        )
        line_lang = str(line.get("lang") or lang)

        samples, sample_rate = kokoro.create(
            spoken_text,
            voice=line_voice,
            speed=line_speed,
            lang=line_lang,
        )
        wav_path = out_dir / f"{line_id}.wav"
        _write_wav(wav_path, samples, int(sample_rate))

        duration_sec = round(len(samples) / float(sample_rate), 4)
        clip_entry = {
            "id": line_id,
            "wav": str(wav_path),
            "duration_sec": duration_sec,
            "sample_rate": int(sample_rate),
            "voice": line_voice,
            "speed": line_speed,
            "original_text": original_text,
            "spoken_text": spoken_text,
        }
        clips.append(clip_entry)
        print(
            f"[tts] {line_id} -> {wav_path} "
            f"({duration_sec:.2f}s, {sample_rate}Hz, voice={line_voice})"
        )

    manifest = {
        "voice": effective_voice,
        "speed": effective_speed,
        "model": str(model_path),
        "voices": str(voices_path),
        "clips": clips,
    }
    manifest_path = out_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"[tts] Wrote manifest: {manifest_path} ({len(clips)} clips)")
    return manifest


# ---------------------------------------------------------------------------
# Self-test suite
# ---------------------------------------------------------------------------

def run_self_test() -> int:
    """Run built-in unit tests for pronunciation rules and model discovery."""
    cases: list[tuple[str, str]] = [
        # IP rules
        ("Check the IP address now.", "Check the eye pee address now."),
        ("Inspect all device IPs in the table.", "Inspect all device eye pees in the table."),
        ("Supports IPv4 and IPv6 routing.", "Supports eye pee vee four and eye pee vee six routing."),
        ("IP-based checks and IP/port pairs.", "eye pee-based checks and eye pee/port pairs."),
        ("Do not touch ship, tip, tips, script, or pipeline.", "Do not touch ship, tip, tips, script, or pipeline."),
        # Present-tense / infinitive / imperative "read" -> "reed"
        ("We read the status table.", "We reed the status table."),
        ("Click to read the health results.", "Click to reed the health results."),
        ("You can read each device IP.", "You can reed each device eye pee."),
        ("We will read the output next.", "We will reed the output next."),
        ("Let's read the health check summary.", "Let's reed the health check summary."),
        ("Read the device table carefully.", "Reed the device table carefully."),
        ("Now read the latency column.", "Now reed the latency column."),
        ("Does he read the logs?", "Does he reed the logs?"),
        ("Mount the volume read-only.", "Mount the volume reed-only."),
        # Past-tense / participle "read" -> stay "read"
        ("The status was read from the API.", "The status was read from the API."),
        ("All entries were read cleanly.", "All entries were read cleanly."),
        ("The service has read the config.", "The service has read the config."),
        ("We have read the logs.", "We have read the logs."),
        ("They had read the report.", "They had read the report."),
        ("The table has been read.", "The table has been read."),
        ("We already read that alert.", "We already read that alert."),
        ("I just read the summary.", "I just read the summary."),
        ("As previously read from disk.", "As previously read from disk."),
        ("This value can be read safely.", "This value can be read safely."),
        ("He read the report.", "He read the report."),
        ("She is well-read on networking.", "She is well-read on networking."),
        # Unrelated words containing "read"
        (
            "System is ready for reading by any reader without spread or thread issues.",
            "System is ready for reading by any reader without spread or thread issues.",
        ),
    ]

    failures = 0
    for src, expected in cases:
        actual = apply_pronunciation_rules(src)
        if actual != expected:
            failures += 1
            print(f"FAIL: {src!r}\n  expected: {expected!r}\n  actual:   {actual!r}")

    # Test model discovery in a temporary directory
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "kokoro-v1.0.onnx").write_bytes(b"")
        (tmp_path / "voices-v1.0.bin").write_bytes(b"")
        m, v = discover_model_files(tmp_path)
        if m.name != "kokoro-v1.0.onnx" or v.name != "voices-v1.0.bin":
            failures += 1
            print(f"FAIL: model discovery got {(m, v)}")

    if failures:
        print(f"Self-test FAILED ({failures} failures).")
        return 1
    print(f"Self-test PASSED ({len(cases)} pronunciation cases + model discovery).")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate WAV narration clips from script.json using Kokoro ONNX "
            "with English pronunciation rules."
        )
    )
    parser.add_argument(
        "--script",
        default=DEFAULT_SCRIPT,
        help=f"Path to input script.json (default: {DEFAULT_SCRIPT})",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory for WAV files and manifest.json (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--model-dir",
        default=DEFAULT_MODEL_DIR,
        help=f"Directory containing Kokoro .onnx and voices files (default: {DEFAULT_MODEL_DIR})",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional explicit path to the Kokoro .onnx model file",
    )
    parser.add_argument(
        "--voices",
        default=None,
        help="Optional explicit path to the Kokoro voices file (.bin or .json)",
    )
    parser.add_argument(
        "--voice",
        default=None,
        help=(
            f"Voice name (default: {DEFAULT_VOICE}; falls back to top-level "
            "script.json 'voice' when omitted, and per-line 'voice' overrides)"
        ),
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=None,
        help=(
            f"Speech speed multiplier (default: {DEFAULT_SPEED}; falls back to "
            "top-level script.json 'speed' when omitted, and per-line 'speed' overrides)"
        ),
    )
    parser.add_argument(
        "--lang",
        default=DEFAULT_LANG,
        help=f"Phonemizer language code (default: {DEFAULT_LANG})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apply pronunciation rules and print transformed lines without loading the ONNX model",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in pronunciation rules and model-discovery tests and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    narrate(
        script_path=Path(args.script),
        out_dir=Path(args.out_dir),
        model_dir=Path(args.model_dir),
        voice=args.voice,
        speed=args.speed,
        lang=args.lang,
        model_override=args.model,
        voices_override=args.voices,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
