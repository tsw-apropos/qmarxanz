"""
# -*- coding: utf-8 -*-
#
# ========================================================
# 
# Purpose: Calculate planning unit content
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
import math,os,inspect
import qmarxanz
from ui_calc import Ui_dlgCalc
from calc_worker import calcContent


class qmzCalcContent(QtGui.QDialog,Ui_dlgCalc):

    #
    # initialization

    def __init__(self, iface):

        QtGui.QDialog.__init__(self)
        self.setupUi(self)
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.puLyr = None
        self.geomType = None
        self.calcLyr = None
        # defaults
        self.puCount = 0
        self.taskStatus = "Not Started"
        self.layerList = []
        # qmz settings
        s = QtCore.QSettings()
        rv = s.value('qmz/projectDir')
        if rv == None:
            self.defaultDir = '.'
        else:
            self.defaultDir = rv
        self.guiStatus = 'Loading'
        
        # debugging
        self.debug = False
        self.showCalcDef = False
        if self.debug == True:
            self.myself = lambda: inspect.stack()[1][3]
            QgsMessageLog.logMessage(self.myself())
        
        # selecting planning unit grid
        QtCore.QObject.connect(self.cbPlanningGrid, QtCore.SIGNAL("currentIndexChanged(int)"), self.updatePUFields)
        # filter layer list
        QtCore.QObject.connect(self.rdoPoint, QtCore.SIGNAL("clicked()"), self.updateMeasureList)
        QtCore.QObject.connect(self.rdoLine, QtCore.SIGNAL("clicked()"), self.updateMeasureList)
        QtCore.QObject.connect(self.rdoArea, QtCore.SIGNAL("clicked()"), self.updateMeasureList)
        QtCore.QObject.connect(self.rdoRaster, QtCore.SIGNAL("clicked()"), self.updateMeasureList)
        # select measure layer
        QtCore.QObject.connect(self.cbMeasureLayer, QtCore.SIGNAL("currentIndexChanged(int)"), self.updateMeasureFields)
        # set single vs group calculations
        QtCore.QObject.connect(self.rdoCalcSingle, QtCore.SIGNAL("clicked()"), self.setSingleMulti)
        QtCore.QObject.connect(self.rdoCalcMulti, QtCore.SIGNAL("clicked()"), self.setSingleMulti)
        # set calc type
        QtCore.QObject.connect(self.rdoMeasure, QtCore.SIGNAL("clicked()"), self.setCalcOptions)
        QtCore.QObject.connect(self.rdoCalculate, QtCore.SIGNAL("clicked()"), self.setCalcOptions)
        QtCore.QObject.connect(self.rdoValue, QtCore.SIGNAL("clicked()"), self.setCalcOptions)
        # set destination
        QtCore.QObject.connect(self.rdoWriteLyr, QtCore.SIGNAL("clicked()"), self.setDestination)
        QtCore.QObject.connect(self.rdoWriteFile, QtCore.SIGNAL("clicked()"), self.setDestination)
        # existing or new field
        QtCore.QObject.connect(self.cbOutputField, QtCore.SIGNAL("currentIndexChanged(int)"), self.setOutputField)
        # set output path and name
        QtCore.QObject.connect(self.tbDestFile, QtCore.SIGNAL("clicked()"), self.selectOutputFile)
        # test output options
        QtCore.QObject.connect(self.leOutput, QtCore.SIGNAL("textChanged(QString)"), self.enableDisableRunButton)
        # set calculation method
        QtCore.QObject.connect(self.chbxRasterize, QtCore.SIGNAL("clicked()"), self.enableDisableRasterize)
        # running process
        QtCore.QObject.connect(self.pbRun, QtCore.SIGNAL("clicked()"), self.calcValues)
        # setup gui
        self.setupGui()
        self.guiStatus = 'Editing'

    #
    # setup GUI

    def setupGui(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.setWindowTitle("Calculate Planning Unit Content")
        # populate layer list
        layers = self.iface.legendInterface().layers()
        for layer in layers:
            if layer.type() == 1:
                self.layerList.append(['raster',layer.name(),layer.source(),layer])
            else:
                if layer.geometryType() == 0:
                    self.layerList.append(['point',layer.name(),layer.source(),layer])
                elif layer.geometryType() == 1:
                    self.layerList.append(['line',layer.name(),layer.source(),layer])
                elif layer.geometryType() == 2:
                    self.layerList.append(['area',layer.name(),layer.source(),layer])
        # populate grid list
        self.cbPlanningGrid.clear()
        x = 0
        cnt = len(self.layerList)
        for x in range(cnt):
            if self.layerList[x][0] == 'area':
                self.cbPlanningGrid.addItem(self.layerList[x][1])
        # populate measure list
        self.updateMeasureList()
        # set control default states
        self.tbDestFile.setVisible(False)
        # reset progress bars
        self.pbCalcProgress.setRange(0, 100)
        self.pbCalcProgress.setValue(0)
        self.pbStepProgress.setRange(0,100)
        self.pbStepProgress.setValue(0)

    #
    # gui operation methods
    #

    #
    # update measure layer list

    def updateMeasureList(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.cbMeasureLayer.clear()
        x = 0
        cnt = len(self.layerList)
        if self.rdoPoint.isChecked():
            self.geomType = 'point'
            for x in range(cnt):
                if self.layerList[x][0] == 'point':
                    self.cbMeasureLayer.addItem(self.layerList[x][1])
            self.chbxRasterize.setChecked(False)
            self.chbxRasterize.setDisabled(True)
        elif self.rdoLine.isChecked():
            self.geomType = 'line'
            for x in range(cnt):
                if self.layerList[x][0] == 'line':
                    self.cbMeasureLayer.addItem(self.layerList[x][1])
            self.chbxRasterize.setChecked(False)
            self.chbxRasterize.setDisabled(True)
        elif self.rdoArea.isChecked():
            self.geomType = 'area'
            for x in range(cnt):
                if self.layerList[x][0] == 'area':
                    self.cbMeasureLayer.addItem(self.layerList[x][1])
            self.chbxRasterize.setChecked(False)
            self.chbxRasterize.setEnabled(True)
        if self.rdoRaster.isChecked():
            self.geomType = 'raster'
            for x in range(cnt):
                if self.layerList[x][0] == 'raster':
                    self.cbMeasureLayer.addItem(self.layerList[x][1])
            self.chbxRasterize.setChecked(False)
            self.chbxRasterize.setDisabled(True)
        else:
            self.rdoCalcSingle.setChecked(True)
            self.rdoCalcMulti.setEnabled(True)
            self.rdoCalcSingle.setEnabled(True)
        self.enableDisableRasterize()
        self.enableDisableRunButton()
        self.setDestination()
        
    #
    # enable or disable rasterize option

    def enableDisableRasterize(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if self.chbxRasterize.isChecked():
            self.lblPixelSize.setEnabled(True)
            self.spbxPixelSize.setEnabled(True)
        else:
            self.lblPixelSize.setDisabled(True)
            self.spbxPixelSize.setDisabled(True)
        #self.setCalcOptions()

    #
    # update pu fields in controls

    def updatePUFields(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.cbPuId.clear()
        self.cbOutputField.clear()
        self.cbOutputField.addItem('--New--')
        lName = self.cbPlanningGrid.currentText()
        lIdx = -1
        for x in range(len(self.layerList)):
            if self.layerList[x][1] == lName:
                lIdx = x
                self.puLyr = self.layerList[lIdx][3]
                break
        if lIdx <> -1:
            fldList = self.layerList[lIdx][3].dataProvider().fields()
            for x in range(fldList.count()):
                if fldList[x].typeName() == 'Integer':
                    self.cbPuId.addItem(fldList[x].name())
                elif fldList[x].typeName() == 'Real':
                    self.cbOutputField.addItem(fldList[x].name())

    #
    # update measure fields in controls

    def updateMeasureFields(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.cbCalcField.clear()
        if self.rdoRaster.isChecked():
            self.cbCalcField.addItem('Pixel Value')
            x = 0
            for x in range(len(self.layerList)):
                if self.layerList[x][0] == 'raster' and \
                self.layerList[x][1] == self.cbMeasureLayer.currentText():
                    self.spbxPixelSize.setValue(self.layerList[x][3].rasterUnitsPerPixelX())
                    self.srcLyr = self.layerList[x][3]
                    break 
        else:
            lName = self.cbMeasureLayer.currentText()
            lIdx = -1
            for x in range(len(self.layerList)):
                if self.layerList[x][1] == lName:
                    lIdx = x
                    self.srcLyr = self.layerList[lIdx][3]
                    break
            if lIdx <> -1:
                fldList = self.layerList[lIdx][3].dataProvider().fields()
                for x in range(fldList.count()):
                    if fldList[x].typeName() in ('Integer','Real'):
                        self.cbCalcField.addItem(fldList[x].name())
        self.enableDisableRunButton()

    #
    # set single or multi field calculation

    def setSingleMulti(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.setDestination()
        if self.rdoCalcSingle.isChecked():
            self.rdoMeasure.setChecked(True)
        else:
            self.rdoCalculate.setChecked(True)
            self.cbOutputField.setCurrentIndex(0)
        
            
    #
    # set calc options

    def setCalcOptions(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if self.rdoCalcSingle.isChecked():
        # single
            self.rdoMeasure.setEnabled(True)
            self.rdoCalculate.setEnabled(True)
            self.rdoValue.setEnabled(True)
        else:
        # multi - requires a value so measure is disabled
            self.rdoMeasure.setDisabled(True)
            self.rdoCalculate.setEnabled(True)
            self.rdoValue.setEnabled(True)
        # enable / disable calc field
        if self.rdoMeasure.isChecked():
            self.lblCalcField.setDisabled(True)
            self.cbCalcField.setDisabled(True)
        elif self.rdoCalculate.isChecked() or self.rdoValue.isChecked():
            self.lblCalcField.setEnabled(True)
            self.cbCalcField.setEnabled(True)
        self.setIntersectionOptions()

    #
    # set intersection options

    def setIntersectionOptions(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.rdoSum.setChecked(True)
        if self.rdoMeasure.isChecked():
        # measure
            if self.rdoRaster.isChecked():
            # raster
                self.rdoSum.setEnabled(True)
                self.rdoMean.setDisabled(True)
                self.rdoMax.setDisabled(True)
                self.rdoMin.setDisabled(True)
                self.rdoCount.setEnabled(True)
                self.rdoPresence.setEnabled(True)
            else:
            # vector
                self.rdoSum.setEnabled(True)
                self.rdoMean.setEnabled(True)
                self.rdoMax.setEnabled(True)
                self.rdoMin.setEnabled(True)
                self.rdoCount.setEnabled(True)
                self.rdoPresence.setEnabled(True)
        else:
        # calculate or value
            if self.rdoCalcSingle.isChecked():
            # single
                if self.rdoCalculate.isChecked():
                # calculate
                    self.rdoSum.setEnabled(True)
                    self.rdoMean.setEnabled(True)
                    self.rdoMax.setEnabled(True)
                    self.rdoMin.setEnabled(True)
                    self.rdoCount.setDisabled(True)
                    self.rdoPresence.setDisabled(True)
                else:
                # value
                    self.rdoSum.setEnabled(True)
                    self.rdoMean.setEnabled(True)
                    self.rdoMax.setEnabled(True)
                    self.rdoMin.setEnabled(True)
                    self.rdoCount.setEnabled(True)
                    self.rdoPresence.setDisabled(True)
            else:
            # multi
                if self.rdoCalculate.isChecked() and self.rdoRaster.isChecked() == False:
                # calculate vector
                    self.rdoSum.setEnabled(True)
                    self.rdoMean.setEnabled(True)
                    self.rdoMax.setEnabled(True)
                    self.rdoMin.setEnabled(True)
                    self.rdoCount.setDisabled(True)
                    self.rdoPresence.setDisabled(True)
                elif self.rdoCalculate.isChecked() and self.rdoRaster.isChecked():
                # calculate raster
                    self.rdoSum.setEnabled(True)
                    self.rdoMean.setEnabled(True)
                    self.rdoMax.setEnabled(True)
                    self.rdoMin.setEnabled(True)
                    self.rdoCount.setEnabled(True)
                    self.rdoPresence.setDisabled(True)
                else:
                # value
                    if self.rdoRaster.isChecked():
                    # value of pixels
                        self.rdoSum.setDisabled(True)
                        self.rdoMean.setDisabled(True)
                        self.rdoMax.setDisabled(True)
                        self.rdoMin.setDisabled(True)
                        self.rdoCount.setDisabled(True)
                        self.rdoPresence.setEnabled(True)
                        self.rdoPresence.setChecked(True)
                    else:
                    # value of fields
                        self.rdoSum.setDisabled(True)
                        self.rdoMean.setDisabled(True)
                        self.rdoMax.setDisabled(True)
                        self.rdoMin.setDisabled(True)
                        self.rdoCount.setEnabled(True)
                        self.rdoPresence.setEnabled(True)
                        self.rdoPresence.setChecked(True)

    ##
    ## disable intersection options
 
    #def disableIntersectionOptions(self):

        #if self.rdoCalcMulti.isChecked():
            #self.rdoCalculate.setChecked(True)
            #self.lblCalcField.setEnabled(True)
            #self.cbCalcField.setEnabled(True)
        #else:
            #self.rdoMeasure.setChecked(True)
            #self.lblCalcField.setDisabled(True)
            #self.cbCalcField.setDisabled(True)
        #self.lblMeasureOrCalc.setDisabled(True)
        #self.rdoMeasure.setDisabled(True)
        #self.rdoCalculate.setDisabled(True)
        #self.rdoPresence.setDisabled(True)
        #self.enableDisableMultiIntersectionActions()

    #
    # enable intersection options

    #def enableIntersectionOptions(self):

        #self.lblMeasureOrCalc.setEnabled(True)
        #self.rdoMeasure.setEnabled(True)
        #self.rdoMeasure.setEnabled(True)
        #self.rdoCalculate.setEnabled(True)
        #self.rdoPresence.setEnabled(True)
        #self.enableDisableMultiIntersectionActions()

    #
    # enable disable multi intersection actions

    #def enableDisableMultiIntersectionActions(self):
        
        #if self.rdoPresence.isChecked() or self.chbxRasterize.isChecked() or \
        #self.rdoCalcMulti.isChecked():
            #self.lblMultipleAction.setDisabled(True)
            #self.rdoSum.setChecked(True)
            #self.rdoSum.setDisabled(True)
            #self.rdoMean.setDisabled(True)
            #self.rdoMax.setDisabled(True)
            #self.rdoMin.setDisabled(True)
            #self.rdoCount.setDisabled(True)
        #else:
            #self.rdoSum.setChecked(True)
            #self.rdoSum.setEnabled(True)
            #self.rdoMean.setEnabled(True)
            #self.rdoMax.setEnabled(True)
            #self.rdoMin.setEnabled(True)
            #self.rdoCount.setEnabled(True)

    #
    # set destination

    def setDestination(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if self.rdoWriteLyr.isChecked():
        # write to pu layer
            self.leOutput.clear()
            self.tbDestFile.setVisible(False)
            if self.rdoCalcSingle.isChecked():
                self.lblSelectField.setEnabled(True)
                self.lblSelectField.setVisible(True)
                self.cbOutputField.setEnabled(True)
                self.cbOutputField.setVisible(True)
                self.lblNewField.setText('Enter name')
                self.leOutput.setMaxLength(10)
            elif self.rdoCalcMulti.isChecked() or self.rdoRaster.isChecked():
                self.lblSelectField.setDisabled(True)
                self.lblSelectField.setVisible(False)
                self.cbOutputField.setDisabled(True)
                self.cbOutputField.setVisible(False)
                self.lblNewField.setText('Enter prefix')
                self.leOutput.setMaxLength(6)
            self.rdoCalcSingle.setText('Single Field')
            self.rdoCalcMulti.setText('Multiple Fields')
        else:
        # write to file
            self.cbOutputField.setCurrentIndex(0)
            self.leOutput.setMaxLength(32767)
            self.leOutput.clear()
            self.lblSelectField.setDisabled(True)
            self.lblSelectField.setVisible(False)
            self.cbOutputField.setDisabled(True)
            self.cbOutputField.setVisible(False)
            self.tbDestFile.setVisible(True)
            if self.rdoCalcSingle.isChecked():
                self.lblNewField.setText('Enter path and name (file extention added at run time)')
            else:
                self.lblNewField.setText('Enter path and prefix (code & file extention added at run time)')
            self.rdoCalcSingle.setText('Single File')
            self.rdoCalcMulti.setText('Multiple Files')
        self.setCalcOptions()
        
    #
    # set output field

    def setOutputField(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.leOutput.clear()
        if self.cbOutputField.currentIndex() == 0:
            self.leOutput.setEnabled(True)
        else:
            self.leOutput.setDisabled(True)
        self.enableDisableRunButton()

    #
    # select output file

    def selectOutputFile(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        ofn = QtGui.QFileDialog.getSaveFileName(self, 'Select output file', self.defaultDir)
        path,fName = os.path.split(ofn)
        fRoot,fExt = os.path.splitext(fName)
        fOFN = os.path.join(path,fRoot)
        self.leOutput.setText(fOFN)
        self.enableDisableRunButton()

    #
    # enable & disable run button based on form state

    def enableDisableRunButton(self):

        if self.guiStatus <> 'Loading':
            if self.debug == True:
                QgsMessageLog.logMessage(self.myself())
            if self.cbPlanningGrid.currentIndex() >= 0 and self.cbPuId.currentIndex() >= 0 \
            and self.cbMeasureLayer.currentIndex() >= 0:
                basicsOk = True
            else:
                basicsOk = False
            if self.rdoCalculate.isChecked():
                if self.cbCalcField.currentIndex() >= 0:
                    measureOk = True
                else:
                    measureOk = False
            else:
                measureOk = True
            if (self.rdoWriteLyr.isChecked() and self.cbOutputField.currentIndex() >= 1) \
            or self.leOutput.text() <> '':
                appendOk = True
            else:
                appendOk = False
            if basicsOk and measureOk and appendOk:
                self.pbRun.setEnabled(True)
            else:
                self.pbRun.setDisabled(True)

    #
    # calculate values

    def calcValues(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        if not crs.isValid():
            crs = None
            QtGui.QMessageBox.warning(self, 'Warning',
                "Set valid project Coordinate Reference System before calculation", QtGui.QMessageBox.Ok)
            return()

        # configure the QgsMessageBar
        self.messageBar = self.iface.messageBar().createMessage('Calculating Values...')

        # set interface interactivity appropriately
        self.setInterfaceForRun()

        # create worker instance
        if self.rdoCalcSingle.isChecked():
            singleField = True
        else:
            singleField = False
        if self.chbxRasterize.isChecked():
            useRaster = True
        else:
            useRaster = False
        if self.rdoMeasure.isChecked():
            calcType = 'measure'
        elif self.rdoCalculate.isChecked():
            calcType = 'calculate'
        else:
            calcType = 'value'
        if calcType in ['calculate','value']:
            if self.rdoRaster.isChecked() == False:
                calcField = self.cbCalcField.currentText()
            else:
                calcField = ''
        else:
            calcField = ''
        if self.rdoSum.isChecked():
            intersectOp = 'sum'
        elif self.rdoMean.isChecked():
            intersectOp = 'mean'
        elif self.rdoMax.isChecked():
            intersectOp = 'max'
        elif self.rdoMin.isChecked():
            intersectOp = 'min'
        elif self.rdoCount.isChecked():
            intersectOp = 'count'
        else:
            intersectOp = 'presence'
        if self.rdoWriteLyr.isChecked():
            destType = 'pulyr'
            if self.cbOutputField.currentIndex() > 0:
                destName = self.cbOutputField.currentText()
            else:
                destName = self.leOutput.text()
        else:
            destType = 'file'
            destName = self.leOutput.text()
        srcNDValue = 0
        # create dictionary to send
        calcDict = {}
        calcDict['key'] = 0
        calcDict['puLyr'] = self.puLyr
        calcDict['idField'] = self.cbPuId.currentText()
        calcDict['geomType'] = self.geomType
        calcDict['srcLyr'] = self.srcLyr
        calcDict['singleField'] = singleField
        calcDict['useRaster'] = useRaster
        calcDict['calcType'] = calcType
        calcDict['calcField'] = calcField
        calcDict['intersectOp'] = intersectOp
        calcDict['destType'] = destType
        calcDict['destName'] = destName
        calcDict['crs'] = crs
        calcDict['pixelSize'] = self.spbxPixelSize.value()
        if self.geomType == 'raster':
            if self.srcLyr.dataProvider().srcHasNoDataValue(1):
                srcNDValue = self.srcLyr.dataProvider().srcNoDataValue(1)
        calcDict['srcNDValue'] = srcNDValue
        calcList = []
        calcList.append(calcDict)
        if self.showCalcDef == True:
            QgsMessageLog.logMessage(str(calcList))
        worker = calcContent(calcList)

        # connect cancel to worker kill
        self.pbCancel.clicked.connect(worker.kill)
            
        # start the worker in a new thread
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        # connect things together
        worker.workerFinished.connect(self.calcFinished)
        worker.workerError.connect(self.calcError)
        worker.workerStatus.connect(self.recordTaskStatus)
        worker.progressCalc.connect(self.pbCalcProgress.setValue)
        worker.progressStep.connect(self.pbStepProgress.setValue)
        thread.started.connect(worker.run)
        # run
        thread.start()
        # manage thread and worker
        self.thread = thread
        self.worker = worker

    #
    # setInterfaceForRun - disable some buttons during running and enable others
    
    def setInterfaceForRun( self ):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # disable and enable buttons as appropriate
        self.pbCancel.setEnabled(True)
        self.pbClose.setDisabled(True)
        self.pbRun.setDisabled(True)

    #
    # setInterfaceAfterRun - disable some buttons after running and enable others
    
    def setInterfaceAfterRun( self ):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # disable and enable buttons as appropriate
        self.pbCancel.setDisabled(True)
        self.pbClose.setEnabled(True)
        self.pbRun.setEnabled(True)
        # reset progress bars
        self.pbCalcProgress.setValue(0)
        self.pbStepProgress.setValue(0)

    #
    # record task status

    def recordTaskStatus(self, ret):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.taskStatus = ret
        self.lblCalcProcess.setText('Calculation Process: ' + ret)

    #
    # clean up after finishing calculation
    
    def calcFinished( self, ret ):
        
        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
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
    
    def calcError(self, e, exception_string):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        QgsMessageLog.logMessage('Worker thread raised an exception:\n'.format(exception_string), level=QgsMessageLog.CRITICAL)
        self.setInterfaceAfterRun()



 
        
