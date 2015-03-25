"""
# -*- coding: utf-8 -*-
#
# ========================================================
# 
# Purpose: Export and run Marxan / Marxan with Zones
# Author: Trevor Wiens
# Copyright: Apropos Information Systems Inc.
# Date: 2015-01-31
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
import qmarxanz
from qgis.core import *
from ui_configure_run import Ui_dlgConfigureRun
import math,os,json,shutil,datetime,inspect,csv
from qmz_utils import qmzCalcChecks
from export_worker import exportContent
from import_worker import importContent
from run_worker import runMarxan

class qmzRun(QtGui.QDialog, Ui_dlgConfigureRun):

    #
    # initialization, connecting GUI controls to methods

    def __init__(self, iface):

        QtGui.QDialog.__init__(self)
        self.setupUi(self)
        self.iface = iface
        self.qmzDir = None
        self.workingDir = None
        self.workingFile = None
        self.workingDict = {}
        self.layerList = []
        self.puLyr = None
        self.resultsLyr = None
        self.crs = None
        self.calcCheck = qmzCalcChecks()
        self.actionDict = {}
        self.actionsStatus = 'Not started'
        self.importLyr = None
        self.importFileDelimiter = ','
        self.actionUpdatesDict = False

        self.debug = False
        if self.debug == True:
            self.myself = lambda: inspect.stack()[1][3]
            QgsMessageLog.logMessage(self.myself())

        # Dialog control
        QtCore.QObject.connect(self.pbClose, QtCore.SIGNAL("clicked()"), self.closeDialog)
        QtCore.QObject.connect(self.cbWorkingProject, QtCore.SIGNAL("currentIndexChanged(int)"), self.projectLoadWorking)
        # General Parameters Tab
        QtCore.QObject.connect(self.pbEditGeneral, QtCore.SIGNAL("clicked()"), self.generalEdit)
        QtCore.QObject.connect(self.pbSaveGeneral, QtCore.SIGNAL("clicked()"), self.generalSave)
        QtCore.QObject.connect(self.pbCancelGeneral, QtCore.SIGNAL("clicked()"), self.generalCancel)
        # Boundary Paramters Tab
        QtCore.QObject.connect(self.pbEditBoundary, QtCore.SIGNAL("clicked()"), self.boundaryEdit)
        QtCore.QObject.connect(self.pbSaveBoundary, QtCore.SIGNAL("clicked()"), self.boundarySave)
        QtCore.QObject.connect(self.pbCancelBoundary, QtCore.SIGNAL("clicked()"), self.boundaryCancel)
        QtCore.QObject.connect(self.cbBoundaryMethod, QtCore.SIGNAL("currentIndexChanged(int)"), self.boundarySetFieldLists)
        # Other Parameters Tab
        QtCore.QObject.connect(self.pbEditOther, QtCore.SIGNAL("clicked()"), self.otherEdit)
        QtCore.QObject.connect(self.pbSaveOther, QtCore.SIGNAL("clicked()"), self.otherSave)
        QtCore.QObject.connect(self.pbCancelOther, QtCore.SIGNAL("clicked()"), self.otherCancel)
        # Output Tab
        QtCore.QObject.connect(self.pbEditOutput, QtCore.SIGNAL("clicked()"), self.outputEdit)
        QtCore.QObject.connect(self.pbSaveOutput, QtCore.SIGNAL("clicked()"), self.outputSave)
        QtCore.QObject.connect(self.pbCancelOutput, QtCore.SIGNAL("clicked()"), self.outputCancel)
        # Export and Run Tab
        QtCore.QObject.connect(self.pbActionReport, QtCore.SIGNAL("clicked()"), self.actionsReport)
        QtCore.QObject.connect(self.pbDoAction, QtCore.SIGNAL("clicked()"), self.actionsPerform)
        QtCore.QObject.connect(self.cbActions, QtCore.SIGNAL("currentIndexChanged(int)"), self.actionsSelect)
        # Reports Tab
        QtCore.QObject.connect(self.tbGetTextFile, QtCore.SIGNAL("clicked()"), self.importSelectTextFile)
        QtCore.QObject.connect(self.cbImportField, QtCore.SIGNAL("currentIndexChanged(int)"), self.importSetField)
        # switching tabs
        QtCore.QObject.connect(self.twInputs, QtCore.SIGNAL("currentChanged(int)"), self.actionsClearReport)
        # Configure gui
        self.setupGui()
        
    #
    # basic gui setup and loading
    
    def setupGui(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # this populates everything if a proper project is selected
        self.readSettings()
        # configure appearance
        self.twInputs.setCurrentIndex(4)
        self.lblActionParameters.setVisible(False)
        self.lnActionParameters.setVisible(False)
        self.frImport.setVisible(False)
        self.lblActions.setDisabled(True)
        self.cbActions.setDisabled(True)
        
    #
    # close dialog

    def closeDialog(self):

        #self.iface.newProject()
        self.close()
        
    #
    # reading QGIS stored settings for QMZ
    
    def readSettings(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        s = QtCore.QSettings()
        # projects directory
        rv = s.value('QMarxanZ/projectsDir')
        if rv == None:
            self.qmzDir = '.'
        else:
            self.qmzDir = rv
        # marxan executable
        rv = s.value('QMarxanZ/MarxanExecutable')
        if rv == None:
            self.marxanPath = ''
        else:
            self.marxanPath = rv
        # R executable
        rv = s.value('QMarxanZ/RExecutable')
        if rv == None:
            self.rPath = ''
        else:
            self.rPath = rv
        # get project list
        self.projectLoadList()
        # default project
        rv = s.value('QMarxanZ/defaultProject')
        if rv <> None:
            defPath = os.path.join(self.qmzDir,str(rv))
            if os.path.exists(defPath):
                tempName = ''
                for key, value in self.projList.iteritems():
                    if value[1] == str(rv):
                        tempName = value[1]
                if tempName <> '':
                    idx = self.cbWorkingProject.findText(tempName)
                    if idx <> -1:
                        self.cbWorkingProject.setCurrentIndex(idx)
                    else:
                        self.cbWorkingProject.setCurrentIndex(0)

    #
    # load project list

    def projectLoadList(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.projList = {}
        dirList = [d for d in os.listdir(self.qmzDir) if os.path.isdir(os.path.join(self.qmzDir,d))]
        x = 0
        for dirName in dirList:
            pfn = os.path.join(self.qmzDir,dirName,'qmzproj.qmz')
            if os.path.exists(pfn):
                f = open(pfn,'r')
                pDict = json.loads(f.read())
                pName = pDict['project']['name']
                self.projList[x] = [pDict['project']['name'],pDict['project']['dirName']]
                f.close()
                x = x + 1
        # get existing working project
        currentName = self.cbWorkingProject.currentText()
        # clear project controls
        self.cbWorkingProject.clear()
        self.cbWorkingProject.addItem('--None--')
        for key, value in self.projList.iteritems():
            self.cbWorkingProject.addItem(value[1])
        if currentName <> '--None--':
            idx = self.cbWorkingProject.findText(currentName)
            if idx <> -1:
                self.cbWorkingProject.setCurrentIndex(idx)

    #
    # load working project for when not editing a project

    def projectLoadWorking(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        newDir = self.cbWorkingProject.currentText()
        loadProject = False
        # clear calculation reports
        self.actionsClearReport()
        self.frImport.setVisible(False)
        self.leTextFile.setText('')
        if newDir == '--None--':
            # define globals
            self.workingDir = None
            self.workingName = ''
            self.workingDict = {}
            self.workingFile = ''
            nTitle = 'No project: QMZ Configure, Export and Run'
            # load blank project
            self.iface.newProject()
            self.setWindowTitle(nTitle)
            self.twInputs.setDisabled(True)
        elif self.workingName <> newDir:
            for key, value in self.projList.iteritems():
                if value[1] == newDir:
                    self.workingDir = os.path.join(self.qmzDir,value[1])
                    self.workingName = newDir
            if os.path.exists(self.workingDir):
                # define globals
                self.workingFile = os.path.join(self.workingDir,'qmzproj.qmz')
                f = open(self.workingFile,'r')
                self.workingDict = json.loads(f.read())
                f.close()
                if self.workingDict['project']['type'] == 'Marxan with Zones':
                    self.workingType = 'Zones'
                    nTitle = '%s: Marxan with Zones Configure, Export and Run' % self.workingDict['project']['name']
                else:
                    self.workingType = 'Marxan'
                    nTitle = '%s: Marxan Configure, Export and Run' % self.workingDict['project']['name']
                self.setWindowTitle(nTitle)
                # load qgis project
                self.qgisProjectLoad(self.workingDict['project']['qgisProject'])
                # add default settings to qmz file if there are not any yet
                if len(self.workingDict['settings']['general']['recs']) == 0:
                    self.generalSave()
                if len(self.workingDict['settings']['boundary']['recs']) == 0:
                    self.boundarySave()
                if len(self.workingDict['settings']['other']['recs']) == 0:
                    if self.workingType == 'Zones':
                        self.cbItImpType.setCurrentIndex(1)
                    else:
                        self.cbItImpType.setCurrentIndex(2)
                    self.otherSave()
                if len(self.workingDict['settings']['output']['recs']) == 0:
                    self.outputSave()
                # adjust appearance based on project type
                if self.workingType == 'Marxan':
                    self.frZonesGeneral.setVisible(False)
                    self.frZonesBoundarySettings.setVisible(False)
                    self.frZonesOutput.setVisible(False)
                    self.frMarxanOutput.setVisible(True)
                else:
                    self.frZonesGeneral.setVisible(True)
                    self.frZonesBoundarySettings.setVisible(True)
                    self.frZonesOutput.setVisible(True)
                    self.frMarxanOutput.setVisible(False)
                # load values into interface
                self.boundaryEdit()
                self.boundaryCancel()
                self.generalEdit()
                self.generalCancel()
                self.otherEdit()
                self.otherCancel()
                self.outputEdit()
                self.outputCancel()
                self.twInputs.setEnabled(True)
                

    #
    # load QGIS project

    def qgisProjectLoad(self, projectName):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if QgsProject.instance().fileName() <> projectName:
            self.iface.newProject()
            result = QgsProject.instance().read(QtCore.QFileInfo(projectName))
        else:
            result = True
        if result == True:
            layers = self.iface.legendInterface().layers()
            self.layerList = []
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
                        if layer.name() == self.workingDict['project']['puLyr']:
                            self.puLyr = layer
                            self.gisUpdatePUFieldList()
                        if layer.name() == self.workingDict['project']['resultsLyr']:
                            self.resultsLyr = layer
                            self.gisUpdateResultsFieldList()
                            
        self.crs = self.iface.mapCanvas().mapSettings().destinationCrs()

    #
    # update pu field list
    
    def gisUpdatePUFieldList(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.cbBoundaryField.clear()
        self.cbPUStatusField.clear()
        self.puFieldList = []
        fields = self.puLyr.dataProvider().fields()
        for field in fields:
            if field.typeName() in ('Integer','Real'):
                self.cbBoundaryField.addItem(field.name())
                self.cbPUStatusField.addItem(field.name())
                self.puFieldList.append(field.name())
        
    #
    # update results field list
    
    def gisUpdateResultsFieldList(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.cbImportField.clear()
        self.cbImportField.addItem('--New--')
        fields = self.resultsLyr.dataProvider().fields()
        for field in fields:
            if field.typeName() == 'Real':
                self.cbImportField.addItem(field.name())

    #
    # General Parameters Tab
    #

    #
    # edit general parameters

    def generalEdit(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['settings']['general']['recs']
        if len(zDict) <> 0:
            self.spbxProp.setValue(float(zDict['proportion']))
            self.spbxBLM.setValue(float(zDict['blm']))
            self.spbxMissLevel.setValue(float(zDict['misslevel']))
            self.spbxNumReps.setValue(int(zDict['numreps']))
            self.spbxNumItns.setValue(int(zDict['numitns']))
            idx = self.cbVerbosity.findText(zDict['verbosity'])
            self.cbVerbosity.setCurrentIndex(idx)
            idx = self.cbSPFMethod.findText(zDict['spfMethod'])
            self.cbSPFMethod.setCurrentIndex(idx)
            self.spbxSolutionTarget.setValue(int(zDict['solutionTarget']))
            self.spbxSPFStep.setValue(float(zDict['spfStep']))
            self.leIterationList.setText(zDict['iterationList'])
            if self.workingType == 'Zones':
                # need to write this
                pass 
        self.generalEnableEditing()

    #
    # save general parameters

    def generalSave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # use temp dict to keep lines short
        tempDict = {}
        tempDict['proportion'] = self.spbxProp.value()
        tempDict['blm'] = self.spbxBLM.value()
        tempDict['misslevel'] = self.spbxMissLevel.value()
        tempDict['numreps'] = self.spbxNumReps.value()
        tempDict['numitns'] = self.spbxNumItns.value()
        tempDict['verbosity'] = self.cbVerbosity.currentText()
        tempDict['spfMethod'] = self.cbSPFMethod.currentText()
        tempDict['solutionTarget'] = self.spbxSolutionTarget.value()
        tempDict['spfStep'] = self.spbxSPFStep.value()
        tempDict['iterationList'] =  self.leIterationList.text()
        if self.workingType == 'Zones':
            tempDict['availablezone'] = self.cbAvailableZone.currentText()
        # push temp dict into main project dictionary
        self.workingDict['settings']['general']['recs'] = tempDict
        self.workingDict['settings']['general']['editdate'] = datetime.datetime.now().isoformat()
        self.workingDict['settings']['editdate'] = datetime.datetime.now().isoformat()
        # write to disk
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        self.generalDisableEditing()
        
    #
    # cancel editing of general parameters

    def generalCancel(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.generalDisableEditing()

    #
    # enable editing of general parameters

    def generalEnableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.frGeneralAll.setEnabled(True)
        self.frMarxanCalibration.setEnabled(True)
        if self.workingType == 'Zones':
            self.frZonesGeneral.setEnabled(True)
        self.pbSaveGeneral.setEnabled(True)
        self.pbCancelGeneral.setEnabled(True)
        self.pbEditGeneral.setDisabled(True)
        # main controls
        self.twInputs.tabBar().setDisabled(True)
        self.pbClose.setDisabled(True)
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)

    #
    # disable editing of general parameters

    def generalDisableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.frGeneralAll.setDisabled(True)
        self.frMarxanCalibration.setDisabled(True)
        self.frZonesGeneral.setDisabled(True)
        self.pbSaveGeneral.setDisabled(True)
        self.pbCancelGeneral.setDisabled(True)
        self.pbEditGeneral.setEnabled(True)
        # main controls
        self.twInputs.tabBar().setEnabled(True)
        self.pbClose.setEnabled(True)
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)


    #
    # Boundary Parameters Tab
    #

    #
    # edit boundary parameters

    def boundaryEdit(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.boundarySetFieldLists()
        zDict = self.workingDict['settings']['boundary']['recs']
        if len(zDict) <> 0:
            if zDict['boundmethod'] == 'Measure':
                self.cbBoundaryMethod.setCurrentIndex(0)
            elif zDict['boundmethod'] == 'Measure x Field':
                self.cbBoundaryMethod.setCurrentIndex(1)
                idx = self.cbBoundaryField.findText(zDict['field'])
            else:
                self.cbBoundaryMethod.setCurrentIndex(2)
            idx = self.cbBoundaryDiffs.findText(zDict['diffmethod'])
            self.cbBoundaryDiffs.setCurrentIndex(idx)
            idx = self.cbBoundaryEdge.findText(zDict['edgemethod'])
            self.cbBoundaryEdge.setCurrentIndex(idx)
            self.cbBoundaryExportPrecision.setCurrentIndex(int(zDict['exportprecision'])+2)
            idx = self.cbPUStatusField.findText(zDict['pustatusfield'])
            self.cbPUStatusField.setCurrentIndex(idx)
            if self.workingType == 'Zones':
                # need to write this
                pass 
        self.boundaryEnableEditing()

    #
    # save boundary parameters

    def boundarySave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # use temp dict to keep lines short
        tempDict = {}
        tempDict['boundmethod'] = self.cbBoundaryMethod.currentText()
        tempDict['field'] = self.cbBoundaryField.currentText()
        tempDict['diffmethod'] = self.cbBoundaryDiffs.currentText()
        tempDict['edgemethod'] = self.cbBoundaryEdge.currentText()
        tempDict['exportprecision'] = self.cbBoundaryExportPrecision.currentIndex()-2
        tempDict['pustatusfield'] = self.cbPUStatusField.currentText()
        if self.workingType == 'Zones':
            tempDict['zonefield'] = self.cbPUZones.currentText()
            tempDict['lockfield'] = self.cbPULocks.currentText()
        # push temp dict into main project dictionary
        self.workingDict['settings']['boundary']['recs'] = tempDict
        self.workingDict['settings']['boundary']['editdate'] = datetime.datetime.now().isoformat()
        self.workingDict['settings']['editdate'] = datetime.datetime.now().isoformat()
        # write to disk
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        self.boundaryDisableEditing()

    #
    # cancel editing of boundary parameters

    def boundaryCancel(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.boundaryDisableEditing()

    #
    # enable editing of boundary parameters

    def boundaryEnableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.frBoundarySettings.setEnabled(True)
        if self.workingType == 'Zones':
            self.frZonesBoundarySettings.setEnabled(True)
        else:
            self.frZonesBoundarySettings.setDisabled(True)
        self.pbSaveBoundary.setEnabled(True)
        self.pbCancelBoundary.setEnabled(True)
        self.pbEditBoundary.setDisabled(True)
        # main controls
        self.twInputs.tabBar().setDisabled(True)
        self.pbClose.setDisabled(True)
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)

    #
    # disable editing of boundary parameters

    def boundaryDisableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.frBoundarySettings.setDisabled(True)
        self.frZonesBoundarySettings.setDisabled(True)
        self.pbSaveBoundary.setDisabled(True)
        self.pbCancelBoundary.setDisabled(True)
        self.pbEditBoundary.setEnabled(True)
        # main controls
        self.twInputs.tabBar().setEnabled(True)
        self.pbClose.setEnabled(True)
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)

    #
    # set the visibility and content of field lists based on boundary method
    
    def boundarySetFieldLists(self):

        if self.cbBoundaryMethod.currentIndex() == 0:
            self.cbBoundaryField.clear()
            self.cbBoundaryField.addItem("--Not Selected--")
            self.lblBoundaryField.setDisabled(True)
            self.cbBoundaryField.setDisabled(True)
        else:
            self.cbBoundaryField.clear()
            self.cbBoundaryField.addItems(self.puFieldList)
            self.lblBoundaryField.setEnabled(True)
            self.cbBoundaryField.setEnabled(True)

    #
    # Other Parameters Tab
    #

    #
    # edit other parameters

    def otherEdit(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['settings']['other']['recs']
        if len(zDict) <> 0:
            idx = self.cbRunMode.findText(zDict['runmode'])
            self.cbRunMode.setCurrentIndex(idx)
            idx = self.cbItImpType.findText(zDict['itimptype'])
            self.cbItImpType.setCurrentIndex(idx)
            self.spbxRandSeed.setValue(int(zDict['randseed']))
            self.spbxStartTemp.setValue(int(zDict['starttemp']))
            self.spbxCoolFac.setValue(float(zDict['coolfac']))
            self.spbxNumTemp.setValue(int(zDict['numtemp']))
            self.spbxCostThreshold.setValue(float(zDict['costthresh']))
            self.spbxThreshPen1.setValue(float(zDict['threshpen1']))
            self.spbxThreshPen2.setValue(float(zDict['threshpen2']))
        self.otherEnableEditing()

    #
    # save other parameters

    def otherSave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # use temp dict to keep lines short
        tempDict = {}
        tempDict['runmode'] = self.cbRunMode.currentText()
        tempDict['itimptype'] = self.cbItImpType.currentText()
        tempDict['randseed'] = self.spbxRandSeed.value()
        tempDict['starttemp'] = self.spbxStartTemp.value()
        tempDict['coolfac'] = self.spbxCoolFac.value()
        tempDict['numtemp'] = self.spbxNumTemp.value()
        tempDict['costthresh'] = self.spbxCostThreshold.value()
        tempDict['threshpen1'] = self.spbxThreshPen1.value()
        tempDict['threshpen2'] = self.spbxThreshPen2.value()
        # push temp dict into main project dictionary
        self.workingDict['settings']['other']['recs'] = tempDict
        self.workingDict['settings']['other']['editdate'] = datetime.datetime.now().isoformat()
        self.workingDict['settings']['editdate'] = datetime.datetime.now().isoformat()
        # write to disk
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        self.otherDisableEditing()

    #
    # cancel editing of other parameters

    def otherCancel(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.otherDisableEditing()

    #
    # enable editing of other parameters

    def otherEnableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.frOther.setEnabled(True)
        self.pbSaveOther.setEnabled(True)
        self.pbCancelOther.setEnabled(True)
        self.pbEditOther.setDisabled(True)
        # main controls
        self.twInputs.tabBar().setDisabled(True)
        self.pbClose.setDisabled(True)
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)

    #
    # disable editing of other parameters

    def otherDisableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.frOther.setDisabled(True)
        self.pbSaveOther.setDisabled(True)
        self.pbCancelOther.setDisabled(True)
        self.pbEditOther.setEnabled(True)
        # main controls
        self.twInputs.tabBar().setEnabled(True)
        self.pbClose.setEnabled(True)
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)


    #
    # Output Parameters Tab
    #

    #
    # edit output parameters

    def outputEdit(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['settings']['output']['recs']
        if len(zDict) <> 0:
            # common outputs
            idx = self.cbSaveRun.findText(zDict['saverun'])
            self.cbSaveRun.setCurrentIndex(idx)
            idx = self.cbSaveBest.findText(zDict['savebest'])
            self.cbSaveBest.setCurrentIndex(idx)
            idx = self.cbSaveSum.findText(zDict['savesum'])
            self.cbSaveSum.setCurrentIndex(idx)
            idx = self.cbSaveSumSoln.findText(zDict['savesumsoln'])
            self.cbSaveSumSoln.setCurrentIndex(idx)
            idx = self.cbSaveTargMet.findText(zDict['savetargmet'])
            self.cbSaveTargMet.setCurrentIndex(idx)
            idx = self.cbSaveSolutionsMatrix.findText(zDict['savesolutionsmatrix'])
            self.cbSaveSolutionsMatrix.setCurrentIndex(idx)
            idx = self.cbSaveLog.findText(zDict['savelog'])
            self.cbSaveLog.setCurrentIndex(idx)
            idx = self.cbSaveScen.findText(zDict['savescen'])
            self.cbSaveScen.setCurrentIndex(idx)
            # standard marxan outputs
            self.spbxSaveSnapSteps.setValue(int(zDict['savesnapsteps']))
            self.spbxSaveSnapChanges.setValue(int(zDict['savesnapchanges']))
            self.spbxSaveSnapFrequency.setValue(int(zDict['savesnapfrequency']))
            # zones outputs
            if self.workingType == 'Zones':
                idx = self.cbSaveAnnealingTrace.findText(zDict['saveannealingtrace'])
                self.cbSaveAnnealingTrace.setCurrentIndex(idx)
                idx = self.cbSaveItImpTrace.findText(zDict['saveitimptrace'])
                self.cbSaveItImpTrace.setCurrentIndex(idx)
                idx = self.cbSavePenalty.findText(zDict['savepenalty'])
                self.cbSavePenalty.setCurrentIndex(idx)
                self.spbxTraceRows.setValue(int(zDict['tracerows']))
                idx = self.cbSaveZoneConnectivitySum.findText(zDict['savezoneconnectivitysum'])
                self.cbSaveZoneConnectivitySum.setCurrentIndex(idx)
                idx = self.cbSaveSolutionsMatrixHeaders.findText(zDict['savesolutionsmatrixheaders'])
                self.cbSaveSolutionsMatrixHeaders.setCurrentIndex(idx)
        self.outputEnableEditing()
        
    #
    # save output parameters

    def outputSave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # use temp dict to keep lines short
        tempDict = {}
        tempDict['saverun'] = self.cbSaveRun.currentText()
        tempDict['savebest'] = self.cbSaveBest.currentText()
        tempDict['savesum'] = self.cbSaveSum.currentText()
        tempDict['savesumsoln'] = self.cbSaveSumSoln.currentText()
        tempDict['savetargmet'] = self.cbSaveTargMet.currentText()
        tempDict['savesolutionsmatrix'] = self.cbSaveSolutionsMatrix.currentText()
        tempDict['savelog'] = self.cbSaveLog.currentText()
        tempDict['savescen'] = self.cbSaveScen.currentText()
        # standard marxan outputs
        tempDict['savesnapsteps'] = self.spbxSaveSnapSteps.value()
        tempDict['savesnapchanges'] = self.spbxSaveSnapChanges.value()
        tempDict['savesnapfrequency'] = self.spbxSaveSnapFrequency.value()
        # zones outputs
        if self.workingType == 'Zones':
            tempDict['saveannealingtrace'] = self.cbSaveAnnealingTrace.currentText()
            tempDict['saveitimptrace'] = self.cbSaveItImpTrace.currentText()
            tempDict['savepenalty'] = self.cbSavePenalty.currentText()
            tempDict['tracerows'] = self.spbxTraceRows.value()
            tempDict['savezoneconnectivitysum'] = self.cbSaveZoneConnectivitySum.currentText()
            tempDict['savesolutionsmatrixheaders'] = self.cbSaveSolutionsMatrixHeaders.currentText()
        # push temp dict into main project dictionary
        self.workingDict['settings']['output']['recs'] = tempDict
        self.workingDict['settings']['output']['editdate'] = datetime.datetime.now().isoformat()
        self.workingDict['settings']['editdate'] = datetime.datetime.now().isoformat()
        # write to disk
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        self.outputDisableEditing()

    #
    # cancel editing of output parameters

    def outputCancel(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.outputDisableEditing()
        
    #
    # enable editing of output parameters

    def outputEnableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.frOutputAll.setEnabled(True)
        if self.workingType == 'Marxan':
            self.frMarxanOutput.setEnabled(True)
        else:
            self.frZonesOutput.setEnabled(True)
        self.pbSaveOutput.setEnabled(True)
        self.pbCancelOutput.setEnabled(True)
        self.pbEditOutput.setDisabled(True)
        # main controls
        self.twInputs.tabBar().setDisabled(True)
        self.pbClose.setDisabled(True)
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)

    #
    # disable editing of output parameters

    def outputDisableEditing(self):
        
        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.frOutputAll.setDisabled(True)
        self.frMarxanOutput.setDisabled(True)
        self.frZonesOutput.setDisabled(True)
        self.pbSaveOutput.setDisabled(True)
        self.pbCancelOutput.setDisabled(True)
        self.pbEditOutput.setEnabled(True)
        # main controls
        self.twInputs.tabBar().setEnabled(True)
        self.pbClose.setEnabled(True)
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)


    #
    # Export and Run Tab
    #

    #
    # reset interface and clear report if tab changes when after actions button enabled

    def actionsClearReport(self):

        self.pteActionsReport.setPlainText('')
        self.pbDoAction.setDisabled(True)
        self.lblActions.setDisabled(True)
        self.cbActions.setDisabled(True)
        
    #
    # check if GIS data is up to date
        
    def actionsGISUpToDate(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        result = False
         # generate calculations list and report
        calcList,summary = self.calcCheck.gisCalculationsReport(self.workingDict, \
            self.puLyr,self.layerList,self.workingDir,self.crs)
        if len(calcList) == 0:
            result = True
        else:
            summary += 'Close this window and go to Settings and GIS to update GIS inputs\n'
        return(result,summary)

    #
    # create report and list of available actions

    def actionsReport(self,pastText=''):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # check if GIS is up to date
        status,report = self.actionsGISUpToDate()
        self.cbActions.clear()
        self.cbActions.addItem('--None--')
        self.lblActions.setEnabled(True)
        self.cbActions.setEnabled(True)
        #QgsMessageLog.logMessage(pastText)
        if pastText <> '':
            newText = "Previous Action Summary:\n"
            newText += pastText
            newText += "\nCurrent Assessment:\n"
            newText += report
            self.pteActionsReport.setPlainText(newText)
        else:
            self.pteActionsReport.setPlainText(report)
        if status == False:
            self.pbDoAction.setDisabled(True)
            self.lblActions.setDisabled(True)
            self.cbActions.setDisabled(True)
        if status:
            # check if problem definition is up to date
            # these generate warnings but are not blockers
            newText = self.pteActionsReport.document().toPlainText()
            status,report = self.calcCheck.definitionStatus(self.workingDir,self.workingDict)
            newText += report
            self.pteActionsReport.setPlainText(newText)
            if status:
                # check if exports are up to date
                self.actionDict['export'],report = self.calcCheck.exportStatus(self.workingDir,self.workingDict,self.puLyr)
                if len(self.actionDict['export']) > 0:
                    newText = self.pteActionsReport.document().toPlainText()
                    newText += report 
                    self.pteActionsReport.setPlainText(newText)
                    self.cbActions.addItem('Export to Marxan')
                else:
                    self.cbActions.addItem('Features and Costs Report')
                    self.cbActions.addItem('Marxan SPF and BLM Calibration')
                    self.cbActions.addItem('Marxan Iterations Calibration')
                    newText = self.pteActionsReport.document().toPlainText()
                    status, report = self.calcCheck.outputStatus(self.workingDir)
                    newText += report 
                    self.pteActionsReport.setPlainText(newText)
                    if status:
                        self.cbActions.addItem('Best Results Report')
                        self.cbActions.addItem('Import Results')
                    else:
                        self.cbActions.addItem('Run Marxan')
                    # check if calibration completed

                    # check if cluster analysis done

                    # check if results imported

    #
    # perform actions

    def actionsPerform(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if self.cbActions.currentText() == 'Features and Costs Report':
            self.reportRunFeaturesAndCostsReport()
        elif self.cbActions.currentText() == 'Best Results Report':
            self.reportRunBestResultsResport()
        elif self.cbActions.currentText() == 'Export to Marxan':
            self.actionsExportToMarxan()
        elif self.cbActions.currentText() == 'Import Results':
            self.actionsImportResults()
        elif self.cbActions.currentText() == 'Run Marxan':
            self.actionDict['run'] = ['run']
            self.actionsRunMarxan()
        elif self.cbActions.currentText() == 'Marxan SPF and BLM Calibration':
            self.actionDict['run'] = ['spfblm']
            self.actionUpdatesDict = True
            self.actionsRunMarxan()
        elif self.cbActions.currentText() == 'Marxan Iterations Calibration':
            self.actionDict['run'] = ['iter']
            self.actionsUpdateDict = True
            self.actionsRunMarxan()
        #elif self.cbActions.currentText() == 'Export to Marxan with Zones':
        #elif self.cbActions.currentText() == 'Run Marxan with Zones':
        #elif self.cbActions.currentText() == 'Import Best and Frequency Results':
        #elif self.cbActions.currentText() == 'Perform Cluster Analysis':

   #
    # process error

    def actionsError(self,e,exception_string,messageText):
        
        QgsMessageLog.logMessage('Worker thread raised an exception\n' + str(exception_string), level=QgsMessageLog.CRITICAL)
        self.errorText = messageText

    #
    # process finished

    def actionsFinished(self,ret,messageText):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        #QgsMessageLog.logMessage(messageText)
        # clean up the worker and thread
        self.worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        # report status
        if ret == True:
            # report the result
            if self.actionsStatus == 'Cancelled':
                QgsMessageLog.logMessage(self.processStatus)
            elif self.actionsStatus <> 'Completed':
                # notify the user that something went wrong
                if self.errorText == '':
                    self.errorText = 'Something went wrong!'
                QgsMessageLog.logMessage([self.errorText])
        # reset the user interface
        self.pbAllProgress.setValue(0)
        self.pbCurrentProgress.setValue(0)
        self.pbStepProgress.setValue(0)
        # reset interface
        self.lblAllProgress.setText('Overall Progress:')
        self.lblCurrentProgress.setText('Current Process:')
        self.pbActionReport.setEnabled(True)
        self.pbDoAction.setDisabled(True)
        self.pbCancelActions.setDisabled(True)
        self.pbClose.setEnabled(True)
        if self.cbActions.currentText() == 'Import Results':
            self.gisUpdateResultsFieldList()
        # re-run report if appropriate
        self.twInputs.tabBar().setEnabled(True)
        if self.actionsStatus == 'Completed':
            self.actionsReport(messageText)
        else:
            self.pteActionsReport.setPlainText(self.errorText)
            self.cbActions.clear()
        # reload dictionary if dictionary could have been updated
        if self.actionUpdatesDict:
            f = open(self.workingFile,'r')
            self.workingDict = json.loads(f.read())
            f.close()
            self.actionUpdatesDict = False
                        

    #
    # report status

    def actionsReportStatus(self,ret):

        self.actionsStatus = ret
        self.lblCurrentProgress.setText('Current Process: %s' % ret)

    #
    # actions select

    def actionsSelect(self):

        self.frImport.setVisible(False)
        if self.cbActions.currentIndex() > 0:
            self.pbDoAction.setEnabled(True)
            if self.cbActions.currentText() == 'Import Results':
                self.frImport.setVisible(True)
        else:
            self.pbDoAction.setDisabled(True)

    #
    # action export to marxan

    def actionsExportToMarxan(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.errorText = ''
        # temporarily disable run and close
        self.pbActionReport.setDisabled(True)
        self.pbDoAction.setDisabled(True)
        self.pbCancelActions.setEnabled(True)
        self.twInputs.tabBar().setDisabled(True)
        self.pbClose.setDisabled(True)
        # instantiate calcContent worker
        if 'export' in self.actionDict:
            worker = exportContent(self.puLyr, self.workingDict, \
                self.actionDict['export'],self.workingFile,self.workingDir)
        # connect cancel to worker kill
        self.pbCancelActions.clicked.connect(worker.kill)
        # start the worker in a new thread
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        # connect things together
        worker.workerFinished.connect(self.actionsFinished)
        worker.workerError.connect(self.actionsError)
        worker.workerStatus.connect(self.actionsReportStatus)
        worker.progressAll.connect(self.pbAllProgress.setValue)
        worker.progressCalc.connect(self.pbCurrentProgress.setValue)
        worker.progressStep.connect(self.pbStepProgress.setValue)
        thread.started.connect(worker.run)
        # run
        thread.start()
        # manage thread and worker
        self.thread = thread
        self.worker = worker
        
    #
    # action import best solution and frequency of selection information

    def actionsImportResults(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.errorText = ''
        # temporarily disable run and close
        self.pbActionReport.setDisabled(True)
        self.pbDoAction.setDisabled(True)
        self.pbCancelActions.setEnabled(True)
        self.twInputs.tabBar().setDisabled(True)
        self.pbClose.setDisabled(True)
        puFieldName = self.workingDict['project']['puid']
        # instantiate importContent worker
        if self.cbImportField.currentIndex() == 0:
            worker = importContent(self.resultsLyr, self.txtFile, puFieldName, \
                self.cbTextField.currentText(), ',', self.leNewField.text())
        else:
            worker = importContent(self.resultsLyr, self.txtFile, puFieldName, \
                self.cbTextField.currentText(), ',', self.cbImportField.currentText())
        # connect cancel to worker kill
        #self.pbCancelActions.clicked.connect(worker.kill)
        # start the worker in a new thread
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        # connect things together
        worker.workerFinished.connect(self.actionsFinished)
        worker.workerError.connect(self.actionsError)
        worker.workerStatus.connect(self.actionsReportStatus)
        worker.progressAll.connect(self.pbAllProgress.setValue)
        worker.progressImport.connect(self.pbCurrentProgress.setValue)
        worker.progressStep.connect(self.pbStepProgress.setValue)
        thread.started.connect(worker.run)
        # run
        thread.start()
        # manage thread and worker
        self.thread = thread
        self.worker = worker
        self.leTextFile.setText('')

    #
    # action run marxan

    def actionsRunMarxan(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.errorText = ''
        # temporarily disable run and close
        self.pbActionReport.setDisabled(True)
        self.pbDoAction.setDisabled(True)
        self.pbCancelActions.setEnabled(True)
        self.twInputs.tabBar().setDisabled(True)
        self.pbClose.setDisabled(True)
        # instantiate runMarxan worker
        worker = runMarxan(self.workingFile,self.workingDir,self.workingDict,self.actionDict['run'],self.marxanPath,self.rPath)
        # connect cancel to worker kill
        self.pbCancelActions.clicked.connect(worker.kill)
        # start the worker in a new thread
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        # connect things together
        worker.workerFinished.connect(self.actionsFinished)
        worker.workerError.connect(self.actionsError)
        worker.workerStatus.connect(self.actionsReportStatus)
        worker.progressAll.connect(self.pbAllProgress.setValue)
        worker.progressCalc.connect(self.pbCurrentProgress.setValue)
        worker.progressStep.connect(self.pbStepProgress.setValue)
        thread.started.connect(worker.run)
        # run
        thread.start()
        # manage thread and worker
        self.thread = thread
        self.worker = worker

        
    #
    # REPORTS
    #

    #
    # features and costs report

    def reportRunFeaturesAndCostsReport(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # set output file
        oFName = os.path.join(self.workingDir,'featcost.csv')
        f = open(oFName,'w')
        # features first
        f.write('"Features",,,,,,,,,,,,,,,,,,,,\n')
        f.write('"Marxan Id","Feature Name","Target Type","Target Value","Penalty"')
        f.write(',"Description","Feature Configuration Date","QMZ Id","GIS Calculation Date"\n')
        # grab required parts of dictionaries to shorten lines
        featRecs = self.workingDict['features']['recs']
        costRecs = self.workingDict['costs']['recs']
        # step through features to create list
        outLines = {}
        for key, feat in featRecs.iteritems():
            gKey = str(int(key.split('-')[0]))
            qmiFile = '%04d.qmi' % int(gKey)
            calcFName = os.path.join(self.workingDir,'qmzfiles',qmiFile)
            calcDate = datetime.datetime.fromtimestamp(os.path.getmtime(calcFName)).isoformat()
            ln = '"%d","%s","%s","%.03f","%.03f"' % (feat['exportnum'],feat['name'],feat['targettype'],float(feat['target']),float(feat['penalty']))
            ln += ',"%s","%s","%s","%s"\n' % (feat['description'],feat['editdate'],gKey,calcDate)
            outLines[feat['exportnum']] = ln
        # write list in key order
        for x in range(1,len(outLines)+1):
            f.write(outLines[x])
        # costs second
        f.write('"Costs",,,,,,,,,,,,,,,,,,,,\n')
        f.write('"Cost Name","Description","Cost Configuration Date","QMZ Id","GIS Calculation Date"\n')
        # step through costs
        outLines = []
        for key, cost in costRecs.iteritems():
            gKey = str(int(key.split('-')[0]))
            qmiFile = '%04d.qmi' % int(gKey)
            calcFName = os.path.join(self.workingDir,'qmzfiles',qmiFile)
            calcDate = datetime.datetime.fromtimestamp(os.path.getmtime(calcFName)).isoformat()
            ln = '"%s","%s","%s","%s","%s"' % (cost['name'],cost['description'],cost['editdate'],gKey,calcDate)
            outLines.append(ln)
        # write list
        for line in outLines:
            f.write(line)
        f.close()
        popupText = 'Creation of Features and Costs Report completed. The file featcost.csv can be found in the folder: %s' % self.workingDir
        QtGui.QMessageBox.information(self, 'Information', popupText, QtGui.QMessageBox.Ok)

    #
    # best results report

    def reportRunBestResultsResport(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        featRecs = self.workingDict['features']['recs']
        featKeys = {}
        # setup keys for reverse lookup
        for key, feat in featRecs.iteritems():
            featKeys[feat['exportnum']] = key
        #QgsMessageLog.logMessage(str(featKeys))
        # set output file
        oFName = os.path.join(self.workingDir,'best.csv')
        f = open(oFName,'w')
        header = '"Marxan Id","Feature Name","Target Type","Target Value"'
        header += ',"Total Available","Target Amount","Amount Conserved","Percent Conserved"'
        header += ',"Target Met"\n'
        f.write(header)
        # get totals
        mxTotals = os.path.join(self.workingDir,'marxan','MarOptTotalAreas.csv')
        tProb = open(mxTotals,'r')
        reader = csv.DictReader(tProb,delimiter = ',')
        totals = {}
        for row in reader:
            totals[row['spname']] = row
        tProb.close()
        #QgsMessageLog.logMessage(str(totals))
        # get solution results
        if self.workingDict['settings']['output']['recs']['savebest'] == "3-CSV":
            mxFile = os.path.join(self.workingDir,'marxan','output','output_mvbest.csv')
        else:
            mxFile = os.path.join(self.workingDir,'marxan','output','output_mvbest.txt')
        fBst = open(mxFile,'r')
        reader = csv.DictReader(fBst, delimiter = ',')
        outLines = {}
        for row in reader:
            #QgsMessageLog.logMessage(str(row))
            mxKey = int(row['Conservation Feature'])
            feat = featRecs[featKeys[mxKey]]
            if feat['targettype'] == 'Proportion':
                ln = '"%d","%s","%s","%.03f"' % (mxKey,feat['name'],feat['targettype'],float(feat['target'])*100)
            else:
                ln = '"%d","%s","%s","%.03f"' % (mxKey,feat['name'],feat['targettype'],float(feat['target']))
            available = float(totals[str(mxKey)]['totalarea'])
            held = float(row['Amount Held'])
            heldPercent = held/available * 100
            ln += ',"%.04f","%.04f","%.04f","%.02f"' % (available,float(row['Target']),held,heldPercent)
            ln += ',"%s"\n' % row['Target Met']
            outLines[mxKey] = ln
        fBst.close()
        # write list in key order
        for x in range(1,len(outLines)+1):
            f.write(outLines[x])
        f.close()
        popupText = 'Creation of Best Results Report completed. The file best.csv can be found in the folder: %s' % self.workingDir
        QtGui.QMessageBox.information(self, 'Information', popupText, QtGui.QMessageBox.Ok)


    #
    # file import
    #

    #
    # set import field

    def importSetField(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.leNewField.clear()
        if self.cbImportField.currentIndex() == 0:
            self.leNewField.setEnabled(True)
        else:
            self.leNewField.setDisabled(True)

    #
    # get text file

    def importSelectTextFile(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        outDir = os.path.join(self.workingDir,'marxan','output')
        ofn = QtGui.QFileDialog.getOpenFileName(self, 'Select file to import', outDir)
        self.leTextFile.setText(ofn)
        if os.path.exists(ofn):
            f = open(ofn)
            firstLine = f.readline().strip('\n')
            flds = firstLine.split(',')
            self.cbTextField.clear()
            for fld in flds:
                fldName = fld.strip('"')
                self.cbTextField.addItem(fldName)
            f.close()
            self.txtFile = ofn
        

        
    
