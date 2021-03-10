import time
import RPi.GPIO as GPIO

pA = 17
pB = 18
pENT = 27
pBELL = 4

def setup():
    #GPIO.setmode(GPIO.BOARD)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup([pA, pB, pENT], GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(pBELL, GPIO.OUT)

def cbClick(channel):
    print('CB on {}'.format(channel))

class Knob:
    def __init__(self):
        self.state = 0
        self.dir_count = 0

    def cbRotate(self, channel):
        bA, bB = int(GPIO.input(pA) == GPIO.LOW), int(GPIO.input(pB) == GPIO.LOW)
        new_state = bB << 1 | (bA ^ bB)
        if new_state == self.state:
            return

        d = (new_state - self.state) % 4 - 2
        self.state = new_state
        self.dir_count += d

        if self.state == 0:
            if self.dir_count < 0:
                print('CCW')
            elif self.dir_count > 0:
                print('CW')
            else:
                print('nothing')
            self.dir_count = 0

if __name__ == '__main__':
    try:
        setup()
        k = Knob()
        GPIO.add_event_detect(pA, GPIO.BOTH, k.cbRotate)
        GPIO.add_event_detect(pB, GPIO.BOTH, k.cbRotate)
        GPIO.add_event_detect(pENT, GPIO.FALLING, cbClick, bouncetime=800)
        time.sleep(100)
    finally:
        GPIO.cleanup()

