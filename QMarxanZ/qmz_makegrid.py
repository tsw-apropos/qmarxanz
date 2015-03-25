"""
# -*- coding: utf-8 -*-
#
# ========================================================
# 
# Purpose: Create a square or hexagon grid for use with Marxan
# Author: Trevor Wiens
# Copyright: Apropos Information Systems Inc.
# Date: 2014-10-01
# License: GPL2 
# 
# licensed under the terms of GNU GPL 2
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# 
#---------------------------------------------------------------------
"""

from PyQt4 import QtCore, QtGui
from qgis.core import *
from qgis.gui import *
import qmarxanz
from ui_mkgrid import Ui_dlgMakeGrid
import math,os
from makegrid_worker import gridCreator
from qmz_utils import qmzGrid


class qmzMakeGrid(QtGui.QDialog,Ui_dlgMakeGrid):

    #
    # initialization

    def __init__(self, iface):

        QtGui.QDialog.__init__(self)
        self.setupUi(self)
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        # defaults
        self.mapLayers = []
        self.outFile = ""
        self.puArea = 0.0
        self.sideLength = 0.0
        self.puCount = 0
        self.taskStatus = "Not Started"
        # lmb settings
        s = QtCore.QSettings()
        rv = s.value('qmz/projectDir')
        if rv == None:
            self.defaultDir = '.'
        else:
            self.defaultDir = rv
        self.gridTools = qmzGrid()
        
        # setting Extent
        QtCore.QObject.connect(self.tbLayerExtents, QtCore.SIGNAL("clicked()"), self.updateExtentsFromLayer)
        QtCore.QObject.connect(self.tbCanvasExtents, QtCore.SIGNAL("clicked()"), self.updateExtentsFromCanvas)
        # setting PU size
        QtCore.QObject.connect(self.spnUnitArea, QtCore.SIGNAL("valueChanged(double)"), self.updateCellCount)
        QtCore.QObject.connect(self.spnSideLength, QtCore.SIGNAL("valueChanged(double)"), self.updateCellCount)
        QtCore.QObject.connect(self.spnXMax, QtCore.SIGNAL("valueChanged(double)"), self.updateCellCount)
        QtCore.QObject.connect(self.spnXMin, QtCore.SIGNAL("valueChanged(double)"), self.updateCellCount)
        QtCore.QObject.connect(self.spnYMax, QtCore.SIGNAL("valueChanged(double)"), self.updateCellCount)
        QtCore.QObject.connect(self.spnYMin, QtCore.SIGNAL("valueChanged(double)"), self.updateCellCount)
        QtCore.QObject.connect(self.rdoArea, QtCore.SIGNAL("clicked()"), self.setAsArea)
        QtCore.QObject.connect(self.rdoSideLength, QtCore.SIGNAL("clicked()"), self.setAsLength)
        QtCore.QObject.connect(self.rdoHexagon, QtCore.SIGNAL("clicked()"), self.updateCellCount)
        QtCore.QObject.connect(self.rdoSquare, QtCore.SIGNAL("clicked()"), self.updateCellCount)
        QtCore.QObject.connect(self.chbxLimitGrid, QtCore.SIGNAL("clicked()"), self.updateCellCount)
        # selecting output
        QtCore.QObject.connect(self.tbOutputFile, QtCore.SIGNAL("clicked()"), self.selectOutputFile)
        QtCore.QObject.connect(self.leFile, QtCore.SIGNAL("textChanged(QString)"), self.enableGridCreation)
        # running process
        QtCore.QObject.connect(self.pbCreateGrid, QtCore.SIGNAL("clicked()"), self.createGrid)
        # setup gui
        self.setupGui()

    #
    # setup GUI

    def setupGui(self):
        self.setWindowTitle("Create Planning Unit Grid")
        self.cbLayer.clear()
        self.mapLayers = []
        layerList = QgsMapLayerRegistry.instance().mapLayers()
        for name, layer in layerList.iteritems():
            # load only rasters or polygon layers
            if layer.type() == 1 or (layer.type() <> 1 and layer.geometryType() == 2):
                self.cbLayer.addItem(layer.name())
                self.mapLayers.append(layer)
        self.pbCreationProgress.setRange(0, 100)
        self.pbCreationProgress.setValue(0)
        self.pbStepProgress.setRange(0,100)
        self.pbStepProgress.setValue(0)

    #
    # gui operation methods
    #

    #
    # set interface for area based operation

    def setAsArea(self):

        if self.rdoArea.isChecked():
            self.lblArea.setEnabled(True)
            self.spnUnitArea.setEnabled(True)
            self.lblLength.setDisabled(True)
            self.spnSideLength.setDisabled(True)
            self.updateCellCount()

    #
    # set interface for length based operation

    def setAsLength(self):

        if self.rdoSideLength.isChecked():
            self.lblArea.setDisabled(True)
            self.spnUnitArea.setDisabled(True)
            self.lblLength.setEnabled(True)
            self.spnSideLength.setEnabled(True)
            self.updateCellCount()

    #
    # set extents

    def updateExtents( self, boundBox ):
        self.spnXMin.setValue( boundBox.xMinimum() )
        self.spnYMin.setValue( boundBox.yMinimum() )
        self.spnXMax.setValue( boundBox.xMaximum() ) 
        self.spnYMax.setValue( boundBox.yMaximum() )

    #
    # set extents from selected layer

    def updateExtentsFromLayer(self):
        
        boundBox = self.mapLayers[self.cbLayer.currentIndex()].extent()
        self.updateExtents(boundBox)
    #
    # set extents from canvas
    
    def updateExtentsFromCanvas(self):
        
        boundBox = self.canvas.extent()
        self.updateExtents(boundBox)


    # select output file
    
    def selectOutputFile(self):

        self.outFile = QtGui.QFileDialog.getSaveFileName(caption="Save File", \
            directory=self.defaultDir, filter="ESRI Shapefile (*.shp)")
        if self.outFile <> "":
            fname,ext = os.path.splitext(self.outFile)
            if ext <> '.shp':
                self.outFile = self.outFile + '.shp'
            self.leFile.setText(self.outFile)
        else:
            self.leFile.setText("")

    #
    # enable and disable grid creation

    def enableGridCreation(self):

        if self.leFile.text() == "":
            self.pbCreateGrid.setDisabled(True)
        else:
            self.pbCreateGrid.setEnabled(True)
 
    #
    # update cell count based on extents, size and shape
    
    def updateCellCount(self):

        xMin = self.spnXMin.value()
        xMax = self.spnXMax.value()
        yMin = self.spnYMin.value()
        yMax = self.spnYMax.value()

        if self.rdoHexagon.isChecked():
            if self.rdoArea.isChecked():
                self.sideLength = self.gridTools.calcHexagonSideLength(self.spnUnitArea.value())
                self.puArea = self.spnUnitArea.value()
            else:
                self.sideLength = self.spnSideLength.value()
                self.puArea = self.gridTools.calcHexagonArea(self.sideLength)
            self.puCount = self.gridTools.calcHexagonCount(self.sideLength,xMin,xMax,yMin,yMax)
        else:
            if self.rdoArea.isChecked():
                self.sideLength = self.gridTools.calcSquareSideLength(self.spnUnitArea.value())
                self.puArea = self.spnUnitArea.value()
            else:
                self.sideLength = self.spnSideLength.value()
                self.puArea = self.gridTools.calcSquareArea(self.sideLength)
            self.puCount = self.gridTools.calcSquareCount(self.sideLength,xMin,xMax,yMin,yMax)
        if self.chbxLimitGrid.isChecked():
            self.lePUNumber.setText('< ' + str(self.puCount))
        else:
            self.lePUNumber.setText(str(self.puCount))

    #
    # create the grid file
    
    def createGrid(self):

        crs = self.iface.mapCanvas().mapRenderer().destinationCrs()
        if not crs.isValid():
            crs = None
            QtGui.QMessageBox.warning(self, 'Warning',
                "Set valid project Coordinate Reference System before creating grid", QtGui.QMessageBox.Ok)
            return()

        # configure the QgsMessageBar
        self.messageBar = self.iface.messageBar().createMessage('Building Grid...')

        # set interface interactivity appropriately
        self.setInterfaceForRun()

        bbox = [self.spnXMin.value(),self.spnYMax.value(),self.spnXMax.value(),self.spnYMin.value()]
        outFName = self.leFile.text()

        # determine method
        if self.chbxRasterClip.isChecked():
            useRaster = True
        else:
            useRaster = False

        # create worker instance
        if self.rdoHexagon.isChecked():
            if self.chbxLimitGrid.isChecked():
                worker = gridCreator(outFName,bbox,'hexagon',self.sideLength,
                    self.puCount,self.mapLayers[self.cbLayer.currentIndex()],
                    useRaster,crs,u'UTF-8')
            else:
                worker = gridCreator(outFName,bbox,'hexagon',self.sideLength,
                    self.puCount,None,useRaster,crs,u'UTF-8')
        else:
            if self.chbxLimitGrid.isChecked():
                worker = gridCreator(outFName,bbox,'square',self.sideLength,
                    self.puCount,self.mapLayers[self.cbLayer.currentIndex()],
                    useRaster,crs,u'UTF-8')
            else:
                worker = gridCreator(outFName,bbox,'square',self.sideLength,
                    self.puCount,None,useRaster,crs,u'UTF-8')

        # connect cancel to worker kill
        self.pbCancel.clicked.connect(worker.kill)
            
        # start the worker in a new thread
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        # connect things together
        worker.finished.connect(self.creationFinished)
        worker.error.connect(self.creationError)
        worker.creationProgress.connect(self.pbCreationProgress.setValue)
        worker.stepProgress.connect(self.pbStepProgress.setValue)
        worker.status.connect(self.recordTaskStatus)
        thread.started.connect(worker.run)
        # run
        thread.start()
        # manage thread and worker
        self.thread = thread
        self.worker = worker

    def recordTaskStatus(self, ret):

        self.taskStatus = ret
        self.lblProgress.setText('Creation Steps: ' + ret)

    def creationFinished( self, ret ):
        
        # clean up the worker and thread
        self.worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        # remove widget from message bar
        self.iface.messageBar().popWidget(self.messageBar)
        if ret == True:
            # report the result
            if self.taskStatus == 'Cancelled':
                self.iface.messageBar().pushMessage(self.taskStatus, level=QgsMessageBar.WARNING, duration=5)
            else:
                self.iface.messageBar().pushMessage(self.taskStatus, duration=5)
        else:
            # notify the user that something went wrong
            self.iface.messageBar().pushMessage('Something went wrong! See the message log for more information.', level=QgsMessageBar.CRITICAL, duration=10)
        self.setInterfaceAfterRun()
        
    #
    # creationError - notify user of error
    
    def creationError(self, e, exception_string):
        QgsMessageLog.logMessage('Worker thread raised an exception:\n'.format(exception_string), level=QgsMessageLog.CRITICAL)
        self.setInterfaceAfterRun()

    #
    # setInterfaceForRun - disable some buttons during running and enable others
    
    def setInterfaceForRun( self ):
        # disable and enable buttons as appropriate
        self.pbCancel.setEnabled(True)
        self.pbClose.setDisabled(True)
        self.pbCreateGrid.setDisabled(True)

    #
    # setInterfaceAfterRun - disable some buttons after running and enable others
    
    def setInterfaceAfterRun( self ):
        # disable and enable buttons as appropriate
        self.pbCancel.setDisabled(True)
        self.pbClose.setEnabled(True)
        self.pbCreateGrid.setEnabled(True)
        # reset progress bars
        self.pbCreationProgress.setValue(0)
        self.pbStepProgress.setValue(0)



 
