import asyncio
import time
import serial
from serialtest import Dwin
from zerogpiotest import Buzzer, Button, Knob

display = None

class Elem:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.text = None
        self.textalign = 'left'
        self.font = 0
        self.fgcolor = (1,1,1)
        self.bgcolor = (0,0,0)

    def draw(self):
        global display
        display.draw_rect(self.x, self.y, self.x+self.width-1, self.y+self.height-1,
                          color=self.bgcolor, fill=1)
        if self.text:
            display.draw_string(self.x, self.y,
                               self.text, self.font,
                               color=self.fgcolor, bgcolor=self.bgcolor,
                               fixedwidth=True)

class Box:
    def __init__(self, x, y, width, height):
        self.x, self.y = x, y
        self.width, self.height = width, height

    def draw(self):
        global display
        display.draw_rect(x, y, x+width, y+height)

class MenuItem(Elem):
    def __init__(self):
        super().__init__()
        self.__selected = False

    @property
    def selected(self):
        return self.__selected

    @selected.setter
    def selected(self, value):
        if self.__selected != value:
            self.__selected = value
            self.draw_select_marker()

    def draw(self):
        super().draw()
        self.draw_select_marker()

    def draw_select_marker(self):
        global display
        color = (1,1,1) if self.__selected else (0,0,0)
        display.draw_rect(self.x, self.y, self.x+self.width-1, self.y+self.height-1,
                          color=color, fill=0)
        #print('mi draw {}, {}, {}, {}'.format(self.x, self.y, self.x+self.width-1, self.y+self.height-1))
        #if self.selected:
            #display.draw_rect(self.x, self.y, self.x+self.width-1, self.y+self.height-1,
                              #color=(1,0,0), fill=2)

class TextBox(Box):
    pass

class Label:
    def __init__(self, text, x, y, width, height):
        self.text = text
        self.x, self.y = x, y
        self.width, self.height = width, height

    def draw(self):
        global display
        display.draw_rect(x, y, x+width, y+height)

class MenuList(Elem):
    def __init__(self):
        super().__init__()
        self.items = []
        self.elems = [MenuItem() for _ in range(8)]
        self.selected_idx = 0
        self.idx_offset = 0
        self.scrollbar_visible = False

    def set_items(self, items):
        self.items = items
        #if self.selected_idx is None:
            #self.selected_idx = 0 if len(self.items) > 0 else None
        if self.selected_idx >= len(self.items):
            self.selected_idx = len(self.items) - 1
        self.scrollbar_visible = len(self.items) > len(self.elems)
        self.update_elems()
        self.layout()
        self.draw()

    def selected_elem(self):
        return self.elems[self.selected_idx - self.idx_offset]

    def adjust_offset(self, delta):
        self.idx_offset += delta
        self.update_elems()

    def move_down(self, steps):
        self.move_selection(1)

    def move_up(self, steps):
        self.move_selection(-1)

    def move_selection(self, direction):
        if self.selected_idx is None:
            return
        self.set_selection(self.selected_idx + direction)

    def scroll_down(self):
        if self.idx_offset < len(self.items) - len(self.elems):
            self.idx_offset += 1

    def scroll_up(self):
        if self.idx_offset > 0:
            self.idx_offset -= 1

    def set_selection(self, new_idx):
        if new_idx == self.selected_idx or new_idx < 0 or new_idx >= len(self.items):
            return
        self.selected_elem().selected = False
        if new_idx < self.idx_offset + 1:
            self.scroll_up()
        elif new_idx >= self.idx_offset + len(self.elems) - 1:
            self.scroll_down()
        else:
            pass
        self.selected_idx = new_idx
        self.selected_elem().selected = True
        #self.update_elems()
        #self.draw()
        global display
        display.update_lcd()

    def update_elems(self):
        for n, e in enumerate(self.elems):
            item_idx = n + self.idx_offset
            e.text = self.items[item_idx] if item_idx < len(self.items) else None
            e.selected = self.selected_idx == item_idx

    def layout(self):
        global display
        item_height = int(self.height / len(self.elems))
        font = display.largest_font_for_height(item_height)
        print('ih {} font {}'.format(item_height, font))
        scroller_width = 10 if self.scrollbar_visible else 0
        for n, e in enumerate(self.elems):
            e.x = self.x
            e.y = n * item_height
            e.width = self.width - scroller_width
            e.height = item_height
            e.font = font

    def draw(self):
        for e in self.elems:
            e.draw()
        self.draw_scrollbar()

    def draw_scrollbar(self):
        print(f"draws {self.scrollbar_visible}")
        if not self.scrollbar_visible:
            return
        before = self.idx_offset
        after = len(self.items) - len(self.elems) - before
        y0 = self.y + int(before / len(self.items) * self.height)
        y1 = self.y + self.height - int(after / len(self.items) * self.height) - 1
        x0 = self.x + self.width - 10
        x1 = self.x + self.width - 1
        bgcolor = (0.25, 0.25, 0.25)
        global display
        display.draw_rect(x0, self.y, x1, self.y + self.height - 1, color=bgcolor, fill=1)
        display.draw_rect(x0, y0, x1, y1, color=(0.75, 0.75, 0.75), fill=1)

class StatusBar(Elem):
    def __init__(self):
        super().__init__()
        self.current_prio = 0

    def info(self, text):
        if self.current_prio == 0:
            self.bgcolor = (0.15, 0.25, 0.50)
            self.text = text

    def warn(self, text):
        if self.current_prio <= 1:
            self.bgcolor = (0.25, 0.25, 0.25)
            self.text = text
            self.current_prio = 1

    def error(self, text):
        if self.current_prio <= 2:
            self.bgcolor = (0.25, 0.25, 0.25)
            self.text = text
            self.current_prio = 2

    def layout(self):
        self.font = display.largest_font_for_height(self.height)

class ValueBox(Elem):
    def __init__(self):
        super().__init__()
        self.horizontal = True
        self.label = Elem()
        self.value = Elem()

    def layout(self):
        self.label.x = self.x
        self.label.y = self.y
        if self.horizontal:
            self.label.width = self.width // 2
            self.label.height = self.height
            self.value.x = self.x + self.label.width + 1
            self.value.y = self.y
            self.value.width = self.width - self.label.width
            self.value.height = self.height
        else:
            self.label.width = self.width
            self.label.height = self.height // 2
            self.value.x = self.x
            self.value.y = self.y + self.label.height + 1
            self.value.width = self.width
            self.value.height = self.height - self.label.height
        self.label.font = 1
        self.value.font = 1

    def draw(self):
        self.label.draw()
        self.value.draw()


class VerticalInfoPanel(Elem):
    def __init__(self):
        super().__init__()
        self.poss = [ValueBox() for _ in range(3)]

    def set_pos(self, posv):
        pass

    def layout(self):
        w3 = self.width // 3
        for n, vb in enumerate(self.poss):
            vb.horizontal = False
            vb.x = self.x + n * w3
            vb.y = self.y
            vb.width = w3
            vb.height = 34
            vb.label.text = ['X', 'Y', 'Z'][n]
            vb.value.text = ['-123.34', '   0.00', '- 13.8'][n]
            vb.layout()

    def draw(self):
        for vb in self.poss:
            vb.draw()


class UI:
    def __init__(self):
        self.width = 480
        self.height = 272
        self.menu = MenuList()
        self.info = VerticalInfoPanel()
        self.focus = self.menu

    def layout(self):
        sidebar_width = 180
        self.info.width = sidebar_width
        self.info.height = self.height
        self.info.layout()

        self.menu.x = sidebar_width + 1
        self.menu.y = 0
        self.menu.width = self.width - sidebar_width
        self.menu.height = self.height

        self.menu.layout()

    def draw(self):
        global display
        display.frame_clear()
        self.info.draw()
        self.menu.draw()

    async def move_down(self, steps):
        self.focus.move_down(steps)

    async def move_up(self, steps):
        self.focus.move_up(steps)

async def test_move(ui):
    await ui.move_down(1)
    await asyncio.sleep(1)

    for _ in range(5):
        await ui.move_up(1)
        await asyncio.sleep(0.1)

    await asyncio.sleep(2)

    for _ in range(10):
        await ui.move_down(1)
        await asyncio.sleep(0.1)

async def main():
    #with serial.Serial('/dev/ttyAMA0', baudrate=115200, timeout=1) as ser:
    with Dwin() as dwin:
        global display
        #display = Dwin(ser)
        display = dwin
        display.send_handshake()
        display.frame_set_rotation(0)
        display.frame_clear()

        ui = UI()
        ui.layout()
        ui.draw()
        ui.menu.set_items(["one", "two", "three", "monkeys", "file", "four", "last"])
        display.update_lcd()

        #ui.menu.set_selection(3)
        #await test_move(ui)

        k = Knob()
        k.on_rotate_cw = ui.move_down
        k.on_rotate_ccw = ui.move_up

        print("ready")
        await asyncio.sleep(10)

if __name__ == '__main__':
    try:
        asyncio.run(main(), debug=True)
    except asyncio.CancelledError:
        pass
