import re
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

try:
    from main import (
        OUTPUT_DIR_NAME,
        SKEW_ANGLE_CANDIDATES,
        TESSERACT_EXE,
        code_to_filename,
        extract_code_from_first_page,
        get_runtime_folder,
        preprocess_for_ocr,
        render_crop_from_page,
        rotate_for_ocr,
        save_pdf_without_first_page,
    )
except ModuleNotFoundError:
    from src.main import (
        OUTPUT_DIR_NAME,
        SKEW_ANGLE_CANDIDATES,
        TESSERACT_EXE,
        code_to_filename,
        extract_code_from_first_page,
        get_runtime_folder,
        preprocess_for_ocr,
        render_crop_from_page,
        rotate_for_ocr,
        save_pdf_without_first_page,
    )

# 상단 우측 표제: 작업요청서
REQUEST_TITLE = "작업요청서"

# pytesseract 경로 적용
pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE


def ocr_korean_text(img: Image.Image, config: str) -> str:
    """한글 제목 검출용 OCR"""
    return pytesseract.image_to_string(img, config=config, lang="kor+eng").strip()


def normalize_request_title_text(text: str) -> str:
    """작업요청서 판정을 위해 공백/기호를 제거"""
    normalized = text.replace(" ", "").replace("\n", "")
    return re.sub(r"[^가-힣A-Za-z0-9]", "", normalized)


def try_request_title_ocr(
    base_img: Image.Image,
    *,
    label: str,
    config: str,
    angles: tuple[int, ...] = SKEW_ANGLE_CANDIDATES,
    use_preprocess: bool,
) -> tuple[bool, str]:
    """여러 각도/설정으로 작업요청서 OCR을 재시도"""
    best_text = ""

    for angle in angles:
        candidate = rotate_for_ocr(base_img, angle)
        if use_preprocess:
            candidate = preprocess_for_ocr(candidate)

        text = ocr_korean_text(candidate, config)
        if text and not best_text:
            best_text = f"[{label} angle={angle}] {text}"

        if REQUEST_TITLE in normalize_request_title_text(text):
            return True, f"[{label} angle={angle}] {text}"

    return False, best_text


def detect_request_title_on_first_page(page: fitz.Page) -> tuple[bool, str]:
    """
    1페이지 상단 우측에서 작업요청서 확인
    """
    # 상단 우측 제목 위치가 조금씩 변할 수 있어 여러 범위를 시도
    region_specs = (
        ("title-tight", (0.55, 0.03, 0.98, 0.17), 4.0),
        ("title-wide", (0.46, 0.02, 0.99, 0.20), 3.5),
        ("top-right-band", (0.40, 0.01, 0.99, 0.22), 3.0),
    )

    attempts: list[tuple[str, Image.Image, bool, str]] = []
    for region_label, region, scale in region_specs:
        img = render_crop_from_page(page, region, scale=scale)
        attempts.extend(
            (
                (f"{region_label}-raw-psm7", img, False, r"--oem 3 --psm 7"),
                (f"{region_label}-bw-psm7", img, True, r"--oem 3 --psm 7"),
                (f"{region_label}-raw-psm11", img, False, r"--oem 3 --psm 11"),
                (f"{region_label}-bw-psm11", img, True, r"--oem 3 --psm 11"),
                (f"{region_label}-bw-psm6", img, True, r"--oem 3 --psm 6"),
            )
        )

    best_text = ""
    for label, img, use_preprocess, config in attempts:
        found, text = try_request_title_ocr(
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

        # 1) 우측 위 작업요청서 확인
        title_found, title_raw = detect_request_title_on_first_page(first_page)
        print(f"[TITLE OCR] {pdf_file.name}: {repr(title_raw)}")

        if not title_found:
            print(f"[건너뜀] 작업요청서 미검출: {pdf_file.name}")
            return

        # 2) 왼쪽 위 코드 추출
        code, code_raw = extract_code_from_first_page(first_page)
        print(f"[CODE OCR] {pdf_file.name}: {repr(code_raw)}")

        if not code:
            print(f"[실패] 코드 추출 실패: {pdf_file.name}")
            return

        new_name = code_to_filename(code) + ".pdf"
        output_pdf = output_dir / new_name

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


if __name__ == "__main__":
    """
    사용 예시
    1) 인자 없이 실행
       python src/main2.py
       -> 실행 파일과 같은 폴더의 PDF 전체 처리

    2) 특정 폴더 전체 처리
       python src/main2.py "C:\\work"

    3) 단일 파일 처리
       python src/main2.py "C:\\work\\test.pdf"
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
