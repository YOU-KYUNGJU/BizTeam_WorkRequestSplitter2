# BizTeam_WorkRequestSplitter2

PDF 1페이지를 OCR로 판별한 뒤, 첫 페이지를 제거하고 코드 기반 파일명으로 저장하는 도구입니다.

## 설치

```powershell
python -m pip install -r requirements.txt
```

추가로 Tesseract OCR이 설치되어 있어야 하며 기본 경로는 `C:\Program Files\Tesseract-OCR\tesseract.exe` 입니다.

## 실행

`main.py`
- 1페이지 하단의 `S/Z`, `S/N` 표식을 기준으로 판별

`main2.py`
- 1페이지 우측 상단의 `작업요청서` 문구를 기준으로 판별

인자 없이 실행하면 스크립트와 같은 폴더의 PDF를 모두 처리합니다.

```powershell
python src/main.py
python src/main2.py
```

특정 파일이나 폴더를 지정할 수도 있습니다.

```powershell
python src/main.py "C:\work\test.pdf"
python src/main.py "C:\work"
python src/main2.py "C:\work\test.pdf"
python src/main2.py "C:\work"
```

처리 결과는 원본 PDF와 같은 폴더의 `processed` 폴더에 저장됩니다.
