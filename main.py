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


LONG_PRESS_TIME = 2


class Buttons:
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
		short_press = []
		long_press = []
		self._a.update()
		self._b.update()
		self._c.update()
		cur = time.time()
		if self._a_tm is not None and (cur - self._a_time) > LONG_PRESS_TIME:
			long_press.append(0)
			self._a_tm = None
		if self._b_tm is not None and (cur - self._b_time) > LONG_PRESS_TIME:
			long_press.append(1)
			self._b_tm = None
		if self._c_tm is not None and (cur - self._c_time) > LONG_PRESS_TIME:
			long_press.append(2)
			self._c_tm = None
		if self._a.fell:
			self._a_tm = time.time()
		if self._a.rose and self._a_tm is not None:
			short_press.append(0)
			self._a_tm = None
		if self._b.fell:
			self._b_tm = time.time()
		if self._b.rose and self._b_tm is not None:
			short_press.append(1)
			self._b_tm = None
		if self._c.fell:
			self._c_tm = time.time()
		if self._c.rose and self._c_tm is not None:
			short_press.append(2)
			self._c_tm = None
		return short_press, long_press

class UI:
	WIDTH = 128
	HEIGHT = 64
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

		self._sm = state_machine.StateMachine()
		self._buttons = Buttons()
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
		self._main.append(label.Label(FONT, x=0, y=0, baseline=True))
		self._main.append(label.Label(FONT, x=0, y=16, baseline=True))
		self._main.append(label.Label(FONT, x=0, y=32, baseline=True))

		self._radio = Radio()
		if "power" in self._config:
			self._radio.power = self._config["power"]
		if "frequency" in self._config:
			self._radio.frequency = self._config["frequency"]
	
	def power_off(self):
		self._display.sleep()
		self._radio.power_off()
	
	def power_on(self):
		self._display.wake()
		self._radio.power_on()
	
	def loop(self):
		while True:
			# process buttons
			short_press, long_press = self._buttons()
			self._sm(short_press=short_press, long_press=long_press)


#######
# Main execution
#######
config = {}
with open('/config.json', 'rt') as f:
	import json
	config = json.load(f)

top = UI(config)
top.loop()
