"""Subject cutout (SAM 2 video): the person/object alone on a transparent background, tracked through a shot.

Main use — text BEHIND the subject: V1 = the shot, V2 = the text graphic (Remotion BigText…),
V3 = this cutout at the same time/position → the subject stands in front of the words.
Also: blur/darken/replace the background behind a facecam, a glow/outline around the subject,
the subject popping out of a frame.

  uv run python -m mce.matte <video> --start S --end E [-o out.mov]
         [--point x,y ...] [--neg x,y ...] [--box x0,y0,x1,y1] [--model small|tiny|base|large] [--mask]

Prompt (source pixels): nothing → the main person (RT-DETR person detector: biggest, most central);
--point on the subject (several = more robust), --neg on things to exclude, --box around it.
For a game character / object, look at a frame of the first second and give a point or a box.
Output: ProRes 4444 with alpha at the source size and frame rate (--mask: a black/white matte .mp4 instead,
for Premiere's Track Matte Key). Keep shots short (a few seconds) — ~3-6 frames/s on Apple Silicon.
"""
import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

MODELS = {s: f"facebook/sam2.1-hiera-{s}" for s in ("tiny", "small", "base-plus", "large")}
MODELS["base"] = MODELS["base-plus"]


def _info(src: str) -> tuple[int, int, str]:
    s = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height,avg_frame_rate:stream_side_data=rotation", "-of", "json", src],
                                  capture_output=True, text=True, check=True).stdout)["streams"][0]
    w, h = s["width"], s["height"]
    rot = next((abs(int(d.get("rotation", 0))) for d in s.get("side_data_list", [])), 0)
    return (h, w, s["avg_frame_rate"]) if rot in (90, 270) else (w, h, s["avg_frame_rate"])


def _frames(src: str, start: float, end: float, w: int, h: int):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(start), "-i", src, "-t", str(end - start),
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n = w * h * 3
    while (buf := p.stdout.read(n)) and len(buf) == n:
        yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    p.wait()


PERSON_DETECTOR = "PekingU/rtdetr_v2_r18vd"


def auto_box(img: np.ndarray) -> list[int]:
    """Box around the main person (biggest, nearest the centre) — RT-DETR, COCO "person"."""
    import torch
    from transformers import AutoImageProcessor, AutoModelForObjectDetection

    proc = AutoImageProcessor.from_pretrained(PERSON_DETECTOR)
    net = AutoModelForObjectDetection.from_pretrained(PERSON_DETECTOR).eval()
    with torch.no_grad():
        out = net(**proc(images=img, return_tensors="pt"))
    det = proc.post_process_object_detection(out, threshold=0.5, target_sizes=[img.shape[:2]])[0]
    h, w = img.shape[:2]
    people = [b.tolist() for b, l in zip(det["boxes"], det["labels"]) if net.config.id2label[int(l)] == "person"]
    if not people:
        raise SystemExit("matte: no person in the first frame — pass --point x,y or --box on the subject")

    def score(b):
        area = (b[2] - b[0]) * (b[3] - b[1]) / (w * h)
        off = abs((b[0] + b[2]) / 2 - w / 2) / w
        return area - off
    return [int(v) for v in max(people, key=score)]


def _fix_mps() -> None:
    """Three torch-MPS bugs hit SAM 2 — max_pool2d, scaled_dot_product_attention and non_blocking
    CPU→MPS copies all return garbage for non-contiguous tensors (the mask lands on the wrong object).
    Same math with contiguous tensors / blocking copies."""
    import torch
    import transformers.models.sam2.modeling_sam2 as ms
    from transformers.modeling_utils import ALL_ATTENTION_FUNCTIONS

    def do_pool(x, query_stride=None):
        if query_stride is None:
            return x
        x = x.contiguous().permute(0, 3, 1, 2)
        x = torch.nn.functional.max_pool2d(x, kernel_size=query_stride, stride=query_stride, ceil_mode=False)
        return x.permute(0, 2, 3, 1)
    ms.do_pool = do_pool

    sdpa = ALL_ATTENTION_FUNCTIONS["sdpa"]
    if not getattr(sdpa, "_contig", False):
        def contiguous_sdpa(module, q, k, v, *a, **kw):
            return sdpa(module, q.contiguous(), k.contiguous(), v.contiguous(), *a, **kw)
        contiguous_sdpa._contig = True
        ALL_ATTENTION_FUNCTIONS["sdpa"] = contiguous_sdpa

    to = torch.Tensor.to
    if not getattr(to, "_contig", False):
        def safe_to(self, *a, **kw):
            if kw.pop("non_blocking", False) and not self.is_contiguous():
                return to(self.contiguous(), *a, **kw)
            return to(self, *a, **kw)
        safe_to._contig = True
        torch.Tensor.to = safe_to


def matte(src: str, start: float, end: float, out: str, points=None, neg=None, box=None,
          model: str = "small", mask_only: bool = False) -> str:
    import torch
    from transformers import Sam2VideoModel, Sam2VideoProcessor

    w, h, fps = _info(src)
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    if device == "mps":
        _fix_mps()
    name = MODELS[model]
    proc = Sam2VideoProcessor.from_pretrained(name)
    net = Sam2VideoModel.from_pretrained(name).to(device).eval()
    session = proc.init_video_session(inference_device=device, video_storage_device="cpu", dtype=torch.float32)

    enc = (["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16"] if mask_only else
           ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-alpha_bits", "16"])
    writer = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gray" if mask_only else "rgba",
                               "-s", f"{w}x{h}", "-r", fps, "-i", "-", *enc, out], stdin=subprocess.PIPE)
    try:
        for i, img in enumerate(_frames(src, start, end, w, h)):
            inputs = proc(images=img, device=device, return_tensors="pt")
            if i == 0:
                pos = points or []
                if not points and not box:
                    box = auto_box(img)
                    print(f"matte: subject box {box}")
                pts = [list(p) for p in pos] + [list(p) for p in (neg or [])]
                kw = {}
                if pts:
                    kw.update(input_points=[[pts]], input_labels=[[[1] * len(pos) + [0] * len(neg or [])]])
                if box:
                    kw["input_boxes"] = [[list(box)]]
                proc.add_inputs_to_inference_session(session, frame_idx=0, obj_ids=1,
                                                     original_size=inputs.original_sizes[0], **kw)
            with torch.no_grad():
                res = net(inference_session=session, frame=inputs.pixel_values[0])
            logits = proc.post_process_masks([res.pred_masks], original_sizes=inputs.original_sizes,
                                             binarize=False)[0][0, 0]
            alpha = torch.sigmoid(logits.float()).cpu().numpy()
            alpha = cv2.GaussianBlur(alpha, (0, 0), 1.2)  # soft, non-jagged edge
            a8 = (np.clip((alpha - 0.15) / 0.7, 0, 1) * 255).astype(np.uint8)
            writer.stdin.write(a8.tobytes() if mask_only else np.dstack([img, a8]).tobytes())
    finally:
        writer.stdin.close()
        writer.wait()
    return out


def _pt(s: str) -> tuple[int, int]:
    x, y = s.split(",")
    return int(float(x)), int(float(y))


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.matte")
    ap.add_argument("video")
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("-o", "--out")
    ap.add_argument("--point", action="append", type=_pt, help="x,y on the subject (repeatable)")
    ap.add_argument("--neg", action="append", type=_pt, help="x,y NOT the subject (repeatable)")
    ap.add_argument("--box", help="x0,y0,x1,y1 around the subject")
    ap.add_argument("--model", choices=list(MODELS), default="small")
    ap.add_argument("--mask", action="store_true", help="write a black/white matte instead of a cutout")
    a = ap.parse_args()
    stem = Path(a.video).with_suffix("").as_posix() + f"_matte_{a.start:g}-{a.end:g}"
    out = a.out or stem + (".mp4" if a.mask else ".mov")
    box = [int(float(v)) for v in a.box.split(",")] if a.box else None
    print(matte(a.video, a.start, a.end, out, a.point, a.neg, box, a.model, a.mask))


if __name__ == "__main__":
    main()
