Matrix portal code project
--------------------------

This is a first project with the AdaFruit MatrixPortal M4 ESP8266 board that
interfaces with the RGB display. Initially this project follows the wonderful
instructions at
https://learn.adafruit.com/rgb-led-matrices-matrix-panels-with-circuitpython
but then software development habits kicked in and I started to systematize the
way I deploy to the device.

# Hardware ingredients

You will obviously need a MatrixPortal and an RGB Matrix. I am using the MatrixPortal M4 from AdaFruit with the 64x32x4 glexible RGB LED Matrix. You may also want to print a case: the STL files for that are at https://www.thingiverse.com/thing:5793070 (my printer can't do it all at once so I have to print both sides and put together) and you may want some other niceities such as a power supply and/or a USB A to C cable.

# Development Setup:

* Populate
* Setup your board with the hardware configuration at https://learn.adafruit.com/rgb-led-matrices-matrix-panels-with-circuitpython/prep-the-matrixportal
* run `make devenv` to set up the initial build environment
* hook up your board to the computer using a USB A to C cable
* run `make upload` to upload new files to the board
* run `make uplink` to start a serial connection to the board for testing
