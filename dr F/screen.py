from mss import mss

sct = mss()

monitor = sct.monitors[1]

def capture():

    filename = "capture.png"

    sct.shot(output=filename)

    return filename