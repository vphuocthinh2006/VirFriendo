"""ViT encoder from best_vit_model.pth — timm vit_base_patch16 @ 448."""

from __future__ import annotations

import threading

import torch
import torch.nn as nn
from loguru import logger

from services.core.config import settings


class _ViTClassifierWrapper(nn.Module):
    """Notebook wrapper: submodule named timm_model (state dict prefix timm_model.)."""

    def __init__(self, timm_core: nn.Module):
        super().__init__()
        self.timm_model = timm_core

    def embedding_prelogits(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.timm_model.forward_features(x)
        return self.timm_model.forward_head(feat, pre_logits=True)


_vit_holder: dict[str, _ViTClassifierWrapper | None] = {"m": None}
_vit_lock = threading.Lock()


def _device() -> torch.device:
    d = (getattr(settings, "ML_DEVICE", "cpu") or "cpu").strip().lower()
    if d in ("cuda", "gpu", "auto") and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def get_vit_encoder() -> _ViTClassifierWrapper | None:
    if not getattr(settings, "ENABLE_VIT_GALLERY", False):
        return None
    path = (getattr(settings, "VIT_MODEL_PATH", "") or "").strip()
    if not path:
        return None
    with _vit_lock:
        if _vit_holder["m"] is not None:
            return _vit_holder["m"]
        try:
            import timm

            name = getattr(settings, "VIT_TIMM_MODEL", "vit_base_patch16_224").strip()
            ncls = int(getattr(settings, "VIT_NUM_CLASSES", 45))
            core = timm.create_model(name, pretrained=False, num_classes=ncls, img_size=448)
            wrap = _ViTClassifierWrapper(core)
            try:
                ckpt = torch.load(path, map_location=_device(), weights_only=False)
            except TypeError:
                ckpt = torch.load(path, map_location=_device())
            sd = ckpt if isinstance(ckpt, dict) else ckpt
            missing, unexpected = wrap.load_state_dict(sd, strict=False)
            if missing:
                logger.warning("ViT partial load missing keys (first 5): {}", missing[:5])
            if unexpected:
                logger.warning("ViT unexpected keys (first 5): {}", unexpected[:5])
            wrap.to(_device())
            wrap.eval()
            _vit_holder["m"] = wrap
            logger.info("ViT gallery encoder loaded from {}", path)
            return wrap
        except Exception as e:
            logger.exception("ViT encoder load failed: {}", e)
            return None


@torch.inference_mode()
def encode_image_pil_normalized(
    pil_image,
    *,
    device: torch.device | None = None,
) -> torch.Tensor | None:
    """RGB PIL image → L2-normalized embedding (1, dim) float32."""
    model = get_vit_encoder()
    if model is None:
        return None
    dev = device or _device()
    from torchvision import transforms

    t = transforms.Compose(
        [
            transforms.Resize((448, 448)),
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
    )(pil_image.convert("RGB")).unsqueeze(0).to(dev)
    model_dev = model
    vec = model_dev.embedding_prelogits(t)[0].float()
    vec = vec / vec.norm(dim=-1, keepdim=True).clamp_min(1e-8)
    return vec.unsqueeze(0).cpu()


def preprocess_imagenet(pil_image) -> torch.Tensor:
    """Alternate normalize (fallback if embeddings were computed with HF processor)."""

    model = get_vit_encoder()
    if model is None:
        raise RuntimeError("ViT unavailable")
    from torchvision import transforms

    t = transforms.Compose(
        [
            transforms.Resize((448, 448)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=(0.485, 0.456, 0.406),
                std=(0.229, 0.224, 0.225),
            ),
        ]
    )(pil_image.convert("RGB")).unsqueeze(0).to(_device())
    return t

