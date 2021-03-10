import asyncio
import collections
import serial
import threading
import time

FONT_SIZES = [12, 16, 20, 24, 28, 32, 40, 48, 56, 64]

PREFIX=bytes.fromhex('aa')
SUFFIX=bytes.fromhex('cc33c33c')

BYTEORDER='big'

def DWIN_Byte(b):
    return b.to_bytes(1, BYTEORDER)

def DWIN_Word(w):
    return w.to_bytes(2, BYTEORDER)

def DWIN_Hex(hexstr):
    return bytes.fromhex(hexstr)

def DWIN_Text(textstr):
    return textstr.encode('ascii')

def DWIN_Lum(l):
    assert(l >= 0 and l <= 1.0)
    return DWIN_Byte(int(0x1f * l + 0.5))

def DWIN_Color(r, g ,b):
    assert(r >= 0 and r <= 1.0)
    assert(g >= 0 and g <= 1.0)
    assert(b >= 0 and b <= 1.0)
    R, G, B = int(0b11111 * r + 0.5), int(0b111111 * g + 0.5), int(0b11111 * b + 0.5)
    return DWIN_Word(R << 11 | G << 5 | B)

def dump_rx(byteData):
    head, tail = b'', b''
    if byteData.startswith(PREFIX):
        head, byteData = PREFIX, byteData[len(PREFIX):]
    if byteData.endswith(SUFFIX):
        byteData, tail = byteData[:-len(SUFFIX)], SUFFIX

    print('<<< {} {} {}  {}'.format(head.hex(), byteData.hex(), tail.hex(), byteData))

def dump_tx(byteData):
    print('>>> {}'.format(byteData.hex()))

class MultiQueue:
    def __init__(self):
        self.__terminate = False
        self.rx_queue = collections.deque()
        self.tx_queue = collections.deque()
        self.cond = threading.Condition()

    def terminate(self):
        with self.cond:
            self.__terminate = True
            self.cond.notify_all()

    def put_rx(self, data):
        with self.cond:
            self.rx_queue.append(data)
            self.cond.notify_all()

    def put_tx(self, data):
        with self.cond:
            self.tx_queue.append(data)
            self.cond.notify_all()

    def get(self):
        with self.cond:
            while True:
                if self.__terminate:
                    return (0, None)
                elif len(self.tx_queue) > 0:
                    return (1, self.tx_queue.popleft())
                elif len(self.rx_queue) > 0:
                    return (2, self.rx_queue.popleft())
                self.cond.wait()

def _io_thread_func(main_loop, queue):
    with serial.Serial('/dev/ttyAMA0', baudrate=115200, timeout=1) as ser:
        while True:
            (task, data) = queue.get()
            if task == 0:
                return
            elif task == 1:
                ser.write(data)
                dump_tx(data)
            elif task == 2:
                skipped = ser.read_until(PREFIX)
                if not skipped:
                    print('<<< no response')
                else:
                    response = ser.read_until(SUFFIX)
                    dump_rx(b'\xaa' + response)


class Dwin:
    def __init__(self):
        #self.ser = serial.Serial('/dev/ttyAMA0', baudrate=115200, timeout=1)
        #self.ser = ser
        self.queue = MultiQueue()

        loop = asyncio.get_event_loop()
        self.__io_thread = threading.Thread(target=_io_thread_func, args=(loop, self.queue))

    def __enter__(self):
        self.__io_thread.start()
        return self

    def __exit__(self, *exc_details):
        self.queue.terminate()
        self.__io_thread.join()

    def largest_font_for(self, height):
        for n, size in reversed(list(enumerate(FONT_SIZES))):
            if size <= height:
                return n

    def read(self):
        self.queue.put_rx(None)
        #skipped = self.ser.read_until(PREFIX)
        #if not skipped:
            #print('<<< no response')
        #else:
            #response = self.ser.read_until(SUFFIX)
            #self.dump_rx(b'\xaa' + response)

    def send(self, *args):
        byteData = b''.join(args)
        message = PREFIX + byteData + SUFFIX
        self.queue.put_tx(message)
        #self.ser.write(message)
        #self.dump_tx(message)

    def send_handshake(self):
        self.send(DWIN_Byte(0x00))
        self.read()

    def frame_set_rotation(self, angle):
        d = [0, 90, 180, 270].index(angle)
        self.send(bytes.fromhex('345aa5') + DWIN_Byte(d))
        self.read()

    def set_backlight(luminance=1.0):
        self.send(DWIN_Byte(0x30), DWIN_Lum(luminance))

    def update_lcd(self):
        self.send(DWIN_Byte(0x3d))

    def frame_clear(self, color=(0,0,0)):
        self.send(DWIN_Byte(0x01), DWIN_Color(*color))

    def draw_string(self, x, y, text, size, color=(1,1,1), bgcolor=None, fixedwidth=False):
        drawbg = bgcolor is not None
        if bgcolor is None:
            bgcolor = (0,0,0)
        self.send(DWIN_Byte(0x11),
                  DWIN_Byte((not fixedwidth) << 7 | drawbg << 6 | size & 0b1111),
                  DWIN_Color(*color),
                  DWIN_Color(*bgcolor),
                  DWIN_Word(x),
                  DWIN_Word(y),
                  text.encode())

    def draw_line(self, x0, y0, x1, y1, color=(1,1,1)):
        self.send(DWIN_Byte(0x03),
                  DWIN_Color(*color),
                  DWIN_Word(x0),
                  DWIN_Word(y0),
                  DWIN_Word(x1),
                  DWIN_Word(y1))

    def draw_rect(self, x0, y0, x1, y1, color=(1,1,1), fill=0):
        # fill: 0=no, 1=yes, 2=xor
        self.send(DWIN_Byte(0x05),
                  DWIN_Byte(fill),
                  DWIN_Color(*color),
                  DWIN_Word(x0),
                  DWIN_Word(y0),
                  DWIN_Word(x1),
                  DWIN_Word(y1))

    def load_jpeg(self, jpegid=0):
        self.send(DWIN_Byte(0x22),
                  DWIN_Byte(0x00),
                  DWIN_Byte(jpegid))

def fontTest():
    sizes = [12, 16, 20, 24, 28, 32, 40, 48, 56, 64]
    y = 0
    for i in range(8):
        c = i % 2
        col = (0, (1 - c) / 2, c * 0.7)
        dwin.draw_string(21,  y, 'hey {}'.format(i), i, bgcolor=col, fixedwidth=True)
        y += sizes[i] + 1
    dwin.drawLine(21, y, 50, y)
    y = 0
    for i in range(2):
        c = i % 2
        col = (0, (1 - c) / 2, c * 0.7)
        dwin.draw_string(221,  y, 'hey {}'.format(i+8), i+8, bgcolor=col, fixedwidth=True)
        y += sizes[i+8] + 1
    dwin.drawLine(221, y, 250, y)
    x = 0
    for y in range(272):
        if y % 10 == 0:
            c = int(y / 10) % 2
            col = (c, 1 - c, 0)
            dwin.draw_rect(x,y,x+20,y+9,col,fill=1)
        c = y % 2
        col = (c, c, 1)
        dwin.drawLine(x+10,y,x+19,y,col)

if __name__ == '__main__':
    # DMT48270C043_04WNZ11
    # 480 x 272
    with serial.Serial('/dev/ttyAMA0', baudrate=115200, timeout=1) as ser:
        dwin = Dwin(ser)
        dwin.send_handshake()
        dwin.frame_set_rotation(0)
        #dwin.update_lcd()
        #time.sleep(2)
        #dwin.frame_clear()

        dwin.load_jpeg(3)

        dwin.update_lcd()

