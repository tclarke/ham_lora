import board
import digitalio
from adafruit_debouncer import Debouncer
import displayio
import adafruit_displayio_sh1107
from terminalio import FONT
from adafruit_display_text import label
from adafruit_display_shapes import circle
import adafruit_imageload
import time
from radio import Radio
import state_machine


class Buttons:
	LONG_PRESS_TIME = 2

	def __init__(self):
		self._ab = digitalio.DigitalInOut(board.D9)
		self._bb = digitalio.DigitalInOut(board.D6)
		self._cb = digitalio.DigitalInOut(board.D5)
		self._ab.switch_to_input(pull=digitalio.Pull.UP)
		self._bb.switch_to_input(pull=digitalio.Pull.UP)
		self._cb.switch_to_input(pull=digitalio.Pull.UP)
		self._a = Debouncer(self._ab, interval=0.01)
		self._b = Debouncer(self._bb, interval=0.01)
		self._c = Debouncer(self._cb, interval=0.01)
		self._a_tm = None
		self._b_tm = None
		self._c_tm = None

	def __call__(self):
		short_press, long_press = [], []
		self._a.update()
		if self._a.fell:
			self._a_tm = time.time()
		if self._a.rose:
			if self._a_tm is not None:
				short_press.append(0)
		if self._a_tm is not None and (time.time() - self._a_tm) > Buttons.LONG_PRESS_TIME:
			long_press.append(0)
			self._a_tm = 0
		self._b.update()
		if self._b.fell:
			self._b_tm = time.time()
		if self._b.rose:
			if self._b_tm is not None:
				short_press.append(1)
		if self._b_tm is not None and (time.time() - self._b_tm) > Buttons.LONG_PRESS_TIME:
			long_press.append(1)
			self._b_tm = 0
		self._c.update()
		if self._c.fell:
			self._c_tm = time.time()
		if self._c.rose:
			if self._c_tm is not None:
				short_press.append(2)
		if self._c_tm is not None and (time.time() - self._c_tm) > Buttons.LONG_PRESS_TIME:
			long_press.append(2)
			self._c_tm = 0
		return short_press, long_press

class GUI:
	WIDTH = 128
	HEIGHT = 64
	MENU_TIME = 2
	TGI_TX = 0
	TGI_RX = 1
	TGI_MENU = 2
	TGI_BLANK = 3
	TGI_BEACON = 4
	TGI_SEQ = 5
	TGI_FREE = 6

	def __init__(self, config) -> None:
		self._config = config
		self._sprites, self._palette = adafruit_imageload.load('/icons.bmp', bitmap=displayio.Bitmap, palette=displayio.Palette)
		self._palette.make_transparent(0)

		displayio.release_displays()
		self._i2c = board.I2C()
		self._display_bus = displayio.I2CDisplay(self._i2c, device_address=0x3C)
		self._display = adafruit_displayio_sh1107.SH1107(self._display_bus, width=UI.WIDTH, height=UI.HEIGHT, rotation=0)
		self._top = displayio.Group()
		self._display.show(self._top)

		self._status = displayio.TileGrid(self._sprites, pixel_shader=self._palette, width=8, height=1, tile_width=16, tile_height=16, default_tile=self.TGI_BLANK)
		self._status[6] = self.TGI_RX
		self._top.append(self._status)

		self._select = displayio.Group(x=0, y=24)
		self._top.append(self._select)
		self._select.append(circle.Circle(8, 0, 4, fill=0xffffff, outline=0xffffff))
		self._select.append(circle.Circle(8, 16, 4, fill=None, outline=0xffffff))
		self._select.append(circle.Circle(8, 32, 4, fill=None, outline=0xffffff))

		self._main = displayio.Group(x=16, y=24)
		self._top.append(self._main)
		self._main.append(label.Label(FONT, x=0, y=0, baseline=True, text=""))
		self._main.append(label.Label(FONT, x=0, y=16, baseline=True, text=""))
		self._main.append(label.Label(FONT, x=0, y=32, baseline=True, text=""))
	
	def set_text(self, idx, text, inverse=False):
		self._main[idx].text = str(text)
		self._main[idx].color = 0x000000 if inverse else 0xffffff
		self._main[idx].background_color = 0xffffff if inverse else None
	
	def set_all_text(self, text):
		for idx, txt in enumerate(text):
			self.set_text(idx, txt)

	def clear_text(self):
		for idx in range(3):
			self._main[idx].text = ""
			self._main[idx].color = 0xffffff
			self._main[idx].background_color = None


#######
# Main execution
#######
config = {}
with open('/config.json', 'rt') as f:
	import json
	config = json.load(f)

ui = GUI(config)
buttons = Buttons()
sm = state_machine.StateMachine()
radio = Radio()
if "power" in config:
	radio.power = config["power"]
if "frequency" in config:
	radio.frequency = config["frequency"]
mode = config["mode"]
while True:
	short_press, long_press = buttons()
	sm(short_press=short_press, long_press=long_press, mode=mode, ui=ui, radio=radio)