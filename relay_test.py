#!/usr/bin/python

# Test 4 channel relay
# Connections for relay board
# GND to GND
# Vcc to Pi 5v
# IN1-4 to Pi GPIO pins

# Setting pin to False is on and True is off

import time
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BOARD)

import os
import sys
import termios
import tty

RELAY1 = 32

print "Hello world, relay is connected to GPIO "+str(RELAY1);

# Init relay and make sure all are off
GPIO.setup(RELAY1, GPIO.OUT);
GPIO.output(RELAY1, True);

# **************************
def getKey():
   # Detect keypress, taken from 
   # http://www.raspberrypi.org/forums/viewtopic.php?f=32&t=16882
   fd = sys.stdin.fileno()
   old = termios.tcgetattr(fd)
   new = termios.tcgetattr(fd)
   new[3] = new[3] & ~termios.ICANON & ~termios.ECHO
   new[6][termios.VMIN] = 1
   new[6][termios.VTIME] = 0
   termios.tcsetattr(fd, termios.TCSANOW, new)
   key = None
   try:
      key = os.read(fd, 3)
   finally:
      termios.tcsetattr(fd, termios.TCSAFLUSH, old)
   return key

# **************************
# Loop waiting for key commands
# 0 - relay 1 off
# 1 - relay 1 on

rout1=True

while True:
	#inkey = raw_input("");
	inkey = str(getKey());
	print "Input was "+inkey;
	if inkey == "1":
  		# Turn on relay
		rout1=False
		print "On"
	elif inkey == "0":
		# Turn off relay
		rout1=True
		print "Off"
	elif inkey == "q":
		# Quit
		break
	GPIO.output(RELAY1, rout1)
	time.sleep(0.25)

print "Done"
GPIO.cleanup()	
	
# ****************************************************

