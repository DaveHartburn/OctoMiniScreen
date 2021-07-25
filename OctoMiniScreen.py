#!/usr/bin/env python

__author__ = "David Hartburn"
__license__ = "Simplified BSD 2-Clause License"

# OctoPi small screen controller, used to perform customisable common
# operations from a small touch screen, typically 3-4". TouchUI does not
# display very well on these screens, use a bigger screen if you want full
# functionality.
#
# Written for a Waveshare 32B, a cheap 3.2" display
#
# A lot of credit goes to Jonas Lorander's OctoPiPanel, which was used as a
# base and inspiration for this project. This excellent utility was not
# customizable, but I may look at merging in my version in the future.
# https://github.com/jonaslorander/OctoPiPanel
#
# API documentation at http://docs.octoprint.org/en/master/api/

# To Do
# Act on GPIO buttons
#   - Power relay
#   - Stop
#   - LEDs
#   - Start print button
#   - bounce delay on multi control
#   - Pause status / not connected error
#		
# Use own functions for all get and post
# Make debugging output (Debug in config)

import os
import getpass
import numpy
#import sys


import pygame
import requests
import json
#import platform
import time
#import subprocess
#from pygame.locals import *
#from collections import deque
from ConfigParser import RawConfigParser
from miniScButton import miniScButton
from socket import error as SocketError
import errno
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BOARD)

# Button data structure
#  format="soft"	       A soft 'on screen' button
#  type - static | toggle      Toggle text changes
#  label                       The current label display, or constant for static
#  toggleOpts                  The list of possible toggle options
#  currentState                Which state is it currently in (for toggles)?
#  command		       Command to execute
#  toggleCmds		       The list of possible toggle commands
#  buttonObj		       The button object - miniScButton
#  visible		       Visibility property a(always),p(not when printing),o(not when no octoprint)

# GPIO button data structure
#  format="hard"	       A hardware button
#  label		       Only used for debugging
#  type - static | toggle      Toggle text changes
#  command		       Command to execute
#  pin			       GPIO pin, only used for GPIO buttons

# Init fonts
pygame.font.init()
statusFont = pygame.font.Font('freesansbold.ttf',14)
saverFont = pygame.font.Font('freesansbold.ttf',24)

class OctoMiniScreen():
	# Main OctoMiniScreen Class

	# Define class global variables
	configFile = "/home/pi/OctoMiniScreen/octominiscreen.cfg"

	# Maximum number of characters to show for the filename.
	# Avoids text running into the button
	printTextWidth = 14

	# Read the config file
	cfg = RawConfigParser()
	cfg.readfp(open(configFile, "r"))

	OctoURL = cfg.get('settings', 'octourl')
	APIkey = cfg.get('settings', 'apikey')
	Width = cfg.getint('settings', 'width')
	Height = cfg.getint('settings', 'height')
	Pointer = cfg.get('settings', 'show_pointer')
	BPR = cfg.getint('settings', 'buttons_per_row')
	screenSave = cfg.getint('settings', 'screen_save')*1000
	screenFile = cfg.get('settings', 'screen_save_cont')
	statRefresh = cfg.getint('settings', 'status_refresh')
	Piezo = cfg.get('settings', 'piezo')
	if(Piezo=="yes"):
		Piezo_pin=cfg.getint('settings', 'piezo_pin')
		Piezo_duration=cfg.getfloat('settings', 'piezo_duration')

	click_delay = cfg.getint('settings', 'click_delay')
	
	butBorder = (160,215,0)
	butText = (100,200,200)
	butHighlight = (40, 80, 160)
	background = (0,0,64)
	
	# Screen saver text starting position
	screenSavePos = [10,10]
	screenSaveLimit = [Width*0.75,Height*0.75]
	# How many seconds to wait before next moving
	screenSaveSpeed = 0.1
	# Direction of screen saver text
	screenSaveDirection = 0
	# Colours
	fileColour=(220,60,0)
	progColour=(60,220,100)
	
	# Time of next screen saver movement
	nextSSaveMove=0
	# Time of permitted next click - used to avoid accidents
	nextClick=0
	
	
	statusSize=40	# How much space to dedicate to a status bar

	# URLs to use
	urls = {'base': OctoURL,
		'version': OctoURL + '/api/version',
		'connection': OctoURL + '/api/connection',
		'printer': OctoURL + '/api/printer',
		'command': OctoURL + '/api/printer/command',
		'job': OctoURL + '/api/job'
		}
	APIheader = {'X-Api-Key': APIkey, 'content-type': 'application/json'}
	
	# Is Octopi running. 0=Yes OK, 1=yes but error, 2=Critical - not running
	# 3=connected no printer, 4=printing
	# Start with -1 to force a state change on startup
	octoPstate = -1
	vQuit = False
	
	# Report printer progress - note this is a string
	vProgress = "0"
	vProgMini = "0"
	
	# Show the connection button? 0=no, 1=connect, 2=pause, 3=resume
	vShowConnect = 1

	# Process the buttons
	sections=cfg.sections()
	Buttons = []
	GPIObuttons = []
	for s in sections:
		#print "Section found: " + s
		if (s.find('button')>-1):
			items = cfg.items(s)
			vType = ""
			newButton = {}
			newButton['format']="soft"
			for i in items:
				#print "    Item: " + i[0] + "=" + i[1]
				if(i[0]=="type"):
					vType=i[1]
					newButton['type']=i[1]
				elif(i[0]=="label"):
					if(newButton['type']=="static"):
						newButton['label']=i[1]
					elif(newButton['type']=="toggle"):
						newButton['toggleOpts']=i[1].split('|')
						newButton['label']=newButton['toggleOpts'][0]
						newButton['currentState']=0
				elif(i[0]=="command"):
					cmdIn=i[1].replace('\n','');
					print("Found command", cmdIn);
					if(newButton['type']=="static"):
						newButton['command']=cmdIn
					elif(newButton['type']=="toggle"):
						newButton['toggleCmds']=cmdIn.split('|')
						newButton['command']=newButton['toggleCmds'][0]
				elif(i[0]=="visible"):
					newButton['visible']=i[1]
			# End of processing items
			Buttons.append(newButton)
		if (s.find('gpio')>-1):
			items = cfg.items(s)
			vType = ""
			newButton = {}
			newButton['format']="hard"
			for i in items:
				if(i[0]=="type"):
					vType=i[1]
					newButton['type']=i[1]
				elif(i[0]=="command"):
					if(newButton['type']=="static"):
						newButton['command']=i[1]
					elif(newButton['type']=="toggle"):
						newButton['toggleCmds']=i[1].split('|')
						newButton['command']=newButton['toggleCmds'][0]
						newButton['currentState']=0
				elif(i[0]=="pin"):
					newButton['pin']=int(i[1])
					newButton['label']="GPIO_PIN"+i[1]
			# End of processing items
			GPIObuttons.append(newButton)		  
	# End of sections for loop, buttons processed

	
		
	def __init__(self, caption="OctoMiniScreen"):
		# *** Learn about __init__ and remove this comment!
		print "Init OctoMiniScreen"
		
		# **** Calculate button geometry
		
		# If root, run full screen - assuming this is on a pi
		# otherwise run as normal popup window
		if(getpass.getuser()=="root"):
			os.putenv('SDL_VIDEODRIVER', 'fbcon')
			os.putenv('SDL_FBDEV'      , '/dev/fb1')
			os.putenv('SDL_MOUSEDRV', 'TSLIB')
			os.putenv('SDL_MOUSEDEV', '/dev/input/touchscreen')
		else:
			# Always show the pointer if not root
			self.Pointer="yes"
			
		# Start pygame and set up screen
		pygame.init()
		
		# Should we show mouse pointer?
		if(self.Pointer=="yes"):
			pygame.mouse.set_visible(True)
		else:
			pygame.mouse.set_visible(False)
			
		# Open window and start
		self.screen = pygame.display.set_mode( (self.Width, self.Height) )
		
		# Init buttons
		# Calculate size
		Padding=6
		bWidth=int((self.Width-(Padding*self.BPR))/self.BPR)-1
		bRows=-(-len(self.Buttons)//self.BPR)
		print "Length={0}, Buttons per row={1}, required rows = {2}".format(len(self.Buttons),self.BPR,bRows)
		bHeight=int((self.Height-self.statusSize-(Padding*bRows))/bRows)
		
		# Define the buttons
		vRow=0
		vCol=0
		for b in self.Buttons:
			print "Defining button " + b['label']
			newButton=miniScButton(((bWidth+Padding)*vCol)+Padding, ((bHeight+Padding)*vRow)+Padding, bWidth, bHeight, b['label'], self.butBorder, self.butText, self.butHighlight, 1)
			b['buttonObj']=newButton
			vCol=vCol+1
			if(vCol==self.BPR):
				vCol=0
				vRow=vRow+1
		
		# Set up the connect button, though we might not draw it
		self.connectButton = miniScButton(self.Width-85, self.Height-self.statusSize+4, 80, self.statusSize-8, "Connect", self.butBorder, self.butText, self.butHighlight, 1)
		
		# Set up GPIO buttons
		for b in self.GPIObuttons:
			print "Defining button GPIO" + str(b['pin'])
			GPIO.setup(b['pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
		
		# And the piezo buzzer
		if(self.Piezo=="yes"):
			GPIO.setup(self.Piezo_pin, GPIO.OUT)
			
		# Set last active timer, used for screen saver
		self.lastActive = pygame.time.get_ticks()
		self.screenSaveOn = False
		
		# Last status used for status updates
		self.lastStatusTime=0
		
		print "Init complete"

	def Start(self):
		# Starting panel
		print "Starting OctoMiniScreen"


		# Main loop
		while not self.vQuit:
			# Handle events
			self.handleEvent()
			
			# Get the Octoprint server status
			if(pygame.time.get_ticks()>(self.lastStatusTime+self.statRefresh)):
				# Reset check time
				self.lastStatusTime=pygame.time.get_ticks()
				s = self.getOctoStatus()
				#print "Return from status: " + str(s)
				
				# Have we changed state?
				if(s != self.octoPstate):
					self.octoPstate=s
					# Update button visibility
					for b in self.Buttons:
						if((self.octoPstate>=1 and self.octoPstate<=3) and (b['visible']=='o' or b['visible']=='p')):
							b['buttonObj'].active=0
						elif(self.octoPstate==4 and b['visible']=='p'):
							b['buttonObj'].active=0
						elif(self.octoPstate==5 and (b['visible']=='o' or b['visible']=='p')):
							# Show o and p buttons when paused
							b['buttonObj'].active=1
						else:
							b['buttonObj'].active=1
			
			# Do we show the screen saver?
			if(self.lastActive+self.screenSave < pygame.time.get_ticks()):
				self.screenSaveOn = True
				
			# Draw the screen
			self.draw()
		print "Application quit, bye bye"	
	
	def draw(self):
		if(self.screenSaveOn):
			# Can't control the backlight with the waveshare screen, just show black
			self.screen.fill( [0,0,0] )
			# If OctoPrint is connected, show data on the screen saver
			self.ssaveData()
			
		else:
			# Set background
			self.screen.fill( [0, 0, 64] )

			# Show buttons
			for b in self.Buttons:
				b['buttonObj'].draw(self.screen)

			# Show status bar

			if(self.octoPstate==0):
				# Octo print running fine, show printer/job status
				statLine = statusFont.render("Octoprint running...", 1, (0,200,0))
			elif(self.octoPstate==1):
				statLine = statusFont.render("Error connecting to Octoprint", 1, (200,130,0))
			elif(self.octoPstate==2):
				statLine = statusFont.render("Error: Octoprint not running", 1, (200,0,0))
			elif(self.octoPstate==3):
				statLine = statusFont.render("Printer not connected", 1, (200,130,0))
			elif(self.octoPstate==4):
				statLine = statusFont.render("Printing: "+self.vProgress, 1, (0,200,0))
			elif(self.octoPstate==5):
				statLine = statusFont.render("Paused: "+self.vProgress, 1, (0,200,0))
			elif(self.octoPstate==6):
				statLine = statusFont.render("Pausing......", 1, (0,200,0))
			elif(self.octoPstate==7):
				statLine = statusFont.render("Ready: "+self.vProgress, 1, (0,200,0))
			else:
				statLine = statusFont.render("Unknown state!", 1, (200,130,0))
			self.screen.blit(statLine, (5,(self.Height-self.statusSize)+10))

			if(self.vShowConnect>0):
				self.connectButton.draw(self.screen)
			
		pygame.display.update()
	
	def ssaveData(self):
		# Only show screen saver if OctoPrint is running
		if(self.octoPstate==0 or self.octoPstate>=4):
			try:
				f=open(self.screenFile, "r")
				# File exists, should be one line
				fstr=f.read()
				f.close()
			except IOError:
				fstr=""
			fileLine = saverFont.render(fstr, 1, self.fileColour)
			self.screen.blit(fileLine, (self.screenSavePos[0],self.screenSavePos[1]))
			
			# If the printer is printing, show a status line
			if(self.octoPstate==4):
				progLine = saverFont.render(self.vProgMini, 1, self.progColour)
				self.screen.blit(progLine, (self.screenSavePos[0],self.screenSavePos[1]+24))			

			# Do we need to move the cursor?
			if(self.nextSSaveMove<time.clock()) :
			

				#Move the cursor for next time
				# Direction: 0=Down,1=right,2=up,3=left
				if(self.screenSaveDirection==0):
					# Down - y++
					self.screenSavePos[1]+=1
					if(self.screenSavePos[1]>self.screenSaveLimit[1]):
						self.screenSaveDirection=1
				if(self.screenSaveDirection==1):
					# Right - x++
					self.screenSavePos[0]+=1
					if(self.screenSavePos[0]>self.screenSaveLimit[0]):
						self.screenSaveDirection=2
				if(self.screenSaveDirection==2):
					# Up - y--
					self.screenSavePos[1]-=1
					if(self.screenSavePos[1]<10):
						self.screenSaveDirection=3
				if(self.screenSaveDirection==3):
					# Left - x--
					self.screenSavePos[0]-=1
					if(self.screenSavePos[0]<10):
						self.screenSaveDirection=0
				self.nextSSaveMove+=self.screenSaveSpeed

		
			
	# Events to handle:
	#  MOUSEBUTTONDOWN pos,button
	#  MOUSEBUTTONUP pos,button
	def handleEvent(self):
		# Handle events
		
		# Check for pygame events
		
		for event in pygame.event.get():
			if (event.type==pygame.QUIT):
				self.vQuit=True
			elif (event.type==pygame.MOUSEBUTTONDOWN or event.type==pygame.MOUSEBUTTONUP):
				# First click with screensaver on removes it
				if(self.screenSaveOn):
					self.screenSaveOn = False
				else:
					#Ignore clicks if insufficient time has passed since last one
					timeNow=pygame.time.get_ticks()
					print("Time now = "+str(timeNow)+" next click="+str(self.nextClick))
					if(timeNow>self.nextClick):
						print "Fine, allowing click"
						# Mousebutton change, test all buttons
						for b in self.Buttons:
							if(b['buttonObj'].handleEvent(event)==2):
								# Button has been clicked
								self.handleClick(b)
								# Reset the click timer
								self.nextClick=timeNow+self.click_delay

						# Has the connect button been clicked?
						if(self.vShowConnect>0):
							if(self.connectButton.handleEvent(event)==2):
								# Yes, beep it
								if(self.Piezo=="yes"):
									self.piezoChirp()
								if(self.vShowConnect==1):
									self.connectPrinter()
								elif(self.vShowConnect==2):
									self.pausePrinter()
								elif(self.vShowConnect==3):
									self.resumePrinter()
								elif(self.vShowConnect==4):
									self.printFile()
								# Reset the click timer
								self.nextClick=timeNow+self.click_delay
						
					else:
						print "Too quick, just wait"
				# Reset the last active timer
				self.lastActive = pygame.time.get_ticks()
				
		# End of pygame events
		
		# Check for GPIO events (pull up so 0 = press)
		for b in self.GPIObuttons:
			if(GPIO.input(b['pin'])==0):
				print "Button press on pin " + str(b['pin'])
				self.handleClick(b)
				# Delay to avoid switch bounce
				time.sleep(0.5)
						
		
				
	# Handle Mouse Click
	def handleClick(self, cButton):
		# Button has been clicked, toggle if needed and execute command
		
		if(self.Piezo=="yes"):
			self.piezoChirp()
			
		print cButton['label'] + " clicked"
		eCmd = cButton['command']
		# Deal with toggle buttons
		if(cButton['type']=="toggle"):
			l=len(cButton['toggleCmds'])
			cButton['currentState']+=1
			if(cButton['currentState']==l):
				cButton['currentState']=0
			if(cButton['format']=="soft"):
				cButton['label']=cButton['toggleOpts'][cButton['currentState']]
				cButton['buttonObj'].text=cButton['label']
			cButton['command']=cButton['toggleCmds'][cButton['currentState']]
			
		
		# Break up command to find type
		print "  Executing command " + eCmd
		sp=eCmd.split(':',1)
		if(len(sp)==0):
			print "Error: Can not parse this command:" + sp
			return
		# What type of command is this?
		if(sp[0]=="GCODE"):
			self.executeGcode(sp[1])
		elif(sp[0]=="API"):
			self.executeAPIcommand(sp[1])
		elif(sp[0]=="URL"):
			self.visitURL(sp[1])
		else:
			print "No method to handle command type: " + sp[0]
			
	def getAPIrequest(self, url=None):
		#print "Getting request - " + url
		try:
			response = requests.get(url, headers=self.APIheader)
			return response
		except requests.exceptions.ConnectionError as e:
			print "Connection error ({0}): {1}".format(e.errno, e.strerror)
			return None
				
	def postAPIrequest(self, url=None, payload=None):
		if(payload is None):
			try:
				print "  No payload, just call URL"
				response = requests.post(url, headers=self.APIheader)
				print "  Post response was "+str(response.status_code)
				return response
			except requests.exceptions.ConnectionError as e:
				print "Connection error ({0}): {1}".format(e.errno, e.strerror)
				return None
		else:
			print "Posting payload "+payload+" to " + url
			try:
				response = requests.post(url, json=json.loads(payload), headers=self.APIheader)
				print "  Post response was "+str(response.status_code)
				return response
			except requests.exceptions.ConnectionError as e:
				print "Connection error ({0}): {1}".format(e.errno, e.strerror)
				return None
				
	def getOctoStatus(self):
		# Is Octopi running. 0=Yes OK, 1=yes but error, 2=Critical - not running
		# 3=connected no printer, 4=printing, 5=paused, 6=pausing
		try:
			r = requests.get(self.urls['version'], headers=self.APIheader)
			#print "Printer status code="+str(r.status_code)
			if (r.status_code==200):
				# We are up and running, what about the connection status?
				printResp = self.getAPIrequest(self.urls['connection'])
				#print "Printer connection status is "+str(printResp.status_code)
				if(printResp.status_code==200):
					rj = printResp.json()
					vState=rj["current"]["state"]
					#print "State="+vState
					if(vState=="Operational"):
						# Got a printer, good to go
						self.vShowConnect = 0
						i = self.getFileInfo();
						if(i==7):
							# There is a file loaded but we are not printing
							# Show a print button
							self.changeConnectButton(4)
						return i
					elif(vState=="Printing"):
						# Show pause
						self.changeConnectButton(2)
						self.getPrintProgress()
						return 4
					elif(vState=="Paused"):
						# Show resume
						self.changeConnectButton(3)
						return 5
					elif(vState=="Pausing"):
						# Report pausing, remove button
						self.vShowConnect = 0
						return 6
				
				# No printer found
				if(self.vShowConnect!=1):
					# Show the connect button
					self.changeConnectButton(1)
				return 3
			else:
				# Some sort of error, don't care what
				return 1
		except requests.exceptions.ConnectionError as e:
			print "Connection error ({0}): {1}".format(e.errno, e.strerror)
			return 2

	def changeConnectButton(self, newState):
		# Change the connect button to show connect, pause or resume
		self.vShowConnect=newState
		if(self.vShowConnect==1):
			self.connectButton.text="Connect"
		elif(self.vShowConnect==2):
			self.connectButton.text="Pause"
		elif(self.vShowConnect==3):
			self.connectButton.text="Resume"
		elif(self.vShowConnect==4):
			self.connectButton.text="Print"
	
	def getPrintProgress(self):
		# Call printer job to get printer progress
		try:
			r = requests.get(self.urls['job'], headers=self.APIheader)
			if(r.status_code==200):
				rj = r.json()
				#print "Progress="+str(rj["progress"]["completion"])
				if(rj["progress"]["completion"]):
					p = int(rj["progress"]["completion"])
				else:
					p = 0
				f = rj["job"]["file"]["name"]
				if(len(f)>self.printTextWidth) :
					self.vProgress=f[:self.printTextWidth]+"... "+str(p)+"%"
				else:
					self.vProgress=f+" - "+str(p)+"%"
				self.vProgMini=str(p)+"%"
			else:
				# An error, lets go with 0%
				self.vProgress="print job unknown!"
				self.vProgMini="??%"
				
		except requests.exceptions.ConnectionError as e:
			print "Connection error ({0}): {1}".format(e.errno, e.strerror)
			return 2
	
	def getFileInfo(self):
		# Called when not printing. If a file is loaded then show a print button
		try:
			r = requests.get(self.urls['job'], headers=self.APIheader)
			if(r.status_code==200):
				rj = r.json()
				f = rj["job"]["file"]["name"]
				#print "File="+str(f)
				if(str(f)=="None"):
					# Nothing to print
					#print " No file to print"
					return 0
				else:
					# We have a file, show a print button
					if(len(f)>self.printTextWidth) :
						self.vProgress=f[:self.printTextWidth+6]+"..."
					else:
						self.vProgress=f
					return 7
					
					
			else:
				# An error, lets go with 0%
				self.vProgress="FileInfo error"
				
		except requests.exceptions.ConnectionError as e:
			print "Connection error ({0}): {1}".format(e.errno, e.strerror)
			return 0
		# Should not reach here
		return 0
		
			
	def connectPrinter(self):
		# Connect to the default printer using defaults
		r = requests.post(self.urls['connection'], json={"command": "connect"},headers=self.APIheader)	
		print "  Connecting to printer, status code = " + str(r.status_code)
		
	def pausePrinter(self):
		# Pause the printer
		self.postAPIrequest(self.urls['job'], '{"command": "pause", "action": "pause"}')
		
	def resumePrinter(self):
		# Resume printing
		self.postAPIrequest(self.urls['job'], '{"command": "pause", "action": "resume"}')
		
	def printFile(self):
		# Start a print job
		self.postAPIrequest(self.urls['job'], '{"command": "start"}')
	
	def togglePower(self):
		# Toggle the printer power supply
		r = requests.post(self.OctoURL+'/api/plugin/psucontrol', json={"command":"togglePSU"},headers=self.APIheader)
		print "  Toggle printer PSU, status code = " + str(r.status_code)
		
	def executeGcode(self, gcode):
		print "Executing gcode "+gcode
		# Break apart commands, reassemble with a ',' and wrap commands in quotes
		tmpList=gcode.split(';')
		# Sending list of commands failed, do it sequentially
		for i in tmpList:
			r = requests.post(self.urls['command'], json={"command": i}, headers=self.APIheader)
			print "Sent GCODE "+i+", response status code = "+str(r.status_code)		
		
	def executeAPIcommand(self, apicmd):
		print "Executing API command "+apicmd
		# Break apart commands, split with a ;
		tmpList=apicmd.split(';')
		for cmd in tmpList:
			# Commands are in the format: url{json}
			# break apart. Test to see if it does have the {} section
			cparts=cmd.split('{',1)
			if (not cparts):
				print "Does have a bracket"
				# Stick the bracket back
				cparts[1]='{'+cparts[1]
				print "  Sending "+cparts[1]+" to URL "+cparts[0]
				r = self.postAPIrequest(self.OctoURL+cparts[0], cparts[1])
			else:
				print "Does not have a bracket"
				print "  Sending no params to to URL "+cmd
				r = self.postAPIrequest(self.OctoURL+cmd)
				
	def visitURL(self, url=None):
		if(url is None):
			print "No URL supplied"
			return None
		else:
			print "Visiting URL: "+url
			response = requests.get(url)
			print "  Post response was "+str(response.status_code)
			return response
			
	def piezoChirp(self):
		GPIO.output(self.Piezo_pin, True)
		time.sleep(self.Piezo_duration)
		GPIO.output(self.Piezo_pin, False)

# End of OctoMiniScreen Class



if __name__ == '__main__':
	oms = OctoMiniScreen("OctoMiniScreen");
	oms.Start()
	

