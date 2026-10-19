"""Audio event detection: what kind of sound is happening, not just how loud.

Runs an AudioSet classifier (AST) over 1 s windows and keeps the labels that
matter for picking moments: the commentator laughing, screaming or gasping,
and big game sounds. Much better than loudness alone, which can't tell a
laugh from a shout from a loud mining loop.

  uv run python -m mce.events <audio.wav> [--labels laugh,scream]
"""
import argparse
import json
import wave

import numpy as np

MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"
SR = 16000

# Our event name -> AudioSet labels that count as it.
GROUPS = {
    "laugh": ["Laughter", "Giggle", "Chuckle, chortle", "Belly laugh", "Snicker", "Baby laughter"],
    "scream": ["Screaming", "Shout", "Yell", "Children shouting", "Battle cry"],
    "gasp": ["Gasp", "Groan", "Grunt"],
    "explosion": ["Explosion", "Boom", "Burst, pop", "Eruption"],
    "music": ["Music"],
}
THRESH = {"laugh": 0.25, "scream": 0.3, "gasp": 0.55, "explosion": 0.3, "music": 0.5}


def _load(path: str) -> np.ndarray:
    import subprocess

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def detect(path: str, win: float = 1.0, hop: float = 0.5, groups: list[str] | None = None,
           batch: int = 32) -> list[dict]:
    import torch
    from transformers import ASTFeatureExtractor, ASTForAudioClassification

    groups = groups or list(GROUPS)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    fe = ASTFeatureExtractor.from_pretrained(MODEL)
    model = ASTForAudioClassification.from_pretrained(MODEL).to(device).eval()
    label_ids = {g: [model.config.label2id[l] for l in GROUPS[g] if l in model.config.label2id] for g in groups}

    x = _load(path)
    w, h = int(win * SR), int(hop * SR)
    starts = list(range(0, max(1, len(x) - w + 1), h))
    scores = {g: np.zeros(len(starts)) for g in groups}
    for b in range(0, len(starts), batch):
        chunk = [x[s:s + w] for s in starts[b:b + batch]]
        feats = fe(chunk, sampling_rate=SR, return_tensors="pt")["input_values"].to(device)
        with torch.no_grad():
            probs = torch.sigmoid(model(feats).logits).cpu().numpy()
        for g, ids in label_ids.items():
            scores[g][b:b + len(chunk)] = probs[:, ids].max(axis=1)

    events = []
    for g in groups:
        on = scores[g] >= THRESH[g]
        i = 0
        while i < len(on):
            if on[i]:
                j = i
                while j + 1 < len(on) and on[j + 1]:
                    j += 1
                peak = i + int(np.argmax(scores[g][i:j + 1]))
                events.append({"kind": g, "start": round(starts[i] / SR, 2), "end": round((starts[j] + w) / SR, 2),
                               "t": round(starts[peak] / SR + win / 2, 2), "score": round(float(scores[g][peak]), 2)})
                i = j + 1
            else:
                i += 1
    return sorted(events, key=lambda e: e["t"])


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.events")
    ap.add_argument("audio")
    ap.add_argument("--labels")
    a = ap.parse_args()
    ev = detect(a.audio, groups=a.labels.split(",") if a.labels else None)
    print(json.dumps(ev, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
