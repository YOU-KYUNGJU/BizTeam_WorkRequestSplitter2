# BizTeam_WorkRequestSplitter2

PDF 1페이지를 OCR로 판별한 뒤, 첫 페이지를 제거하고 코드 기반 파일명으로 다시 저장하는 도구입니다.

## 주요 기능

- `main.py`
  - 1페이지 하단의 `S/Z`, `S/N` 표식을 기준으로 대상 PDF를 판별합니다.
  - 기울어진 스캔을 고려해 여러 각도와 여러 OCR 설정으로 재시도합니다.
- `main2.py`
  - 1페이지 우측 상단의 `작업요청서` 문구를 기준으로 대상 PDF를 판별합니다.
  - 한국어 OCR(`kor+eng`)을 사용해 여러 범위와 각도로 재시도합니다.
- 공통 동작
  - 1페이지 좌측 상단에서 코드 형식 `N232-26-03706`을 OCR로 추출합니다.
  - 추출한 코드를 `N2322603706.pdf` 형태의 파일명으로 변환합니다.
  - 원본 PDF의 첫 페이지를 제거한 새 PDF를 `processed` 폴더에 저장합니다.
  - 같은 이름이 이미 있으면 `_2`, `_3`처럼 번호를 붙여 저장합니다.

## 요구 사항

- Windows
- Python 3.14 이상 권장
- Tesseract OCR 설치
  - 기본 경로: `C:\Program Files\Tesseract-OCR\tesseract.exe`
  - 한국어 OCR용 `kor` 학습 데이터 필요

## Python 환경 설치

```powershell
python -m pip install -r requirements.txt
```

## 소스 실행 방법

인자를 주지 않으면 실행 중인 스크립트와 같은 폴더의 PDF를 모두 처리합니다.

```powershell
python src/main.py
python src/main2.py
```

특정 파일 또는 폴더를 직접 지정할 수도 있습니다.

```powershell
python src/main.py "C:\work\test.pdf"
python src/main.py "C:\work"

python src/main2.py "C:\work\test.pdf"
python src/main2.py "C:\work"
```

## exe 파일

PyInstaller로 아래 두 실행 파일을 만들 수 있습니다.

- `dist\BizTeam_WorkRequestSplitter2_SN.exe`
- `dist\BizTeam_WorkRequestSplitter2_작업요청서.exe`

빌드 스크립트:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

실행 예시:

```powershell
.\dist\BizTeam_WorkRequestSplitter2_SN.exe
.\dist\BizTeam_WorkRequestSplitter2_작업요청서.exe

.\dist\BizTeam_WorkRequestSplitter2_SN.exe "C:\work\test.pdf"
.\dist\BizTeam_WorkRequestSplitter2_작업요청서.exe "C:\work\test.pdf"
```

## 출력 규칙

- 출력 폴더: 원본 PDF와 같은 폴더의 `processed`
- 출력 파일명: OCR로 추출한 코드에서 `-`를 제거한 이름
- 예시: `N232-26-03706` -> `N2322603706.pdf`

## 프로젝트 파일

- `src/main.py`
- `src/main2.py`
- `build_exe.ps1`
- `requirements.txt`
