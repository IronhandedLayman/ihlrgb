# SPDX-FileCopyrightText: 2019 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

from os import getenv
import board
import busio
from digitalio import DigitalInOut
import framebufferio
import displayio
import rgbmatrix
import adafruit_display_text.label
import terminalio
import adafruit_requests as requests
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi

TEXT_URL = "http://wifitest.adafruit.com/testwifi/index.html"
JSON_URL = "http://api.coindesk.com/v1/bpi/currentprice/USD.json"


def main():
    setup_board()
    setup_secrets()
    setup_display()
    setup_wifi()
    run_demo()


def setup_board():
    global esp, esp32_cs, esp32_ready, esp32_reset
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    esp32_cs = DigitalInOut(board.ESP_CS)
    esp32_ready = DigitalInOut(board.ESP_BUSY)
    esp32_reset = DigitalInOut(board.ESP_RESET)
    esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
    if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
        print("ESP32 found and in idle mode")
    print("Firmware vers.", str(esp.firmware_version))
    print("MAC addr:", "-".join([str(hex(i))[2:] for i in esp.MAC_address]))


def setup_secrets():
    global secrets
    secrets = {
        "ssid": getenv("CIRCUITPY_WIFI_SSID"),
        "password": getenv("CIRCUITPY_WIFI_PASSWORD"),
    }
    if secrets == {"ssid": None, "password": None}:
        try:
            from secrets import secrets
        except ImportError:
            print("WiFi secrets are kept in settings.toml, please add them there!")
            raise


def setup_display():
    global matrix, display
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
        addr_pins=[board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC, board.MTX_ADDRD],
        clock_pin=board.MTX_CLK,
        latch_pin=board.MTX_LAT,
        output_enable_pin=board.MTX_OE,
    )
    display = framebufferio.FramebufferDisplay(matrix, auto_refresh=False)


def setup_wifi():
    requests.set_socket(socket, esp)
    for ap in esp.scan_networks():
        print("\t%s\t\tRSSI: %d" % (str(ap["ssid"], "utf-8"), ap["rssi"]))

    print("Connecting to AP...")
    while not esp.is_connected:
        try:
            esp.connect_AP(secrets["ssid"], secrets["password"])
        except OSError as e:
            print("could not connect to AP, retrying: ", e)
            continue
    print("Connected to", str(esp.ssid, "utf-8"), "\tRSSI:", esp.rssi)
    print("My IP address is", esp.pretty_ip(esp.ip_address))
    print(
        "IP lookup adafruit.com: %s"
        % esp.pretty_ip(esp.get_host_by_name("adafruit.com"))
    )
    print("Ping google.com: %d ms" % esp.ping("google.com"))


# This function will scoot one label a pixel to the left and send it back to
# the far right if it's gone all the way off screen. This goes in a function
# because we'll do exactly the same thing with line1 and line2 below.
def scroll(line):
    line.x = line.x - 1
    line_width = line.bounding_box[2]
    if line.x < -line_width:
        line.x = display.width


# This function scrolls lines backwards.  Try switching which function is
# called for line2 below!
def reverse_scroll(line):
    line.x = line.x + 1
    line_width = line.bounding_box[2]
    if line.x >= display.width:
        line.x = -line_width


def run_demo():
    print("Fetching text from", TEXT_URL)
    r = requests.get(TEXT_URL)
    print("-" * 40)
    print(r.text)
    print("-" * 40)
    r.close()

    print()
    print("Fetching json from", JSON_URL)
    r = requests.get(JSON_URL)
    print("-" * 40)
    print(r.json())
    print("-" * 40)
    r.close()

    line1 = adafruit_display_text.label.Label(
        terminalio.FONT,
        color=0xFF0000,
        text="This scroller is brought to you by CircuitPython RGBMatrix",
    )
    line1.x = display.width
    line1.y = 8

    line2 = adafruit_display_text.label.Label(
        terminalio.FONT,
        color=0x0080FF,
        text="Hello to all CircuitPython contributors worldwide <3",
    )
    line2.x = display.width
    line2.y = 24

    # Put each line of text into a Group, then show that group.
    g = displayio.Group()
    g.append(line1)
    g.append(line2)
    display.root_group = g

    # You can add more effects in this loop. For instance, maybe you want to set the
    # color of each label to a different value.
    while True:
        scroll(line1)
        scroll(line2)
        # reverse_scroll(line2)
        display.refresh(minimum_frames_per_second=0)


if __name__ == "__main__":
    main()
