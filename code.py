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

	def __call__(self):
		press, release = [], []
		self._a.update()
		if self._a.fell:
			press.append(0)
		if self._a.rose:
			release.append(0)
		self._b.update()
		if self._b.fell:
			press.append(1)
		if self._b.rose:
			release.append(1)
		self._c.update()
		if self._c.fell:
			press.append(2)
		if self._c.rose:
			release.append(2)
		return press, release


class MainFA:
	INVALID = -1
	BEACON = 0
	XMIT = 1
	MENU = 2
	SEQUENCE = 3
	FREE = 4
	MENU_MODE = 5
	MENU_SETTINGS = 6
	MENU_POWER = 7

	def __init__(self) -> None:
		self.state = MainFA.INVALID
		self.seq_idx = 5
		self.theircall = ""

	def set_mode(self, mode):
		if mode == 'beacon':
			self.state = MainFA.BEACON
		elif mode == 'sequence':
			self.state = MainFA.SEQUENCE
		elif mode == 'free':
			self.state = MainFA.FREE
		else:
			self.state = MainFA.MENU

	def menu(self):
		self.state = MainFA.MENU
		return "Mode", "Settings", "Power Off"
	
	def select(self, idx):
		if self.state == MainFA.MENU:
			if idx == 0:
				self.state = MainFA.MENU_MODE
				return "Beacon", "Sequence", "Free"
			elif idx == 1:
				self.state = MainFA.MENU_SETTINGS
				return "SETTINGS HERE", "", ""
			elif idx == 2:
				self.state = MainFA.MENU_POWER
				return "Powering Off", "", ""
		elif self.state == MainFA.MENU_MODE:
			if idx == 0:
				self.state = MainFA.BEACON
			elif idx == 1:
				self.state = MainFA.SEQUENCE
			elif idx == 2:
				self.state = MainFA.FREE
		return None

class UI:
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

		self._fa = MainFA()
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
		self._cur = 0
		self._selecting = None
		self._xmit = None
		self._xmit_message = None
		self._recv = False

		self._main = displayio.Group(x=16, y=24)
		self._top.append(self._main)
		self._main.append(label.Label(FONT, x=0, y=0, baseline=True, text="First line"))
		self._main.append(label.Label(FONT, x=0, y=16, baseline=True, text="Second line"))
		self._main.append(label.Label(FONT, x=0, y=32, baseline=True, text="Third line"))

		self.update_mode(self._config.get("mode", None))

		self._radio = Radio()
		if "power" in self._config:
			self._radio.power = self._config["power"]
		if "frequency" in self._config:
			self._radio.frequency = self._config["frequency"]
	
	def update_mode(self, mode=None):
		if mode is not None:
			self._fa.set_mode(mode)
		if self._fa.state == MainFA.MENU:
			self._select.hidden = False
			self._recv = False
		else:
			self._select.hidden = True
		if self._fa.state == MainFA.BEACON:
			self._xmit_message = self._config["messages"]["beacon"].format(**self._config)
			self._main[0].text = self._xmit_message
			self._main[1].text = ""
			self._main[2].text = ""
			self._status[1] = self.TGI_BEACON
			self._recv = True
		elif self._fa.state == MainFA.SEQUENCE:
			self._xmit_message = self._config["messages"]["sequence"][self._fa.seq_idx].format(**self._config, theircall=self._fa.theircall)
			self._main[0].text = self._xmit_message
			self._main[1].text = ""
			self._main[2].text = ""
			self._status[1] = self.TGI_SEQ
			self._recv = True
		elif self._fa.state == MainFA.FREE:
			free_msgs = self._config["messages"]["free"]
			self._xmit_message = free_msgs[0].format(**self._config, theircall=self._fa.theircall) if len(free_msgs) >= 1 else ""
			self._main[0].text = self._xmit_message
			self._main[1].text = free_msgs[1].format(**self._config, theircall=self._fa.theircall) if len(free_msgs) >= 2 else ""
			self._main[2].text = free_msgs[2].format(**self._config, theircall=self._fa.theircall) if len(free_msgs) >= 3 else ""
			self._status[1] = self.TGI_FREE
			self._recv = True
		if self._xmit is not None:
			self._status[6] = self.TGI_TX
		elif self._recv:
			self._status[6] = self.TGI_RX
		else:
			self._status[6] = self.TGI_BLANK

	def update_selection(self):
		if self._select.hidden:
			self._main[self._cur].color = 0xffffff
			self._main[self._cur].background_color = None
		else:
			self._select[0].fill = 0xffffff if self._cur == 0 else None
			self._select[1].fill = 0xffffff if self._cur == 1 else None
			self._select[2].fill = 0xffffff if self._cur == 2 else None
			self._main[self._cur].color = 0x000000 if self._selecting is not None else 0xffffff
			self._main[self._cur].background_color = 0xffffff if self._selecting is not None else None
	
	def process_message(self, m):
		print(f"RECV: {m}")

	def select(self):
		if not self._select.hidden:  # process menu selection
			txt = self._fa.select(self._cur)
			if txt is None:
				self.update_mode()
			else:
				for i, v in enumerate(txt):
					self._main[i].text = v if v else ""
			if self._fa.state == MainFA.MENU_POWER:
				self.power_off()
		else:
			self.toggle_xmit()  # turn transmit on/off
	
	def toggle_xmit(self):
		if self._xmit is None:
			self._xmit = 0
		else:
			self._xmit = None
		if self._xmit:
			self._status[6] = self.TGI_TX
		elif self._recv:
			self._status[6] = self.TGI_RX
		else:
			self._status[6] = self.TGI_BLANK
	
	def menu(self):
		self._select.hidden = False
		self._cur = 0
		txt = self._fa.menu()
		for i, v in enumerate(txt):
			self._main[i].text = v

	def selection_up(self):
		if not self._select.hidden:
			if self._cur == 0:
				self._cur = 2
			else:
				self._cur -= 1

	def selection_down(self):
		if not self._select.hidden:
			if self._cur == 2:
				self._cur = 0
			else:
				self._cur += 1
	
	def power_off(self):
		self._display.sleep()
		self._radio.power_off()
	
	def power_on(self):
		self._display.wake()
		self._radio.power_on()
	
	def loop(self):
		while True:
			# process buttons
			press, release = self._buttons()

			# special case if we're in low power mode
			if self._fa.state == MainFA.MENU_POWER and len(press) > 0:
				self.update_mode(self._config.get("mode", None))
				self.power_on()
				continue

			# check to see if middle button is pressed, if so start a timer
			if 1 in press:
				self._selecting = time.time()

			# see if we've released the middle button, if so see if it was a long or short press
			if 1 in release:
				if self._selecting is not None and (time.time() - self._selecting) >= UI.MENU_TIME:
					# activate the menu
					self.menu()
				else:
					# a short press
					self.select()
				self._selecting = None  # reset the timer

			if 2 in release:
				self.selection_down()
			if 0 in release:
				self.selection_up()

			# redraw the selection icons
			self.update_selection()

			# radio xmit
			if self._xmit is not None:
				diff = time.time() - self._xmit
				if diff >= self._config["beacon_time"]:
					self._status[6] = self.TGI_TX
					self._radio.transmit(self._xmit_message)
					if self._fa.state == MainFA.BEACON:
						self._xmit = time.time()
					else:
						self.toggle_xmit()
				elif diff >= 1:
					self._status[6] = self.TGI_RX if self._recv else self.TGI_BLANK
			elif self._recv:  # radio polling
				self._radio.update()
				while len(self._radio.messages) > 0:
					self.process_message(self._radio.messages.pop(0))


#######
# Main execution
#######
config = {}
with open('/config.json', 'rt') as f:
	import json
	config = json.load(f)

top = UI(config)
top.loop()