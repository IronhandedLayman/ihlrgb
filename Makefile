devenv: requirements.devenv.txt
	python -m venv .
	source bin/activate
	pip install -r requirements.devenv.txt

upload: *.py requirements.circup.txt
	circup install -r requirements.circup.txt
	cp *.py /Volumes/CIRCUITPY/
	cp settings.toml /Volumes/CIRCUITPY/

uplink:
	screen /dev/tty.usbmodem2112401 115200

.PHONY: devenv upload
