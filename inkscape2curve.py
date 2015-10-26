#!BPY

""" 
Name: 'Inkscape(.svg)'
Blender: 244
Group: 'Import'
Tooltip: 'Import Inkscape drawing as a curve(s)'
"""

# --------------------------------------------------------------------------
# ***** BEGIN GPL LICENSE BLOCK *****
#
# Copyright (C) 2005-2006 Ari Hayrinen
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****
# --------------------------------------------------------------------------

__author__ = ["Ari Hayrinen"]
__url__ = ("blender", "elysiun", "http://www.opendimension.org/blender3d_en")
__version__ = "0.12"


# svg-import
#Ari Hayrinen 20.12.2006
#ari.hayrinen at gmail.com
"""
Few notes:
- This script imports vector graphics from Inkscape and it is mainly aimed for architectural drawings. 
- This is not full SVG-import script!
- Current implemented commands:M,L,C,c,z. 
- Only direct matrix transformations are implemented

USAGE:
- Copy this file in Blender scripts directory
- Make your drawing in Inkscape
- Convert it to path! (Path - Object to Path)
- Save
- Open Blender and choose File -> Import -> Inkscape2curve

TODO:
- rotate and skew transformations 
- layer support


Changelog:
	- first release
	6.12.2006
	- added matrix transformations
	3.6.2007
	- separete path by default
	- not closing open curves anymore
	- added translate and scale transformations
	4.7.2007
	- fixed open curve's handling (wrong handles)
	3.10.2008
	- removed non-ascii character that prevented script for working 
	  in some environments (Thanks Jean-Denis)
	29.9.2009
	- added explicit conversion from string to float 
	  (did not work with Blender 2.49)	
"""

import Blender
from xml.sax import make_parser
from xml.sax.handler import ContentHandler
from Blender import NMesh, Curve, BezTriple, Object, Window, Mathutils, Draw, BGL
from Blender.Mathutils import *
import re
#import pdb

div = 1							# scale down amount NOT USED
separate_paths = 1					# separate paths?
DEBUG = 0

class SVGHandler(ContentHandler):

	def __init__ (self):

		self.curCommand = 0
		self.pathCommands = {'C':self.C,'c':self.C,'L':self.L,'M':self.M,'z':self.z,'A':self.notImp}
		self.x1loc = {'C':0,'L':0,'M':0} 	# location of x1
		self.x2loc = {'C':1,'L':0,'M':0} 	# location of x2
		self.xloc = {'C':2,'L':0,'M':0,'c':2} 	# location of x
		self.handle = {'C':BezTriple.HandleTypes.FREE,'L':BezTriple.HandleTypes.VECT}
		self.unsupported_commands = ['a','q','v','h','s','t']
		self.errors = []
		
		self.separate = 0		
		self.matrix = Matrix([1,0,0],[0,1,0],[0,0,1]) #identity	
		self.flipMatrix = Matrix([0.01,0,0],[0,-0.01,0],[0,0,1]) #flip y and scale down
		self.matrices = []
		self.matrix_state = []
		
		self.curves = []
		c = Curve.New('svg_imported_')
		self.curves.append(c)
		
		self.firstPoint = 0
		self.firstPointType = 0
		self.latestPoint = 0
		self.latestPointType = 0
		self.absX = 0
		self.absY = 0
		
		self.pathCounter = -1 	# 0 is first path
		self.curveCounter = -1	# 0 is first curve
			
		self.newpath = 0
		
		
		
	def startElement(self, name, attrs):

		if name == 'path':	 
			if self.separate:
				c = Curve.New('svg_imported_')
				self.curves.append(c)
				self.pathCounter = self.pathCounter + 1
				self.curveCounter = -1
				
			self.pathPoints = attrs.get('d',"")
			self.pathId = attrs.get('id',"")
			if DEBUG:
				print 'start elemtent:',self.pathId
			#self.latestPoint = 0

		self.composeMatrix(attrs)
			
	def composeMatrix(self, attrs):
		m = attrs.get('transform',"")
		if m:
			m = m.replace(')','')
			splitted = m.split('(')
			matrixtype = splitted[0]
			mVals = splitted[1].split(',')
			
			if matrixtype.strip() == 'matrix':
				mat = Matrix([float(mVals[0]),float(mVals[2]),float(mVals[4])],[float(mVals[1]),float(mVals[3]),float(mVals[5])],[0,0,1])
				self.matrices.insert(0,mat)						# add matrix to the stack as a first item
				self.matrix_state.append(1)
				
			elif matrixtype.strip() == 'translate':
				mat = Matrix([1.0,0.0,float(mVals[0])],[0.0,1.0,float(mVals[1])],[0.0,0.0,1.0])
				self.matrices.insert(0,mat)						# add matrix to the stack as a first item
				self.matrix_state.append(1)
				
			elif matrixtype.strip() == 'scale':
				mat = Matrix([float(mVals[0]),0.0,0.0],[0.0,float(mVals[1]),0.0],[0.0,0.0,1.0])
				self.matrices.insert(0,mat)						# add matrix to the stack as a first item
				self.matrix_state.append(1)
				
			else:
				print 'sorry ',matrixtype.strip(), 'not implemented!'
				
		else:
			self.matrix_state.append(0)							# not matrix added

	def createVectorList(self,coords):
		vectors = []
		j = 0		
		count = len(coords)/2

		for i in range(count):
			vectors.append(self.makeTransformedVector(coords[j],coords[j+1],0.0))	
			j = j + 2
		return vectors

	def makeTransformedVector(self,x,y,z):
		v = Vector(float(x),float(y),1.0)
		if len(self.matrices):
			for m in self.matrices:
				v = m * v
		v = v * self.flipMatrix			# flip y-axis
		return v

	def makeAbsolute(self,coords,x,y):
		c = float(coords[0]) + float(x), float(coords[1]) + float(y), float(coords[2]) + float(x),float(coords[3]) + float(y), float(coords[4]) + float(x),float(coords[5]) + float(y)
			
		return c
	
	
	
	def comparePoints(self,last,first):
		if DEBUG:
			print 'compare points'
			print 'firstpoint',self.firstPointType,self.firstPoint
			print 'latestpoint' ,self.latestPointType, self.latestPoint
			
		lpt = self.latestPointType
		fpt = self.firstPointType
		
		if(first[self.xloc[fpt]][0] == last[self.xloc[lpt]][0]):
			if(first[self.xloc[fpt]][1] == last[self.xloc[lpt]][1]):
				return 1
		else:
			return 0
			
			
#***********************************************************************************************************
	# functions for different types
#***********************************************************************************************************

	def notImp(self, coords):
		print 'not implemented'

	def M(self,coords):
		if self.latestPoint and self.firstPoint:					# finalise previous curve
			self.finalize()
		
		co = coords[0]
		bt1 = BezTriple.New(co[0],co[1],0.0, co[0],co[1],0.0, co[0],co[1],0.0)
		self.cu = self.curves[self.pathCounter].appendNurb(bt1)
		
		self.latestPoint = 0
		self.newpath = 1
		self.curveCounter = self.curveCounter + 1
		self.firstPoint = coords
		self.latestPoint = coords
		#self.latestPointType = 'L'


		
	def L(self,coords):
		if self.newpath:
			self.firstPointType = 'L'
			self.newpath = 0
			
		else:		
			co = self.latestPoint
			lpt = self.latestPointType
			bt = BezTriple.New(co[self.x2loc[lpt]][0],co[self.x2loc[lpt]][1],0.0, co[self.xloc[lpt]][0], co[self.xloc[lpt]][1],0.0, 0.0,0.0,0.0)
			bt.handleTypes= (self.handle[lpt],BezTriple.HandleTypes.VECT)
			self.cu.append(bt)

		self.latestPoint = coords
		self.latestPointType = 'L'


		
	def C(self,coords):
		if self.newpath:
	
			vec = Vector(coords[0][0], coords[0][1], 0.0)
			p = [vec, vec , Vector(self.firstPoint[0][0], self.firstPoint[0][1],0.0)]

			self.firstPoint = p						# add handles to the first point
			self.firstPointType = 'C'
			self.newpath = 0
			
		else:
			if(coords == []):
				coords = [self.latestPoint[2]]
				
			cc = coords[0]	 
 			co = self.latestPoint
			lpt = self.latestPointType
			bt = BezTriple.New(co[self.x2loc[lpt]][0],co[self.x2loc[lpt]][1],0.0, co[self.xloc[lpt]][0], co[self.xloc[lpt]][1],0.0, cc[0],cc[1],0.0)

			bt.handleTypes= (self.handle[lpt],BezTriple.HandleTypes.FREE)
			self.cu.append(bt)
			
		if(len(coords) != 1):
			self.latestPoint = coords
		self.latestPointType = 'C'
	
	

	def z(self,coords = 0):								# we are closing, so update first point's handles
		self.updateFirstPoint(self.latestPoint)	 
		self.curves[self.pathCounter][self.curveCounter].setFlagU(1)
		self.latestPoint = 0						# set to zero so that next M won't close again



	def updateFirstPoint(self, coords, cyclic=1):
	
		lp = coords
		fp = self.firstPoint	
		lpt = self.latestPointType
		fpt = self.firstPointType
		p = self.curves[self.pathCounter][self.curveCounter][0]
		
		if DEBUG:
			print 'updatefirstpoint, coords:',lpt,coords
			print 'firstpoint',fpt,fp
			#pdb.set_trace()

		if cyclic:
			bt = [lp[self.x2loc[lpt]][0], lp[self.x2loc[lpt]][1],0.0, p.vec[1][0],p.vec[1][1], 0.0, fp[self.x1loc[lpt]][0],fp[self.x1loc[lpt]][1],0.0]
			self.curves[self.pathCounter][self.curveCounter][0].handleTypes= (self.handle[lpt],self.handle[fpt])
			self.curves[self.pathCounter].setControlPoint(self.curveCounter,0,bt)	
		else:
			bt = [lp[self.x2loc[lpt]][0], lp[self.x2loc[lpt]][1],0.0, p.vec[1][0],p.vec[1][1], 0.0, fp[self.x1loc[lpt]][0],fp[self.x1loc[lpt]][1],0.0]
			self.curves[self.pathCounter][self.curveCounter][0].handleTypes= (BezTriple.HandleTypes.VECT,self.handle[fpt])
			self.curves[self.pathCounter].setControlPoint(self.curveCounter,0,bt)			 	



	def microParse(self,coords):
		
		p = coords[0].strip()

		
		if self.curCommand:				
			if self.curCommand == 'c':
				coords = self.makeAbsolute(coords, self.absX, self.absY)

			vectorList = self.createVectorList(coords)	
			apply(self.pathCommands[self.curCommand],(vectorList,))
			
			if self.curCommand != 'z':
				# save absolute x,y before transformations
				self.absX = coords[self.xloc[self.curCommand]*2]		# multiply by 2 because not a vector list
				self.absY = coords[self.xloc[self.curCommand]*2+1]			
			self.curCommand = 0		
			
		if p in self.pathCommands:	
			self.curCommand = p.encode('ascii')


	
	def endElement(self, name):

		if DEBUG:
			print 'end element', name, self.pathCounter
		
		cds = [] # list of coordinates
		if name == 'path' :
			m = re.split('([a|A-z|Z])', self.pathPoints)  	# split by commands (letters)
			for l in m:										# every other round there is only path command in cds
				cds = []
				l = l.replace('-',' -')						# add space to minus signs and use space as a delimiter
				l = l.replace(',',' ')	
				l = l.replace('  ',' ')
				l = l.strip()						
				splitted = l.split(' ')						# get individual coords
								
				for c in range(len(splitted)):
					cds.append(splitted[c].strip())
				self.microParse(cds)						# do thing for every node	
			
			if self.latestPoint:								# if last curve is not closed then finalize it
				self.finalize()


		if len(self.matrix_state): 
			matrix_state = self.matrix_state.pop()			# if this element added matrix then ...
			if matrix_state:
				m = self.matrices.pop(0)					# ... pop out first matrix



	def finalize(self):

		if DEBUG:
			print 'finalising element', self.pathCounter
					
		if self.comparePoints(self.latestPoint,self.firstPoint):	# if last and first point are the same, then close
			self.z()
		else :														# otherwise ...	
			lpt = self.latestPointType
			vectorList = [self.latestPoint[self.xloc[lpt]]]							
			apply(self.pathCommands[self.latestPointType],(vectorList,))	# ... add the last point and
			self.updateFirstPoint(self.latestPoint,0)					# set the handles of the first point
			
		self.latestPoint = 0										# set to zero so that next M won't finalise again
				
				
				
def my_function(filename):

	parser = make_parser()   
	curHandler = SVGHandler()
	parser.setContentHandler(curHandler)
	curHandler.separate = separate_paths
	print 'Inkscape2curve-script started'
	
	parser.parse(open(filename))
	
	for c in curHandler.curves:
		name = c.getName()
		objekti = Object.New ('Curve')
		c.update()

		objekti.link (c)
		cur = Blender.Scene.GetCurrent ()
		cur.objects.link (objekti)
		
	print 'Done!'	
	Blender.Redraw()


#************************************************************************************************
#main
#************************************************************************************************

# Check if full version of python is installed:
try:
	import os
	pythonFull = True
except ImportError:
	pythonFull = False

if not pythonFull:
	stop = Draw.PupMenu("ERROR!%t|You need full Python Install! %x1")


# save Editmode state so we can restore it afterwards
editmode = Window.EditMode()
# if user is in editmode, we have to change to objectmode  
if editmode: Window.EditMode(0) 

Blender.Window.FileSelector (my_function, 'OPEN .SVG')

