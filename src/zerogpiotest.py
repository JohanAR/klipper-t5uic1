import asyncio
import gpiozero as gpio
import logging

PIN_A = 17
PIN_B = 18
PIN_ENT = 27
PIN_BUZZ = 4

class Buzzer:
    def __init__(self):
        self.alarm = False

        self.buzzer = gpio.Buzzer(PIN_BUZZ)

    async def blip(self):
        if not self.alarm:
            self.buzzer.on()
            await asyncio.sleep(0.01)
            self.buzzer.off()

    def set_alarm(self, value):
        new_state = bool(value)
        if new_state != self.alarm:
            self.alarm = new_state
            self.buzzer.value = self.alarm

class Button:
    def __init__(self):
        self.was_held = False
        self.loop = asyncio.get_running_loop()

        self.button = gpio.Button(PIN_ENT, hold_time=1)
        self.button.when_pressed = self.__pressed
        self.button.when_held = self.__held
        self.button.when_released = self.__released

        self.on_pressed = None
        self.on_held = None
        self.on_released = None

    def __pressed(self):
        print("__pressed")
        if self.on_pressed is not None:
            asyncio.run_coroutine_threadsafe(self.on_pressed(), self.loop)

    def __held(self):
        if self.on_held is not None:
            self.was_held = True
            asyncio.run_coroutine_threadsafe(self.on_held(), self.loop)

    def __released(self):
        print("__released")
        if not self.was_held:
            if self.on_released is not None:
                asyncio.run_coroutine_threadsafe(self.on_released(), self.loop)
        self.was_held = False

class Knob:
    def __init__(self):
        self.state = 0
        self.dir_count = 0
        self.a = 0
        self.b = 0
        self.loop = asyncio.get_running_loop()

        self.on_rotate_cw = None
        self.on_rotate_ccw = None

        self.button_a = gpio.Button(PIN_A)
        self.button_a.when_pressed = self.__set_a
        self.button_a.when_released = self.__clear_a

        self.button_b = gpio.Button(PIN_B)
        self.button_b.when_pressed = self.__set_b
        self.button_b.when_released = self.__clear_b

    def __set_a(self):
        self.a = 1
        self.__rotate()

    def __clear_a(self):
        self.a = 0
        self.__rotate()

    def __set_b(self):
        self.b = 1
        self.__rotate()

    def __clear_b(self):
        self.b = 0
        self.__rotate()

    def __rotate(self):
        new_state = self.b << 1 | (self.a ^ self.b)
        if new_state == self.state:
            return

        d = (new_state - self.state) % 4 - 2
        self.state = new_state
        self.dir_count += d

        if self.state == 0:
            if self.dir_count < 0:
                if self.on_rotate_ccw is not None:
                    asyncio.run_coroutine_threadsafe(self.on_rotate_ccw(-1), self.loop)
            elif self.dir_count > 0:
                if self.on_rotate_cw is not None:
                    asyncio.run_coroutine_threadsafe(self.on_rotate_cw(1), self.loop)
            self.dir_count = 0

def handle_exception(loop, context):
    # context["message"] will always be there; but context["exception"] may not
    msg = context.get("exception", context["message"])
    logging.error(f"Caught exception: {msg}")
    logging.info("Shutting down...")
    #asyncio.create_task(shutdown(loop))


async def main():
    asyncio.get_event_loop().set_exception_handler(handle_exception)
    z = Buzzer()
    alarm_on = False

    async def toggle_alarm():
        try:
            global alarm_on, z
            print("3")
            alarm_on = not alarm_on
            print("4")
            print("setting alarm {}".format(alarm_on))
            z.set_alarm(alarm_on)
            print("5")
        except Exception as err:
            print(err)
            raise

    async def turn(delta):
        print(delta)

    b = Button()
    b.on_pressed = z.blip
    b.on_held = toggle_alarm
    k = Knob()
    k.on_rotate_cw = turn
    k.on_rotate_ccw = turn
    print("ready")
    await asyncio.sleep(10)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    try:
        asyncio.run(main(), debug=True)
    except asyncio.CancelledError:
        pass
