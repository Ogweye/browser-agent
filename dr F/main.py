from screen import capture
from ocr import read_text

image = capture()

text = read_text(image)

print(text)