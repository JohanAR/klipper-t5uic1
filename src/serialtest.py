import asyncio
import collections
import serial
import threading
import time

FONT_HEIGHTS = [12, 16, 20, 24, 28, 32, 40, 48, 56, 64]
FONT_WIDTHS =  [ 6,  8, 10, 12, 14, 16, 20, 24, 28, 32]

PREFIX=bytes.fromhex('aa')
SUFFIX=bytes.fromhex('cc33c33c')

BYTEORDER='big'

def DWIN_Byte(b, signed=False):
    return b.to_bytes(1, BYTEORDER, signed=signed)

def DWIN_Word(w, signed=False):
    return w.to_bytes(2, BYTEORDER, signed=signed)

def DWIN_Long(w, signed=False):
    return w.to_bytes(4, BYTEORDER, signed=signed)

def DWIN_VeryLong(w, signed=False):
    return w.to_bytes(8, BYTEORDER, signed=signed)

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

    def font_height(self, font):
        return FONT_HEIGHTS[font]

    def font_width(self, font):
        return FONT_WIDTHS[font]

    def largest_font_for_height(self, height):
        for n, size in reversed(list(enumerate(FONT_HEIGHTS))):
            if size <= height:
                return n

    def largest_font_for_width(self, width, ncharacters=1):
        for n, size in reversed(list(enumerate(FONT_WIDTHS))):
            if size * ncharacters <= width:
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

    def set_backlight(self, luminance=1.0):
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

    def draw_number(self, x, y, value, size, color=(1,1,1), bgcolor=None, signed=False, digits=5, decimals=0, left_adjust=False, zero_pad=False):
        drawbg = bgcolor is not None
        if bgcolor is None:
            bgcolor = (0,0,0)
        #display_zero = zero_as is not None
        #zero_style = zero_as == '0'
        value = round(value * 10 ** decimals)
        #adjust = 1 if not left_adjust and signed and value >= 0 else 0
        if not left_adjust and signed and value >= 0:
            x += FONT_WIDTHS[size]
        self.send(DWIN_Byte(0x14),
                  DWIN_Byte(drawbg << 7 | signed << 6 | (not left_adjust) << 5 | zero_pad << 4 | size & 0b1111),
                  DWIN_Color(*color),
                  DWIN_Color(*bgcolor),
                  DWIN_Byte(digits - decimals),
                  DWIN_Byte(decimals),
                  DWIN_Word(x),
                  DWIN_Word(y),
                  DWIN_Long(value, signed))

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

    def draw_qr(self, x, y, message, pixel_size=1):
        self.send(DWIN_Byte(0x21),
                  DWIN_Word(x),
                  DWIN_Word(y),
                  DWIN_Byte(pixel_size),
                  message.encode())

    def load_jpeg(self, jpegid=0):
        self.send(DWIN_Byte(0x22),
                  DWIN_Byte(0x00),
                  DWIN_Byte(jpegid))

def number_test(d):
    font = 5
    decs = 2
    for n, val in enumerate([0, 123, -48342, 2.21231, -87.8, 923.9898]):
        d.draw_number(0, n*FONT_HEIGHTS[font], val, font, signed=True, decimals=decs)
        d.draw_number(120, n*FONT_HEIGHTS[font], val, font, signed=True, zero_pad=True, decimals=decs)
        d.draw_number(240, n*FONT_HEIGHTS[font], val, font, signed=True, left_adjust=True, decimals=decs)
        d.draw_number(360, n*FONT_HEIGHTS[font], val, font, signed=True, left_adjust=True, zero_pad=True, decimals=decs)

#if __name__ == '__main__':
async def main():
    # DMT48270C043_04WNZ11
    # 480 x 272
    #with serial.Serial('/dev/ttyAMA0', baudrate=115200, timeout=1) as ser:
    with Dwin() as dwin:
        dwin.send_handshake()
        dwin.frame_set_rotation(0)
        dwin.set_backlight(0.5)
        dwin.update_lcd()
        #time.sleep(2)
        dwin.frame_clear()

        #dwin.load_jpeg(3)
        number_test(dwin)
        #dwin.draw_string(100, 60, "Monkeys!", 4)
        #dwin.draw_number(100, 100, 123, 4)

        #dwin.draw_qr(0,0,"hej",5)

        dwin.update_lcd()
        await asyncio.sleep(10)

if __name__ == '__main__':
    try:
        asyncio.run(main(), debug=True)
    except asyncio.CancelledError:
        pass
