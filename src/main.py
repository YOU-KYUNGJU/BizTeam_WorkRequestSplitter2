import os
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageOps, ImageFilter

# =========================
# 환경설정
# =========================

# 필요하면 본인 PC 경로로 수정
# 예: r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# 저장 폴더
OUTPUT_DIR_NAME = "processed"

# OCR 확대 배율
RENDER_SCALE = 3.0

# S/Z 검출 시 허용할 기울기 각도 후보
SKEW_ANGLE_CANDIDATES = (0, -4, 4, -8, 8)

# 정규식: N232-26-03706 같은 형식
CODE_PATTERN = re.compile(r"\b([A-Z]\d{3}-\d{2}-\d{5})\b")
MARKER_PATTERN = re.compile(r"S/?[ZN]")

# pytesseract 경로 적용
pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE


# =========================
# 이미지 전처리
# =========================
def preprocess_for_ocr(img: Image.Image) -> Image.Image:
    """OCR 인식률 향상을 위한 전처리"""
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.SHARPEN)

    # 흑백 임계처리
    bw = gray.point(lambda x: 0 if x < 180 else 255, mode="1")
    return bw.convert("L")


def rotate_for_ocr(img: Image.Image, angle: float) -> Image.Image:
    """기울어진 스캔을 보정하기 위해 소각도 회전"""
    if angle == 0:
        return img

    resampling = Image.Resampling.BICUBIC if hasattr(Image, "Resampling") else Image.BICUBIC
    fillcolor = 255 if img.mode in {"1", "L"} else (255, 255, 255)
    return img.rotate(angle, resample=resampling, expand=True, fillcolor=fillcolor)


def normalize_marker_text(text: str) -> str:
    """S/Z, S/N 검출에 필요한 문자만 남기고 흔한 OCR 오인식을 보정"""
    normalized = (
        text.upper()
        .replace("\\", "/")
        .replace("5", "S")
        .replace("2", "Z")
    )
    return re.sub(r"[^A-Z/]", "", normalized)


def try_marker_ocr(
    base_img: Image.Image,
    *,
    label: str,
    config: str,
    angles: tuple[int, ...] = SKEW_ANGLE_CANDIDATES,
    use_preprocess: bool,
) -> tuple[bool, str]:
    """여러 각도/설정으로 S/Z, S/N OCR을 재시도"""
    best_text = ""

    for angle in angles:
        candidate = rotate_for_ocr(base_img, angle)
        if use_preprocess:
            candidate = preprocess_for_ocr(candidate)

        text = ocr_text(candidate, config)
        if text and not best_text:
            best_text = f"[{label} angle={angle}] {text}"

        if MARKER_PATTERN.search(normalize_marker_text(text)):
            return True, f"[{label} angle={angle}] {text}"

    return False, best_text


def render_crop_from_page(page: fitz.Page, rect_ratio: tuple[float, float, float, float], scale: float = RENDER_SCALE) -> Image.Image:
    """
    PDF 페이지의 특정 비율 영역을 렌더링해서 PIL Image로 반환
    rect_ratio = (x0_ratio, y0_ratio, x1_ratio, y1_ratio)
    """
    page_rect = page.rect
    x0 = page_rect.width * rect_ratio[0]
    y0 = page_rect.height * rect_ratio[1]
    x1 = page_rect.width * rect_ratio[2]
    y1 = page_rect.height * rect_ratio[3]

    clip = fitz.Rect(x0, y0, x1, y1)
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)

    mode = "RGB" if pix.n < 4 else "RGBA"
    img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    return img


# =========================
# OCR 함수
# =========================
def ocr_text(img: Image.Image, config: str) -> str:
    return pytesseract.image_to_string(img, config=config).strip()


def detect_sz_on_first_page(page: fitz.Page) -> tuple[bool, str]:
    """
    1페이지 하단 영역에서 S/Z 또는 S/N 확인
    """
    # 위치가 조금씩 바뀌는 경우를 고려해 하단 우측 중심에서 하단 절반까지 점진적으로 확대
    region_specs = (
        ("focused-left", (0.38, 0.80, 0.62, 0.96), 4.5),
        ("right-bottom", (0.45, 0.78, 0.98, 0.995), 3.5),
        ("bottom-half", (0.28, 0.74, 0.98, 0.995), 3.0),
    )

    attempts: list[tuple[str, Image.Image, bool, str]] = []
    for region_label, region, scale in region_specs:
        img = render_crop_from_page(page, region, scale=scale)
        attempts.extend(
            (
                (
                    f"{region_label}-bw-psm11",
                    img,
                    True,
                    r'--oem 3 --psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz/\\',
                ),
                (
                    f"{region_label}-raw-psm7",
                    img,
                    False,
                    r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz/\\',
                ),
                (
                    f"{region_label}-bw-psm7",
                    img,
                    True,
                    r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz/\\',
                ),
            )
        )

    best_text = ""
    for label, img, use_preprocess, config in attempts:
        found, text = try_marker_ocr(
            img,
            label=label,
            config=config,
            use_preprocess=use_preprocess,
        )
        if found:
            return True, text

        if text and not best_text:
            best_text = text

    return False, best_text


def extract_code_from_first_page(page: fitz.Page) -> tuple[str | None, str]:
    """
    1페이지 왼쪽 위에서 N232-26-03706 형식의 코드 추출
    """
    # 샘플 PDF 기준 왼쪽 위 코드 영역
    # 필요시 조금씩 조정
    code_region = (0.10, 0.06, 0.62, 0.21)

    img = render_crop_from_page(page, code_region)
    img = preprocess_for_ocr(img)

    text = ocr_text(
        img,
        r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'
    )

    # OCR 오인식 보정
    cleaned = (
        text.upper()
        .replace(" ", "")
        .replace("_", "-")
        .replace("—", "-")
        .replace("–", "-")
        .replace("O", "0")  # 숫자 0 오인식 대비
    )

    match = CODE_PATTERN.search(cleaned)
    if match:
        return match.group(1), text

    return None, text


# =========================
# 파일 처리
# =========================
def code_to_filename(code: str) -> str:
    """
    N232-26-03706 -> N2322603706
    """
    return code.replace("-", "")


def save_pdf_without_first_page(src_pdf: Path, output_pdf: Path) -> None:
    """
    첫 페이지를 제거한 새 PDF 저장
    """
    src_doc = fitz.open(src_pdf)
    try:
        if src_doc.page_count <= 1:
            raise ValueError("페이지가 1장뿐이라 첫 페이지 삭제 후 저장할 수 없습니다.")

        new_doc = fitz.open()
        try:
            new_doc.insert_pdf(src_doc, from_page=1, to_page=src_doc.page_count - 1)
            new_doc.save(output_pdf)
        finally:
            new_doc.close()
    finally:
        src_doc.close()


def process_pdf(pdf_path: str) -> None:
    pdf_file = Path(pdf_path)

    if not pdf_file.exists():
        print(f"파일 없음: {pdf_file}")
        return

    if pdf_file.suffix.lower() != ".pdf":
        print(f"PDF 아님: {pdf_file}")
        return

    output_dir = pdf_file.parent / OUTPUT_DIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_file)
    try:
        if doc.page_count < 2:
            print(f"[실패] 페이지 수 부족: {pdf_file.name}")
            return

        first_page = doc[0]

        # 1) 오른쪽 아래 S/Z 확인
        sz_found, sz_raw = detect_sz_on_first_page(first_page)
        print(f"[S/Z OCR] {pdf_file.name}: {repr(sz_raw)}")

        if not sz_found:
            print(f"[건너뜀] S/Z 미검출: {pdf_file.name}")
            return

        # 2) 왼쪽 위 코드 추출
        code, code_raw = extract_code_from_first_page(first_page)
        print(f"[CODE OCR] {pdf_file.name}: {repr(code_raw)}")

        if not code:
            print(f"[실패] 코드 추출 실패: {pdf_file.name}")
            return

        new_name = code_to_filename(code) + ".pdf"
        output_pdf = output_dir / new_name

        # 같은 이름 있으면 번호 붙이기
        if output_pdf.exists():
            stem = output_pdf.stem
            suffix = output_pdf.suffix
            idx = 2
            while True:
                candidate = output_dir / f"{stem}_{idx}{suffix}"
                if not candidate.exists():
                    output_pdf = candidate
                    break
                idx += 1

        # 3) 첫 페이지 삭제 후 저장
        save_pdf_without_first_page(pdf_file, output_pdf)

        print(f"[완료] {pdf_file.name} -> {output_pdf.name} / 추출코드: {code}")

    finally:
        doc.close()


def process_folder(folder_path: str) -> None:
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        print(f"폴더 없음: {folder}")
        return

    pdf_files = sorted(
        file_path
        for file_path in folder.iterdir()
        if file_path.is_file() and file_path.suffix.lower() == ".pdf"
    )
    if not pdf_files:
        print("PDF 파일이 없습니다.")
        return

    for pdf_file in pdf_files:
        print("-" * 60)
        process_pdf(str(pdf_file))


def get_runtime_folder() -> Path:
    """실행 중인 스크립트 또는 exe와 같은 폴더"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# =========================
# 실행부
# =========================
if __name__ == "__main__":
    """
    사용 예시
    1) 인자 없이 실행
       python src/main.py
       -> 실행 파일과 같은 폴더의 PDF 전체 처리

    2) 특정 폴더 전체 처리
       python src/main.py "C:\\work"

    3) 단일 파일 처리
       python src/main.py "C:\\work\\test.pdf"
    """
    if len(sys.argv) < 2:
        runtime_folder = get_runtime_folder()
        print(f"[기본 실행] 실행 파일 폴더의 PDF를 처리합니다: {runtime_folder}")
        process_folder(str(runtime_folder))
        sys.exit(0)

    target = Path(sys.argv[1])

    if target.is_file():
        process_pdf(str(target))
    elif target.is_dir():
        process_folder(str(target))
    else:
        print("올바른 파일 또는 폴더 경로를 입력하세요.")
