# MiniScButton
#
# By David Hartburn - February 2018
#
# Draws simple buttons and reponds yes/no if clicked
# Buttons are an outline with coloured text

import pygame

# Initialise fonts
pygame.font.init()
Font = pygame.font.Font('freesansbold.ttf', 14)

class miniScButton(object):
	def __init__(self, x, y, w, h, text, borderCol, textCol, highCol, a):
		# Button paramaters: geom = (x, y of top left, w, h)
		self.text=text
		self.x=x
		self.y=y
		self.w=w
		self.h=h
		self.BoundBox=pygame.Rect(x,y,w,h)
		self.borderCol=borderCol
		self.textCol=textCol
		self.highCol=highCol
		self.Border = 3
		self.highlight = 0
		self.active=a
		
	# Handle mouse events	
	def handleEvent(self, eventObj):
		# Is this event mine? Exit quietly if not.
		rtn=0
		# Can not click if not active
		if(self.active==0):
			return 0
		
		# Return codes, 0 not clicked, 1 mouse button down, 2 button up
		if(self.BoundBox.collidepoint(eventObj.pos)):
			if(eventObj.type==pygame.MOUSEBUTTONDOWN):
				self.highlight=1
				rtn=1
			if(eventObj.type==pygame.MOUSEBUTTONUP):
				self.highlight=0
				rtn=2
		return rtn
		
		
	def draw(self, screen):
		# Draw object on screen
		if(self.highlight==1):
			pygame.draw.rect(screen, self.highCol, (self.x,self.y,self.w,self.h))
		pygame.draw.rect(screen, self.borderCol, (self.x,self.y,self.w,self.h), self.Border)
		label = Font.render(self.text, 1, self.textCol)
		labelBox = label.get_rect()
		labelBox.center = int(self.w/2)+self.x, int(self.h/2)+self.y
		screen.blit(label, labelBox)

		if(self.active==0):
			temp = pygame.Surface((self.w+2, self.h+2)).convert()
			temp.fill((50,50,50))
			temp.set_alpha(192)
			screen.blit(temp,(self.x-1,self.y-1))
			#pygame.draw.rect(screen, (50,50,50), (self.x,self.y,self.w,self.h), 10)
