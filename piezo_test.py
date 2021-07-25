#!/usr/bin/python

# Piezo buzzer test

import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)

BUZPIN = 36

GPIO.setup(BUZPIN, GPIO.OUT)

GPIO.output(BUZPIN, True)
time.sleep(0.01)
GPIO.output(BUZPIN, False)
