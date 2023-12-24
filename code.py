# Original source:
# SPDX-FileCopyrightText: 2019 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT
#
# Heavily modified by Nathaniel Dean started December 2023, License MIT

from os import getenv
from adafruit_bitmap_font import bitmap_font
import rtc
import json
import board
import busio
from digitalio import DigitalInOut
import framebufferio
import displayio
import rgbmatrix
import adafruit_display_text.label
import terminalio
import time
from adafruit_datetime import datetime
import adafruit_requests as requests
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi

TEXT_URL = "http://wifitest.adafruit.com/testwifi/index.html"
BTC_URL = "http://api.coindesk.com/v1/bpi/currentprice/USD.json"
WTC_URL = "http://worldtimeapi.org/api/ip"

SETUP_WIFI = "SETUP_WIFI"
RESET_DISPLAY = "RESET_DISPLAY"
SETUP_BOOT_SCREEN = "SETUP_BOOT_SCREEN"
SETUP_BOARD_STATE = "SETUP_BOARD_STATE"
SETUP_WIFI_STATE = "SETUP_WIFI_STATE"
SET_RTC = "SET_RTC"
RUN_DEMO_STATE = "RUN_DEMO_STATE"
EXIT_STATE = "EXIT_STATE"

DISPLAY_BOOTING = "Booting"
DISPLAY_DEMO1 = "Demo1"

IHLRGB_VERSION = "v0.0.2"


class LinedGroup:
    def __init__(self, name, fontchoice=None, textcolor=0x00A000):
        self.font = terminalio.FONT
        if fontchoice is not None:
            self.font = bitmap_font.load_font(f"fonts/{fontchoice}.bdf")

        self.fontheight = self.font.get_bounding_box()[1]
        self.numlines = 32 // self.fontheight

        if self.numlines == 0:
            self.numlines = 1

        self.lines = [
            adafruit_display_text.label.Label(
                font=self.font, color=0x00A000, text=f"Line {i+1}"
            )
            for i in range(self.numlines)
        ]

        self.group = displayio.Group()
        for i, line in enumerate(self.lines):
            line.x = 0
            line.y = (i + 1) * self.fontheight - (self.fontheight // 2)
            self.group.append(line)

        self.name = name

    def update_anim(self):
        pass

    def group(self):
        return self.group

    def name(self):
        return self.name

    def set_text(self, lineno, text):
        if lineno > len(self.lines) or lineno < 0:
            return  # should this be a silent error?
        self.lines[lineno].text = text


class IHLRGB:
    def __init__(self):
        self.esp = None
        self.board_firmware_version = ""
        self.board_mac_pretty = ""

        self.secrets = {}

        self.matrix = None
        self.display = None
        self.allgroups = {}
        self.rootgroup = None
        self.displaystate = ""
        self.displaynewstate = ""

        self.state = RESET_DISPLAY

        self.statetask = None
        self.displaytask = None

    def run(self):
        while self.state != EXIT_STATE:
            self.detect_inputs()
            self.run_state()
            self.refresh_screen()
        self.exit_state()

    def run_state(self):
        if self.state == RESET_DISPLAY:
            self.state = self.reset_display()
        elif self.state == SETUP_BOOT_SCREEN:
            self.state = self.setup_screens()
        elif self.state == SETUP_BOARD_STATE:
            self.state = self.setup_board()
        elif self.state == SETUP_WIFI:
            self.state = self.setup_wifi()
        elif self.state == RUN_DEMO_STATE:
            self.state = self.run_demo_tick()
        elif self.state == SET_RTC:
            self.state = self.set_rtc()
        else:
            print(f"What state is this? {self.state}")

    def detect_inputs(self):
        pass

    def run_demo_tick(self):
        self.displaynewstate = DISPLAY_DEMO1
        c = rtc.RTC().datetime
        hr = str(100 + c.tm_hour)[1:]
        mn = str(100 + c.tm_min)[1:]
        sc = str(100 + c.tm_sec)[1:]
        self.demopage_line(0, f"{c.tm_mon}/{c.tm_mday}/{c.tm_year}")
        self.demopage_line(1, f"{hr}:{mn}:{sc}")

        return RUN_DEMO_STATE

    def set_rtc(self):
        rsp = requests.get(WTC_URL)
        if rsp.status_code == 200:
            rr = json.loads(rsp.content)
            newtime = datetime.fromisoformat(rr["datetime"])
            rtc.RTC().datetime = newtime.timetuple()
            print(f"New time: {time.localtime()}")
            time.sleep(1)
        return RUN_DEMO_STATE

    def refresh_screen(self):
        if self.display is not None:
            if self.displaynewstate != self.displaystate:
                self.displaystate = self.displaynewstate
                self.rootgroup = self.allgroups[self.displaystate].group
                self.display.root_group = self.rootgroup
            if (
                self.displaystate is not None
                and self.allgroups is not None
                and self.displaystate in self.allgroups
            ):
                self.allgroups[self.displaystate].update_anim()
            while not self.display.refresh(minimum_frames_per_second=0):
                time.sleep(0.001)

    def reset_display(self):
        displayio.release_displays()

        matrix = rgbmatrix.RGBMatrix(
            width=64,
            bit_depth=4,
            rgb_pins=[
                board.MTX_R1,
                board.MTX_G1,
                board.MTX_B1,
                board.MTX_R2,
                board.MTX_G2,
                board.MTX_B2,
            ],
            addr_pins=[
                board.MTX_ADDRA,
                board.MTX_ADDRB,
                board.MTX_ADDRC,
                board.MTX_ADDRD,
            ],
            clock_pin=board.MTX_CLK,
            latch_pin=board.MTX_LAT,
            output_enable_pin=board.MTX_OE,
        )
        self.display = framebufferio.FramebufferDisplay(matrix, auto_refresh=False)
        return SETUP_BOOT_SCREEN

    def setup_screens(self):
        self.setup_bootscreen()
        self.setup_demoscreen()
        return SETUP_BOARD_STATE

    def setup_bootscreen(self):
        bootscreen = LinedGroup(DISPLAY_BOOTING, "4x6")
        self.allgroups[DISPLAY_BOOTING] = bootscreen
        self.rootgroup = self.allgroups[DISPLAY_BOOTING].group
        self.display.root_group = self.rootgroup
        self.displaystate = DISPLAY_BOOTING
        self.displaynewstate = DISPLAY_BOOTING

        for i in range(len(bootscreen.lines)):
            bootscreen.set_text(i, "")
        bootscreen.set_text(0, f"IHLRGB {IHLRGB_VERSION}")

    def bootscreen_line(self, lineno, text):
        self.allgroups["Booting"].set_text(lineno, text)
        self.refresh_screen()

    def setup_demoscreen(self):
        demoscreen = LinedGroup(DISPLAY_DEMO1)
        self.allgroups[DISPLAY_DEMO1] = demoscreen

        for i in range(len(demoscreen.lines)):
            demoscreen.set_text(i, "")

    def demopage_line(self, lineno, text):
        self.allgroups[DISPLAY_DEMO1].set_text(lineno, text)
        self.refresh_screen()

    def setup_board(self):
        print(f"Booting up IHLRGB {IHLRGB_VERSION}")

        # all board pin settings
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        esp32_cs = DigitalInOut(board.ESP_CS)
        esp32_ready = DigitalInOut(board.ESP_BUSY)
        esp32_reset = DigitalInOut(board.ESP_RESET)
        self.esp = adafruit_esp32spi.ESP_SPIcontrol(
            spi, esp32_cs, esp32_ready, esp32_reset
        )
        if self.esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
            print("ESP32 found and in idle mode")
        self.board_firmware_version = self.esp.firmware_version.decode()[:-1]
        print(f"Firmware vers. {self.board_firmware_version}")
        self.bootscreen_line(1, f"FW {self.board_firmware_version}")

        self.board_mac_pretty = "-".join(
            [str(hex(256 + i))[3:] for i in self.esp.MAC_address]
        )
        print(f"MAC addr: {self.board_mac_pretty}")
        self.bootscreen_line(2, f"MAC {self.board_mac_pretty}")

        return SETUP_WIFI

    def setup_wifi(self):
        self.secrets = {
            "ssid": getenv("CIRCUITPY_WIFI_SSID"),
            "password": getenv("CIRCUITPY_WIFI_PASSWORD"),
        }

        requests.set_socket(socket, self.esp)

        print("Connecting to AP...")
        self.bootscreen_line(3, "Connecting...")

        while not self.esp.is_connected:
            try:
                self.esp.connect_AP(self.secrets["ssid"], self.secrets["password"])
            except OSError as e:
                print("could not connect to AP, retrying: ", e)
                self.bootscreen_line(3, "Retrying...")
                continue
        print("Connected to", str(self.esp.ssid, "utf-8"), "\tRSSI:", self.esp.rssi)
        ip = self.esp.pretty_ip(self.esp.ip_address)
        print("My IP address is", ip)
        self.bootscreen_line(3, f"IP {ip}")
        print(
            "IP lookup adafruit.com: %s"
            % self.esp.pretty_ip(self.esp.get_host_by_name("adafruit.com"))
        )
        print("Ping google.com: %d ms" % self.esp.ping("google.com"))

        return SET_RTC

    def exit_state(self):
        while True:
            time.sleep(1)

    def find_access_points(self):
        for ap in self.esp.scan_networks():
            print("\t%s\t\tRSSI: %d" % (str(ap["ssid"], "utf-8"), ap["rssi"]))


if __name__ == "__main__":
    IHLRGB().run()
