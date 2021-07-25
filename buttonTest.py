#!/usr/bin/python
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BOARD)

# Define button GPIO pins
K1=12
K2=16
K3=18

# Enable buttons as inputs
GPIO.setup(K1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(K2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(K3, GPIO.IN, pull_up_down=GPIO.PUD_UP)

while True:
	print "K1 - " + str(GPIO.input(K1)) + " K2 - " + str(GPIO.input(K2))+" K3 - " + str(GPIO.input(K3))
	
