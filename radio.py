import board
import busio
import digitalio
import time
from adafruit_rfm9x import RFM9x

class Radio:
    RST = board.D11
    CS = board.D10
    IRQ = board.D12

    def __init__(self, frequency=915.) -> None:
        self._spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        self._cs = digitalio.DigitalInOut(Radio.CS)
        self._rst = digitalio.DigitalInOut(Radio.RST)
        self._rfm9x = RFM9x(self._spi, self._cs, self._rst, frequency)
        #self._rfm9x.coding_rate = 8
    
    @property
    def frequency(self):
        return self._rfm9x.frequency_mhz
    
    @frequency.setter
    def frequency(self, v):
        self._rfm9x.frequency_mhz = v
    
    @property
    def power(self):
        return self._rfm9x.tx_power
    
    @power.setter
    def power(self, v):
        self._rfm9x.tx_power = v
    
    def power_off(self):
        self._rfm9x.sleep()
    
    def power_on(self):
        self._rfm9x.reset()
    
    def receive(self, timeout=0.005):
        buf = self._rfm9x.receive(timeout=timeout)
        if buf is not None and buf[0] != 0:
            return buf
        return None
    
    def transmit(self, msg):
        self._rfm9x.send(msg)