"""Judge-style smoke tests for deterministic analyze pipeline."""
import asyncio
import base64
import io
from PIL import Image, ImageDraw, ImageFilter

import routes.analyze as analyze_route
from routes.analyze import AnalyzeRequest, analyze_medicine


class _DummyProvider:
    def generate_explanation(self, analysis, verdict):
        return f"Deterministic test explanation ({verdict})"


def to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def make_real_medicine_like() -> Image.Image:
    img = Image.new("RGB", (900, 500), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 880, 480], outline="black", width=3)
    d.text((40, 40), "PARACETAMOL TABLETS IP 500 MG", fill="black")
    d.text((40, 110), "BATCH NO: AB12C34", fill="black")
    d.text((40, 180), "EXP: 12/2028", fill="black")
    d.text((40, 250), "MFD BY: MEDLIFE PHARMA LTD", fill="black")
    d.text((40, 320), "DOSAGE: 1 TABLET TWICE DAILY", fill="black")
    return img


def make_random_object() -> Image.Image:
    img = Image.new("RGB", (900, 500), (30, 120, 200))
    d = ImageDraw.Draw(img)
    d.ellipse([180, 120, 360, 300], fill=(240, 80, 80))
    d.rectangle([500, 140, 760, 360], fill=(70, 220, 120))
    return img


def make_blurry_medicine() -> Image.Image:
    base = make_real_medicine_like()
    return base.filter(ImageFilter.GaussianBlur(radius=4.0))


async def run_case(name: str, img: Image.Image):
    req = AnalyzeRequest(image_base64=to_b64(img), mime_type="image/png")
    try:
        res = await analyze_medicine(req)
        print(f"{name}: verdict={res.get('verdict')} confidence={res.get('overall_confidence')} medicine={res.get('medicine_name')}")
    except Exception as exc:
        print(f"{name}: ERROR {exc}")


async def main():
    # Avoid live network calls during local judge-style smoke tests.
    analyze_route.get_provider_manager = lambda: _DummyProvider()

    await run_case("REAL_MEDICINE_LIKE", make_real_medicine_like())
    await run_case("RANDOM_OBJECT", make_random_object())
    await run_case("BLURRY_MEDICINE", make_blurry_medicine())


if __name__ == "__main__":
    asyncio.run(main())
