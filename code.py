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
from digitalio import DigitalInOut, Direction, Pull
import framebufferio
import displayio
import rgbmatrix
import adafruit_display_text.label
import terminalio
import time
import random
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
DISPLAY_GOL = "Gol"
DISPLAY_CAG = "CAG"
DISPLAY_WEATHER = "Weather"

DISPLAY_LIST = [DISPLAY_DEMO1, DISPLAY_GOL, DISPLAY_CAG]

IHLRGB_VERSION = "v0.1.0"


class ChaserAnimationGroup:
    def __init__(self, name):
        self.tick = [[random.randint(0, 9) for _ in range(64)] for _ in range(32)]
        self.tock = [[random.randint(0, 9) for _ in range(64)] for _ in range(32)]

        self.palette = displayio.Palette(10)
        for i in range(10):
            self.palette[i] = 0x060402 * (i + 1)

        self.bitmap = displayio.Bitmap(64, 32, len(self.palette))
        self.tilegrid = displayio.TileGrid(
            bitmap=self.bitmap, pixel_shader=self.palette
        )
        self.group = displayio.Group()
        self.group.append(self.tilegrid)

        self.directions = [
            (63, 31),
            (0, 31),
            (1, 31),
            (63, 0),
            (1, 0),
            (63, 1),
            (0, 1),
            (1, 1),
        ]

        self.ticktock = False

    def update_anim(self):
        if self.ticktock:
            for y in range(32):
                for x in range(64):
                    inside = (1 + self.tick[y][x]) % 10
                    for d in self.directions:
                        if self.tick[(y + d[1]) % 32][(x + d[0]) % 64] == inside:
                            self.tock[y][x] = inside
                            break
            for y in range(32):
                for x in range(64):
                    self.bitmap[x, y] = self.tock[y][x]
            self.ticktock = False
        else:
            for y in range(32):
                for x in range(64):
                    inside = (1 + self.tock[y][x]) % 10
                    for d in self.directions:
                        if self.tock[(y + d[1]) % 32][(x + d[0]) % 64] == inside:
                            self.tick[y][x] = inside
                            break
            for y in range(32):
                for x in range(64):
                    self.bitmap[x, y] = self.tick[y][x]
            self.ticktock = True

    def group(self):
        return self.group

    def name(self):
        return self.name

    def set_text(self, lineno, text):
        pass


class GameOfLifeAnimationGroup:
    def __init__(self, name, colors=(0x080808, 0xC00000), initPattern=None):
        self.tick = [[random.randint(0, 1) for _ in range(64)] for _ in range(32)]
        self.tock = [[random.randint(0, 1) for _ in range(64)] for _ in range(32)]
        if initPattern is not None:
            for y in range(32):
                for x in range(64):
                    self.tick[y][x] = 0
            for x, y in initPattern:
                self.tick[y][x] = 1

        self.palette = displayio.Palette(2)
        self.palette[0] = colors[0]
        self.palette[1] = colors[1]

        self.bitmap = displayio.Bitmap(64, 32, 2)
        self.tilegrid = displayio.TileGrid(
            bitmap=self.bitmap, pixel_shader=self.palette
        )
        self.group = displayio.Group()
        self.group.append(self.tilegrid)

        self.directions = [
            (63, 31),
            (0, 31),
            (1, 31),
            (63, 0),
            (1, 0),
            (63, 1),
            (0, 1),
            (1, 1),
        ]

        self.ticktock = False

    def update_anim(self):
        if self.ticktock:
            for y in range(32):
                for x in range(64):
                    popcount = 0
                    for d in self.directions:
                        popcount = (
                            popcount + self.tick[(y + d[1]) % 32][(x + d[0]) % 64]
                        )
                    if popcount == 2:
                        self.tock[y][x] = self.tick[y][x]
                    elif popcount == 3:
                        self.tock[y][x] = 1
                    else:
                        self.tock[y][x] = 0
            for y in range(32):
                for x in range(64):
                    self.bitmap[x, y] = self.tock[y][x]
            self.ticktock = False
        else:
            for y in range(32):
                for x in range(64):
                    popcount = 0
                    for d in self.directions:
                        popcount = (
                            popcount + self.tock[(y + d[1]) % 32][(x + d[0]) % 64]
                        )
                    if popcount == 2:
                        self.tick[y][x] = self.tock[y][x]
                    elif popcount == 3:
                        self.tick[y][x] = 1
                    else:
                        self.tick[y][x] = 0
            for y in range(32):
                for x in range(64):
                    self.bitmap[x, y] = self.tick[y][x]
            self.ticktock = True

    def group(self):
        return self.group

    def name(self):
        return self.name

    def set_text(self, lineno, text):
        pass


class LinedGroup:
    def __init__(self, name, fontchoice=None, textcolor=0x00A000):
        self.font = terminalio.FONT
        if fontchoice is not None:
            self.font = bitmap_font.load_font(f"fonts/{fontchoice}.bdf")

        self.centered = False

        self.fontheight = self.font.get_bounding_box()[1]
        self.numlines = 32 // self.fontheight
        self.yoffset = 16 - ((self.numlines * self.fontheight) // 2)

        if self.numlines == 0:
            self.numlines = 1

        self.lines = [
            adafruit_display_text.label.Label(
                font=self.font, color=textcolor, text=f"Line {i+1}"
            )
            for i in range(self.numlines)
        ]

        self.group = displayio.Group()
        for i, line in enumerate(self.lines):
            line.x = 0
            line.y = self.yoffset + ((i + 1) * self.fontheight - (self.fontheight // 2))
            self.group.append(line)

        self.name = name

    def update_anim(self):
        pass

    def group(self):
        return self.group

    def name(self):
        return self.name

    def set_text(self, lineno, text):
        if lineno >= len(self.lines) or lineno < 0:
            return  # TODO: should this be a silent error?
        self.lines[lineno].text = text
        if self.centered:
            self.lines[lineno].x = 32 - (self.lines[lineno].width // 2)


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

        self.fliplatch = False

        self.buttonup = None
        self.buttondown = None

        self.processup = False
        self.processdown = False

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
        if (
            self.buttonup is not None
            and self.buttondown is not None
            and not self.processup
            and not self.processdown
        ):
            if not self.buttonup.value:
                time.sleep(0.05)
                if not self.buttonup.value:
                    self.processup = True
                    print("Pressed up value")
            if not self.buttondown.value:
                time.sleep(0.05)
                if not self.buttondown.value:
                    self.processdown = True
                    print("Pressed down value")

    def run_demo_tick(self):
        c = rtc.RTC().datetime
        hr = str(100 + c.tm_hour)[1:]
        mn = str(100 + c.tm_min)[1:]
        sc = str(100 + c.tm_sec)[1:]
        yr = str(c.tm_year)[2:]
        self.demopage_line(0, f"{hr}:{mn}:{sc}")
        self.demopage_line(1, f"{c.tm_mon}/{c.tm_mday}/{yr}")
        if not self.fliplatch:
            if self.processup or self.processdown:
                self.fliplatch = True
                q = 0
                if self.processup:
                    q = 1
                    self.processup = False
                if self.processdown:
                    q = -1
                    self.processdown = False
                idx = 0
                for i, lbl in enumerate(DISPLAY_LIST):
                    if self.displaystate == lbl:
                        idx = i
                        break
                idx = (idx + q) % len(DISPLAY_LIST)
                self.displaynewstate = DISPLAY_LIST[idx]
        else:
            self.fliplatch = False

        return RUN_DEMO_STATE

    def set_rtc(self):
        rsp = requests.get(WTC_URL)
        if rsp.status_code == 200:
            rr = json.loads(rsp.content)
            newtime = datetime.fromisoformat(rr["datetime"])
            rtc.RTC().datetime = newtime.timetuple()
            print(f"New time: {time.localtime()}")
            time.sleep(1)
        self.displaynewstate = DISPLAY_DEMO1
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
                time.sleep(0.0001)

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
        self.setup_GOLscreen()
        self.setup_CAGscreen()
        return SETUP_BOARD_STATE

    def setup_GOLscreen(self):
        golscreen = GameOfLifeAnimationGroup("gol")
        self.allgroups[DISPLAY_GOL] = golscreen

    def setup_CAGscreen(self):
        cagscreen = ChaserAnimationGroup("cag")
        self.allgroups[DISPLAY_CAG] = cagscreen

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
        demoscreen = LinedGroup(DISPLAY_DEMO1, "t0-14-uni", 0x0080D0)
        demoscreen.centered = True
        self.allgroups[DISPLAY_DEMO1] = demoscreen

        for i in range(len(demoscreen.lines)):
            demoscreen.set_text(i, "")

    def demopage_line(self, lineno, text):
        self.allgroups[DISPLAY_DEMO1].set_text(lineno, text)
        self.refresh_screen()

    def setup_board(self):
        print(f"Booting up IHLRGB {IHLRGB_VERSION}")

        self.buttondown = DigitalInOut(board.BUTTON_DOWN)
        self.buttondown.direction = Direction.INPUT
        self.buttondown.pull = Pull.UP
        self.buttonup = DigitalInOut(board.BUTTON_UP)
        self.buttonup.direction = Direction.INPUT
        self.buttonup.pull = Pull.UP

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
