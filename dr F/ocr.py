from paddleocr import PaddleOCR

ocr = PaddleOCR(use_angle_cls=True, lang="en")

def read_text(image_path):
    result = ocr.ocr(image_path)

    text = []

    for page in result:
        for line in page:
            text.append(line[1][0])

    return "\n".join(text)