"""
# -*- coding: utf-8 -*-
#
# ========================================================
# 
# Purpose: Manage QMZ project and GIS settings
# Author: Trevor Wiens
# Copyright: Apropos Information Systems Inc.
# Date: 2014-12-30
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
from qgis.gui import *
from ui_settings_gis import Ui_dlgSettingsGIS
import math,os,json,shutil,datetime,inspect,glob
from calc_worker import calcContent
from qmz_utils import qmzCalcChecks

class qmzSettings(QtGui.QDialog, Ui_dlgSettingsGIS):

    #
    # initialization, connecting GUI controls to methods

    def __init__(self, iface):

        QtGui.QDialog.__init__(self)
        self.setupUi(self)
        self.iface = iface
        # qmz defaults
        self.qmzDir = None
        # project editing globals
        self.editDir = None
        self.editFile = None
        self.editDict = {}
        self.layerList = []
        # default project globals
        self.defaultDir = None
        self.workingDir = None
        self.workingDict = {}
        self.workingFile = None
        self.workingLoaded = False
        self.workingName = ''
        self.puLyr = None
        self.resultsLyr = None
        self.crs = None
        self.processStatus = 'Not started'
        self.calcList = []
        self.projStatus = 'Load'
        self.recStatus = 'None'
        # track if new gis key is used
        self.newGISKey = False
        # enable checks
        self.calcCheck = qmzCalcChecks()

        self.debug = False
        self.GISdebug = False
        if self.debug == True or self.GISdebug == True:
            self.myself = lambda: inspect.stack()[1][3]
            QgsMessageLog.logMessage(self.myself())

        # enable sorting of table(s)
        self.tblGIS.setSortingEnabled(True)
        self.tblProjectList.setSortingEnabled(True)
        
        # Connect methods to controls using signals
        # dialog control
        QtCore.QObject.connect(self.pbClose, QtCore.SIGNAL("clicked()"), self.closeDialog)
        QtCore.QObject.connect(self.cbWorkingProject, QtCore.SIGNAL("currentIndexChanged(int)"), self.projectLoadWorking)
        # Settings Tab
        # buttons
        QtCore.QObject.connect(self.tbMarxanPath, QtCore.SIGNAL("clicked()"), self.getMarxan)
        QtCore.QObject.connect(self.tbMarxanZonesPath, QtCore.SIGNAL("clicked()"), self.getMarxanZ)
        QtCore.QObject.connect(self.tbRPath, QtCore.SIGNAL("clicked()"), self.getR)
        QtCore.QObject.connect(self.tbQMZDir, QtCore.SIGNAL("clicked()"), self.getProjectDir)
        QtCore.QObject.connect(self.pbSaveQMZSettings, QtCore.SIGNAL("clicked()"), self.settingsWrite)
        QtCore.QObject.connect(self.pbCancelQMZSettings, QtCore.SIGNAL("clicked()"), self.settingsCancel)
        QtCore.QObject.connect(self.cbResultsLayer, QtCore.SIGNAL("currentIndexChanged(int)"), self.projectCreateResultsLayer)
        # content changes
        QtCore.QObject.connect(self.leMarxanPath, QtCore.SIGNAL("textChanged(QString)"), self.settingsEnableSave)
        QtCore.QObject.connect(self.leMarxanZonesPath, QtCore.SIGNAL("textChanged(QString)"), self.settingsEnableSave)
        QtCore.QObject.connect(self.leRPath, QtCore.SIGNAL("textChanged(QString)"), self.settingsEnableSave)
        QtCore.QObject.connect(self.leQMZDir, QtCore.SIGNAL("textChanged(QString)"), self.settingsEnableSave)
        # Projects Tab
        # buttons
        QtCore.QObject.connect(self.pbNewProject, QtCore.SIGNAL("clicked()"), self.projectNew)
        QtCore.QObject.connect(self.pbSaveProject, QtCore.SIGNAL("clicked()"), self.projectSave)
        QtCore.QObject.connect(self.pbCancelProject, QtCore.SIGNAL("clicked()"), self.projectCancel)
        QtCore.QObject.connect(self.pbDuplicateProject, QtCore.SIGNAL("clicked()"), self.projectDuplicate)
        QtCore.QObject.connect(self.tbQGISProject, QtCore.SIGNAL("clicked()"), self.qgisProjectGet)
        QtCore.QObject.connect(self.cbPlanningLayer, QtCore.SIGNAL("currentIndexChanged(int)"), self.projectUpdatePUFieldList)
        # project editing
        QtCore.QObject.connect(self.tblProjectList, QtCore.SIGNAL("itemSelectionChanged()"), self.projectSelect)
        # GIS Sources Tab
        # buttons
        QtCore.QObject.connect(self.pbNewGISSource, QtCore.SIGNAL("clicked()"), self.gisNewSource)
        QtCore.QObject.connect(self.pbSaveGISSource, QtCore.SIGNAL("clicked()"), self.gisSaveSource)
        QtCore.QObject.connect(self.pbCancelGISSource, QtCore.SIGNAL("clicked()"), self.gisDisableEditing)
        QtCore.QObject.connect(self.pbDeleteGISSource, QtCore.SIGNAL("clicked()"), self.gisDeleteSource)
        # update interface based on user actions
        QtCore.QObject.connect(self.tblGIS, QtCore.SIGNAL("itemSelectionChanged()"), self.gisSelect)
        QtCore.QObject.connect(self.cbGISStatus, QtCore.SIGNAL("currentIndexChanged(int)"), self.gisSetStatus)
        QtCore.QObject.connect(self.cbGISLayerType, QtCore.SIGNAL("currentIndexChanged(int)"), self.gisUpdateLayerList)
        QtCore.QObject.connect(self.cbGISLayer, QtCore.SIGNAL("currentIndexChanged(int)"), self.gisUpdateCalcFieldList)
        QtCore.QObject.connect(self.cbGISSingleMulti, QtCore.SIGNAL("currentIndexChanged(int)"), self.gisSetOuptut)
        QtCore.QObject.connect(self.cbGISMeasureType, QtCore.SIGNAL("currentIndexChanged(int)"), self.gisSetMeasure)
        QtCore.QObject.connect(self.cbGISCalcMethod, QtCore.SIGNAL("currentIndexChanged(int)"), self.gisSetCalcMethod)
        # Calculation Tab
        # buttons
        QtCore.QObject.connect(self.pbReport, QtCore.SIGNAL("clicked()"), self.calculationsCreateReport)
        QtCore.QObject.connect(self.cbActions, QtCore.SIGNAL("currentIndexChanged(int)"), self.calculationsSelectAction)
        QtCore.QObject.connect(self.pbCalculate, QtCore.SIGNAL("clicked()"), self.calculationsPerform)
        # switching tabs
        QtCore.QObject.connect(self.twSettingsGIS, QtCore.SIGNAL("currentChanged(int)"), self.calculationsClear)
        # Final Setup
        # configure gui
        self.setupGui()
        self.projStatus = 'Edit'
        
    #
    # basic gui setup and loading
    
    def setupGui(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # this populates everything if a proper project is selected
        self.settingsRead()
        # set gui appearance
        self.gisDisableEditing()
        if self.leMarxanPath.text() == '' or self.leMarxanZonesPath.text() == '':
            self.twSettingsGIS.setCurrentIndex(0)
        elif self.workingLoaded == True:
            self.twSettingsGIS.setCurrentIndex(2)
        else:
            self.twSettingsGIS.setCurrentIndex(1)
        # clear gis option controls
        self.cbGISMeasureType.clear()
        self.cbGISCalcField.clear()
        self.cbGISIntAction.clear()
        self.projectDisableEdit()
        self.lblGISId.setEnabled(False)
        self.spbxGISId.setEnabled(False)

    #
    # close dialog

    def closeDialog(self):

        self.close()
        

    #
    # QGIS settings functions
    #

    #
    # reading QGIS stored settings for QMZ
    
    def settingsRead(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        s = QtCore.QSettings()
        # marxan executable
        rv = s.value('QMarxanZ/MarxanExecutable')
        if rv == None:
            self.leMarxanPath.setText('')
        else:
            self.leMarxanPath.setText(rv)
        # marxan with zones executable
        rv = s.value('QMarxanZ/MarxanZonesExecutable')
        if rv == None:
            self.leMarxanZonesPath.setText('')
        else:
            self.leMarxanZonesPath.setText(rv)
        # R executable
        rv = s.value('QMarxanZ/RExecutable')
        if rv == None:
            self.leRPath.setText('')
        else:
            self.leRPath.setText(rv)
        # projects directory
        rv = s.value('QMarxanZ/projectsDir')
        if rv <> None and os.path.exists(rv):
            self.qmzDir = rv
        else:
            self.qmzDir = '.'
        self.leQMZDir.setText(self.qmzDir)
        # get project list
        self.projectLoadList()
        # default project
        rv = s.value('QMarxanZ/defaultProject')
        if rv <> None:
            defPath = os.path.join(self.qmzDir,str(rv))
            if os.path.exists(defPath):
                self.defaultDir = defPath
                self.leDefaultProject.setText(defPath)
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
        else:
            self.defaultDir = None

    #
    # settings cancel

    def settingsCancel(self):

        self.settingsRead()
        self.settingsDisableSave()

    #
    # writing QGIS settings for QMZ
    
    def settingsWrite(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        s = QtCore.QSettings()
        s.setValue('QMarxanZ/MarxanExecutable', self.leMarxanPath.text())
        s.setValue('QMarxanZ/MarxanZonesExecutable', self.leMarxanZonesPath.text())
        s.setValue('QMarxanZ/RExecutable', self.leRPath.text())
        self.qmzDir = self.leQMZDir.text()
        if s.value('QMarxanZ/projectsDir') <> self.qmzDir:
            s.setValue('QMarxanZ/defaultProject', None)
            s.setValue('QMarxanZ/projectsDir', self.qmzDir)
        self.projectLoadList()
        self.settingsDisableSave()


    #
    # Reading and writing qmzproj.qmz JSON configuration file(s)
    #

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
        self.tblProjectList.clear()
        self.tblProjectList.setColumnCount(1)
        self.tblProjectList.setRowCount(len(self.projList))
        self.tblProjectList.setHorizontalHeaderLabels(['Project Folder'])
        self.tblProjectList.setColumnWidth(0,200)
        self.cbWorkingProject.clear()
        self.cbWorkingProject.addItem('--None--')
        for key, value in self.projList.iteritems():
            # project table
            self.projectAddToTable(key,value[1])
            self.cbWorkingProject.addItem(value[1])
        if currentName <> '--None--':
            idx = self.cbWorkingProject.findText(currentName)
            if idx <> -1:
                self.cbWorkingProject.setCurrentIndex(idx)
            
    #
    # add project record into table

    def projectAddToTable(self,x,value):

        # project name
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value))
        item.setToolTip('Folder')
        self.tblProjectList.setItem(x,0,item)

    #
    # load working project for when not editing a project

    def projectLoadWorking(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        newDir = self.cbWorkingProject.currentText()
        loadProject = False
        # clear calculation reports
        self.calculationsClear()
        if newDir == '--None--':
            # define globals
            self.workingDir = None
            self.workingName = ''
            self.workingDict = {}
            self.workingFile = ''
            nTitle = 'No project: QMZ Settings, Project Management and Project GIS'
            self.workingLoaded = False
            self.pbNewGISSource.setDisabled(True)
            self.pbReport.setDisabled(True)
            self.tblGIS.clear()
            self.tblGIS.setColumnCount(0)
            self.tblGIS.setRowCount(0)
            # load blank project
            self.iface.newProject()
            self.setWindowTitle(nTitle)
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
                nTitle = '%s: QMZ Settings, Project Management and Project GIS' % self.workingName
                loadProject = True
                self.workingLoaded = True
                self.pbNewGISSource.setEnabled(True)
                self.pbReport.setEnabled(True)
                self.setWindowTitle(nTitle)
        if loadProject:
            self.qgisProjectLoad(self.workingDict['project']['qgisProject'],'working')
            self.gisLoadList()
        
    #
    # select project

    def projectSelect(self):

        if len(self.tblProjectList.selectedItems()) >  0:
            self.projectLoadInfo()
            self.projectDisplayInfo()
            self.projectEnableEdit()

    #
    # load project info for editing

    def projectLoadInfo(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if len(self.projList) > 0:
            projDir = self.tblProjectList.selectedItems()[0].text()
            projIdx = -1
            for key, value in self.projList.iteritems():
                if value[1] == projDir:
                    projIdx = key
            if projIdx >= 0:
                projName = self.projList[projIdx][0]
                self.editFile = os.path.join(self.qmzDir,projDir,'qmzproj.qmz')
                if not os.path.exists(self.editFile):
                    response = QtGui.QMessageBox.warning(self, 'Warning', "Can't find qmzproj.qmz file for %s. Please select it." % projName, QtGui.QMessageBox.Ok)
                    self.editFile = QtGui.QFileDialog.getOpenFileName(self,'Get qmzproj.qmz','*.qmz')
                if self.editFile <> '':
                    f = open(self.editFile,'r')
                    self.editDict = json.loads(f.read())
                    f.close()
                    self.editDir = self.editDict['project']['dirName']
                    if self.editDict['project']['qgisProject'] <> '':
                        self.qgisProjectLoad(self.editDict['project']['qgisProject'],'edit')
                    else:
                        self.iface.newProject()
                else:
                    self.projectCancel()

    #
    # display project info

    def projectDisplayInfo(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if len(self.editDict) > 0:
            # project name
            self.leProjectName.setText(self.editDict['project']['name'])
            # project type
            if self.editDict['project']['type'] == 'Marxan':
                self.cbProjectType.setCurrentIndex(0)
            else:
                self.cbProjectType.setCurrentIndex(1)
            # project dir name
            self.leProjectDir.setText(self.editDict['project']['dirName'])
            # project default
            if self.defaultDir <> None:
                pDir = os.path.split(self.defaultDir)[1]
                if pDir == self.editDict['project']['dirName']:
                    self.cbProjectIsDefault.setCurrentIndex(1)
                else:
                    self.cbProjectIsDefault.setCurrentIndex(0)
            else:
                self.cbProjectIsDefault.setCurrentIndex(0)
            # project description
            self.pteProjectDescription.setPlainText(self.editDict['project']['description'])
            # qgis project
            self.leQGISProject.setText(self.editDict['project']['qgisProject'])
            # study area layer
            saIdx = self.cbStudyAreaLayer.findText(self.editDict['project']['saLyr'])
            if saIdx > -1:
                self.cbStudyAreaLayer.setCurrentIndex(saIdx)
            else:
                self.cbStudyAreaLayer.setCurrentIndex(0)
            # planning layer
            cbIdx = self.cbPlanningLayer.findText(self.editDict['project']['puLyr'])
            if cbIdx > -1:
                self.cbPlanningLayer.setCurrentIndex(cbIdx)
            else:
                self.cbPlanningLayer.setCurrentIndex(0)
            # puid
            idx  = self.cbPUField.findText(self.editDict['project']['puid'])
            if idx > -1:
                self.cbPUField.setCurrentIndex(idx)
            else:
                self.cbPUField.setCurrentIndex(0)
            # results layer
            cbIdx = self.cbResultsLayer.findText(self.editDict['project']['resultsLyr'])
            if cbIdx > -1:
                self.cbResultsLayer.setCurrentIndex(cbIdx)
            else:
                self.cbResultsLayer.setCurrentIndex(0)

    #
    # new project

    def projectNew(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        pdName, ok = QtGui.QInputDialog.getText(self,"Enter directory name for new project",
            "Directory name:")
        if ok and pdName <> '':
            dn = pdName.replace(' ','')
            self.editDir = os.path.join(self.qmzDir,pdName)
            if not os.path.exists(self.editDir):
                os.mkdir(self.editDir)
                os.mkdir(os.path.join(self.editDir,'qmzfiles'))
                os.mkdir(os.path.join(self.editDir,'marxan'))
                os.mkdir(os.path.join(self.editDir,'marxan','input'))
                os.mkdir(os.path.join(self.editDir,'marxan','output'))
                os.mkdir(os.path.join(self.editDir,'marxan','pu'))
                self.leProjectDir.setText(dn)
                self.editFile = os.path.join(self.editDir,'qmzproj.qmz')
                f = open(self.editFile,'w')
                eDate = datetime.datetime.now().isoformat()
                self.editDict = {'project': { 'name':'New Project', \
                'type':'Marxan', 'description':'A new project', 'resultsLyr':'', \
                'dirName':dn, 'qgisProject':'', 'puLyr':'', 'saLyr':'', 'puid':''}}
                self.editDict['gis'] = {'recs':{},'editdate':eDate,'lastkey':0}
                self.editDict['features'] = {'recs':{},'editdate':eDate}
                self.editDict['costs'] = {'recs':{},'editdate':eDate}
                self.editDict['zoneinfo'] = {'zones':{'recs':{},'editdate':eDate}, \
                    'zonetargets':{'recs':{},'editdate':eDate}, \
                    'zonecontributions':{'recs':{},'editdate':eDate}, \
                    'zoneboundarycosts':{'recs':{},'editdate':eDate}, \
                    'zonecosts':{'recs':{},'editdate':eDate} }
                self.editDict['settings'] = {'general':{'recs':{},'editdate':eDate},\
                    'boundary':{'recs':{},'editdate':eDate}, \
                    'other':{'recs':{},'editdate':eDate}, \
                    'output':{'recs':{},'editdate':eDate} }
                f.write(json.dumps(self.editDict))
                f.close()
                self.projectLoadList()
            else:
                ok = QtGui.QMessageBox.critical(self,'Error',"Directory '%s' exists. Name must be unique" % self.editDir, QtGui.QMessageBox.Ok)

    #
    # save project

    def projectSave(self):

        deleteFiles = False
        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # write changes to disk
        workingName = self.cbWorkingProject.currentText()
        oldName = self.editDict['project']['name']
        newName = self.leProjectName.text()
        if self.editDict['project']['name'] <> newName:
            self.editDict['project']['name'] = newName
        self.editDict['project']['name'] = self.leProjectName.text()
        self.editDict['project']['type'] = self.cbProjectType.currentText()
        self.editDict['project']['description'] = self.pteProjectDescription.document().toPlainText()
        self.editDict['project']['qgisProject'] = self.leQGISProject.text()
        if self.cbPlanningLayer.currentText() <> self.editDict['project']['puLyr']:
            deleteFiles = True
            self.editDict['project']['puLyr'] = self.cbPlanningLayer.currentText()
        self.editDict['project']['puid'] = self.cbPUField.currentText()
        self.editDict['project']['saLyr'] = self.cbStudyAreaLayer.currentText()
        self.editDict['project']['resultsLyr'] = self.cbResultsLayer.currentText()
        f = open(self.editFile,'w')
        f.write(json.dumps(self.editDict))
        f.close()
        # if qmd and marxan files need to be deleted do that now
        if deleteFiles:
            marxanInputDir = os.path.join(self.qmzDir,self.editDict['project']['dirName'],'marxan','input')
            for fName in glob.glob(marxanInputDir + '/*'):
                os.remove(fName)
            qmzDir = os.path.join(self.qmzDir,self.editDict['project']['dirName'],'qmzfiles')
            for fName in glob.glob(qmzDir + '/*'):
                os.remove(fName)
        # check defaults
        s = QtCore.QSettings()
        rv = s.value('QMarxanZ/defaultProject')
        if self.cbProjectIsDefault.currentIndex() == 1:
            # edited project IS default
            self.defaultDir = self.editDict['project']['dirName']
            s.setValue('QMarxanZ/defaultProject', self.defaultDir)
            self.leDefaultProject.setText(self.defaultDir)
        elif self.cbProjectIsDefault.currentIndex() == 0:
            if rv == self.editDict['project']['dirName']:
                # editing project WAS default but not default now
                self.defaultDir = None
                s.setValue('QMarxanZ/defaultProject', self.defaultDir)
                self.leDefaultProject.setText('')
        # check if edit project needs to be closed
        if self.workingDict == {}:
            self.iface.newProject()
        else:
            # check if edit project is the same as the working project
            if self.editDict['project']['dirName'] == self.workingDict['project']['dirName']:
                # no need to clear and reload the project
                # update edits to workingDict
                self.workingDict = self.editDict
            else:
                # edit project is not the same as the working project
                # clear edit project
                self.cbWorkingProject.setCurrentIndex(0)
                # reload working project
                idx = self.cbWorkingProject.findText(workingName)
                if idx <> -1:
                    self.cbWorkingProject.setCurrentIndex(idx)
        # disable editing
        self.projectDisableEdit()

    #
    # project cancel

    def projectCancel(self):

        # close existing project
        self.iface.newProject()
        # check if edit project needs to be closed
        workingName = self.cbWorkingProject.currentText()
        if self.workingDict == {}:
            self.iface.newProject()
        else:
            # check if edit project is the same as the working project
            if self.editDict['project']['dirName'] <> self.workingDict['project']['dirName']:
                # edit project is not the same as the working project
                # clear edit project
                self.cbWorkingProject.setCurrentIndex(0)
                # reload working project
                idx = self.cbWorkingProject.findText(workingName)
                if idx <> -1:
                    self.cbWorkingProject.setCurrentIndex(idx)
        # disable editing
        self.projectDisableEdit()
        
    #
    # duplicate project

    def projectDuplicate(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        pdName, ok = QtGui.QInputDialog.getText(self,"Enter directory name for project copy",
            "Directory name:")
        if ok and pdName <> '':
            dn = pdName.replace(' ','')
            newDir = os.path.join(self.leQMZDir.text(),dn)
            if not os.path.exists(newDir):
                os.mkdir(newDir)
                #os.mkdir(os.path.join(newDir,'marxan'))
                sd = os.path.join(self.editDir,'qmzfiles')
                dd = os.path.join(newDir,'qmzfiles')
                shutil.copytree(sd,dd)
                sd = os.path.join(self.editDir,'marxan')
                dd = os.path.join(newDir,'marxan')
                shutil.copytree(sd,dd)
                sf = os.path.join(self.editDir,'qmzproj.qmz')
                df = os.path.join(newDir,'qmzproj.qmz')
                shutil.copy(sf,df)
                f = open(df,'r')
                tempDict = json.loads(f.read())
                f.close()
                tempDict['project']['name'] = 'Copy of ' + tempDict['project']['name']
                tempDict['project']['dirName'] = dn
                f = open(df,'w')
                f.write(json.dumps(tempDict))
                f.close()
                self.projectLoadList()
            else:
                ok = QtGui.QMessageBox.critical(self,'Error',"Directory '%s' exists. Name must be unique" % newDir, QtGui.QMessageBox.Ok)
        self.projectDisableEdit()

    #
    # update pulayer field list for selection of puid

    def projectUpdatePUFieldList(self):

        tempPULyr = None
        for x in range(len(self.layerList)):
            if self.layerList[x][0] == 'area' and self.layerList[x][1] == self.cbPlanningLayer.currentText():
                tempPULyr = self.layerList[x][3]
        if tempPULyr <> None:
            self.cbPUField.clear()
            fields = tempPULyr.dataProvider().fields()
            for field in fields:
                if field.typeName() in ('Integer'):
                    self.cbPUField.addItem(field.name())

    #
    # create results PU layer if selected

    def projectCreateResultsLayer(self):

        if self.cbResultsLayer.currentText() == 'Create Results Layer':
            if self.debug == True:
                QgsMessageLog.logMessage(self.myself())
            res = QtGui.QMessageBox.warning(self, 'Warning',
               "Do you want to create a results layer?", QtGui.QMessageBox.Yes|QtGui.QMessageBox.No)
            if res == QtGui.QMessageBox.Yes:
                self.twSettingsGIS.setDisabled(True)
                res = QtGui.QMessageBox.warning(self,'Warning',
                    'Please be patient. This may take a little while', QtGui.QMessageBox.Ok)
                layerName = '%sresults.shp' % self.editDir
                fName = os.path.join(self.qmzDir,self.editDir,'marxan','pu', layerName)
                fields = QgsFields()
                fields.append(QgsField("puid", QtCore.QVariant.Int))
                check = QtCore.QFile(fName)
                if check.exists():
                    if not QgsVectorFileWriter.deleteShapeFile(fName):
                        return
                if self.editPULyr <> None:
                    writer = QgsVectorFileWriter(fName, u'UTF-8', fields, QGis.WKBPolygon, self.crs, 'ESRI Shapefile')
                    outFeat = QgsFeature()
                    outFeat.setFields(fields)
                    srcFields = self.editPULyr.dataProvider().fields()
                    puidIdx = srcFields.indexFromName(self.editDict['project']['puid'])
                    featIter = self.editPULyr.getFeatures()
                    for feat in featIter:
                        puid = feat.attributes()[puidIdx]
                        outFeat.setGeometry(feat.geometry())
                        outFeat.setAttribute(0, puid)
                        writer.addFeature(outFeat)
                    # close writer
                    del writer
                    vlayer = QgsVectorLayer(fName, layerName, "ogr")
                    QgsMapLayerRegistry.instance().addMapLayer(vlayer)
                    self.iface.actionSaveProject().trigger()
                    self.qgisRefreshLayers('edit')
                    self.projectDisplayInfo()
                    res = QtGui.QMessageBox.information(self,'Information',
                        '%s created and added to QGIS project.' % layerName, QtGui.QMessageBox.Ok)
                    cbIdx = self.cbResultsLayer.findText(layerName)
                    if cbIdx > -1:
                        self.cbResultsLayer.setCurrentIndex(cbIdx)
                    else:
                        self.cbResultsLayer.setCurrentIndex(0)
                else:
                    res = QtGui.QMessageBox.warning(self,'Warning',
                        'No Source PU layer set and saved. Could not proceed.', QtGui.QMessageBox.Ok)
                self.twSettingsGIS.setEnabled(True)
            else:
                self.cbResultsLayer.setCurrentIndex(0)
                
    #
    # GUI methods for QMarxanZ Settings and Projects Panel
    #

    #
    # enable save settings

    def settingsEnableSave(self):

        if self.projStatus <> 'Load':
            if self.debug == True:
                QgsMessageLog.logMessage(self.myself())
            self.pbSaveQMZSettings.setEnabled(True)
            self.pbCancelQMZSettings.setEnabled(True)
            self.pbClose.setDisabled(True)
            self.twSettingsGIS.tabBar().setDisabled(True)

    #
    # disable save settings

    def settingsDisableSave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.pbSaveQMZSettings.setDisabled(True)
        self.pbCancelQMZSettings.setDisabled(True)
        self.pbClose.setEnabled(True)
        self.twSettingsGIS.tabBar().setEnabled(True)

    #
    # get Marxan with Zones executable

    def getMarxanZ(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        executable = QtGui.QFileDialog.getOpenFileName(self, 'Select Marxan with Zones executable')
        if executable <> '':
            self.leMarxanZonesPath.setText(executable)
        else:
            self.leMarxanZonesPath.setText('')

    #
    # get Marxan executable

    def getMarxan(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        executable = QtGui.QFileDialog.getOpenFileName(self, 'Select Marxan executable')
        if executable <> '':
            self.leMarxanPath.setText(executable)
        else:
            self.leMarxanPath.setText('')

    #
    # get R executable

    def getR(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        executable = QtGui.QFileDialog.getOpenFileName(self, 'Select R executable')
        if executable <> '':
            self.leRPath.setText(executable)
        else:
            self.leRPath.setText('')

    #
    # get project dir

    def getProjectDir(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        dirName = QtGui.QFileDialog.getExistingDirectory(self, 'Select QMZ Projects Directory')
        if dirName <> '':
            self.leQMZDir.setText(dirName)
        else:
            self.leQMZDir.setText('')

    #
    # enable project edit
    
    def projectEnableEdit(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # working project selection
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)
        # edit controls
        self.frProjectControls1.setEnabled(True)
        self.frProjectControls2.setEnabled(True)
        # buttons
        self.pbNewProject.setDisabled(True)
        self.pbDuplicateProject.setEnabled(True)
        # list widget
        self.tblProjectList.setDisabled(True)
        self.pbClose.setDisabled(True)
        self.twSettingsGIS.tabBar().setDisabled(True)
        # save / cancel buttons
        self.pbSaveProject.setEnabled(True)
        self.pbCancelProject.setEnabled(True)

    #
    # disable project edit

    def projectDisableEdit(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.tblProjectList.clearSelection()
        # working project selection
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)
        # edit controls
        self.frProjectControls1.setDisabled(True)
        self.frProjectControls2.setDisabled(True)
        # clear values
        self.leProjectName.setText('')
        self.pteProjectDescription.setPlainText('')
        self.leProjectDir.setText('')
        self.leQGISProject.setText('')
        self.cbPlanningLayer.clear()
        self.cbStudyAreaLayer.clear()
        self.cbPUField.clear()
        # buttons
        self.pbNewProject.setEnabled(True)
        self.pbDuplicateProject.setDisabled(True)
        # list widget
        self.tblProjectList.setEnabled(True)
        self.pbClose.setEnabled(True)
        self.twSettingsGIS.tabBar().setEnabled(True)
        # save / cancel buttons
        self.pbSaveProject.setDisabled(True)
        self.pbCancelProject.setDisabled(True)

    #
    # get QGIS project

    def qgisProjectGet(self):

        projectName = QtGui.QFileDialog.getOpenFileName(self, 'Select QGIS project', self.qmzDir, '*.qgs')
        if os.path.exists(projectName):
            self.leQGISProject.setText(projectName)

    #
    # load QGIS project

    def qgisProjectLoad(self,qgisProject,projectType):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if QgsProject.instance().fileName() <> qgisProject:
            self.iface.newProject()
            result = QgsProject.instance().read(QtCore.QFileInfo(qgisProject))
        else:
            result = True
        if result == True:
            self.qgisRefreshLayers(projectType)
        self.crs = self.iface.mapCanvas().mapSettings().destinationCrs()

    #
    # refresh QGIS project layers

    def qgisRefreshLayers(self,projectType):

        self.cbStudyAreaLayer.clear()
        self.cbPlanningLayer.clear()
        self.cbResultsLayer.clear()
        self.cbPUField.clear()
        if projectType == 'edit':
            self.cbPlanningLayer.addItem('--Not Set--')
            self.cbStudyAreaLayer.addItem('--Not Set--')
            self.cbResultsLayer.addItem('--Not Set--')
            self.cbResultsLayer.addItem('Create Results Layer')
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
                    if projectType == 'edit':
                        self.cbPlanningLayer.addItem(layer.name())
                        self.cbStudyAreaLayer.addItem(layer.name())
                        self.cbResultsLayer.addItem(layer.name())
                        if layer.name() == self.editDict['project']['puLyr']:
                            self.editPULyr = layer
                    elif projectType == 'working':
                        if self.workingDict <> {} and layer.name() == self.workingDict['project']['puLyr']:
                            self.puLyr = layer


    #
    # GIS
    #

    #
    # GIS - load GIS Source List

    def gisLoadList(self):

        if self.GISdebug == True:
            QgsMessageLog.logMessage(self.myself())
        # load data
        zDict = self.workingDict['gis']['recs']
        rc = len(zDict)
        # clear GIS controls
        self.tblGIS.clear()
        self.tblGIS.setColumnCount(2)
        self.tblGIS.setRowCount(rc)
        self.tblGIS.setHorizontalHeaderLabels(['Id','Name'])
        self.tblGIS.setColumnWidth(0,50)
        self.tblGIS.setColumnWidth(1,200)
        x = 0
        for key, value in zDict.iteritems():
            # GIS table
            self.gisAddToTable(x,key,value['name'])
            x += 1

    #
    # GIS - set GIS record into table

    def gisAddToTable(self,x,key,value):

        if self.GISdebug == True:
            QgsMessageLog.logMessage(self.myself())
        # id
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(key))
        item.setToolTip('Id')
        self.tblGIS.setItem(x,0,item)
        # user name
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value))
        item.setToolTip('Name')
        self.tblGIS.setItem(x,1,item)
        
    #
    #  GIS - select GIS source

    def gisSelect(self):

        if self.GISdebug == True:
            QgsMessageLog.logMessage(self.myself())
        if len(self.tblGIS.selectedItems()) > 0:
            self.newGISKey = False
            self.gisEnableEditing()
            self.gisLoadSource()

    #
    #  GIS - create new GIS source

    def gisNewSource(self):

        if self.GISdebug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['gis']['recs']
        newId = self.workingDict['gis']['lastkey'] + 1
        self.newGISKey = True
        self.spbxGISId.setValue(newId)
        self.leGISName.setText('New GIS Source')
        self.pteGISDescription.setPlainText('')
        self.leGISDataProvider.setText('')
        self.cbGISStatus.setCurrentIndex(0)
        self.cbGISLayerType.setCurrentIndex(0)
        self.cbGISLayer.setCurrentIndex(0)
        self.cbGISSingleMulti.setCurrentIndex(0)
        self.cbGISMeasureType.setCurrentIndex(0)
        self.cbGISCalcField.setCurrentIndex(0)
        self.cbGISIntAction.setCurrentIndex(0)
        self.cbGISCalcMethod.setCurrentIndex(0)
        self.spbxGISPixelSize.setValue(0)
        self.gisEnableEditing()
        self.gisSetStatus()
        self.pbDeleteGISSource.setDisabled(True)

    #
    #  GIS - load GIS source for editing

    def gisLoadSource(self):

        if self.GISdebug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['gis']['recs']
        cr = self.tblGIS.currentRow()
        if cr > -1:
            self.recStatus = 'Load'
            zId = int(self.tblGIS.item(cr,0).text())
            #QgsMessageLog.logMessage(str(zDict[str(zId)]))
            self.spbxGISId.setValue(zId)
            self.leGISName.setText(zDict[str(zId)]['name'])
            self.pteGISDescription.setPlainText(zDict[str(zId)]['description'])
            self.leGISDataProvider.setText(zDict[str(zId)]['dataprovider'])
            #
            idx = self.cbGISStatus.findText(zDict[str(zId)]['status'])
            if idx == -1:
                idx = 0
            self.recStatus = 'Edit'
            if idx == self.cbGISStatus.currentIndex():
                self.gisSetStatus()
            else:
                self.cbGISStatus.setCurrentIndex(idx)
            self.recStatus = 'Load'
            #
            if zDict[str(zId)]['status'] == 'GIS Source':
                idx = self.cbGISLayerType.findText(zDict[str(zId)]['layertype'])
                if idx == -1:
                    idx = 0
                if idx == self.cbGISLayerType.currentIndex():
                    self.gisUpdateLayerList()
                else:
                    self.cbGISLayerType.setCurrentIndex(idx)
                #
                idx = self.cbGISLayer.findText(zDict[str(zId)]['layername'])
                if idx == -1:
                    idx = 0
                self.cbGISLayer.setCurrentIndex(idx)
                #
                idx = self.cbGISSingleMulti.findText(zDict[str(zId)]['singlemulti'])
                if idx == -1:
                    idx = 0
                self.cbGISSingleMulti.setCurrentIndex(idx)
                #
                idx = self.cbGISMeasureType.findText(zDict[str(zId)]['measuretype'])
                if idx == -1:
                    idx = 0
                self.cbGISMeasureType.setCurrentIndex(idx)
                #
                idx = self.cbGISIntAction.findText(zDict[str(zId)]['intaction'])
                if idx == -1:
                    idx = 0
                self.cbGISIntAction.setCurrentIndex(idx)
                #
                idx = self.cbGISCalcMethod.findText(zDict[str(zId)]['calcmethod'])
                if idx == -1:
                    idx = 0
                self.cbGISCalcMethod.setCurrentIndex(idx)
                #
                tval = zDict[str(zId)]['pixelsize']
                if tval == '':
                    tval = 0
                self.spbxGISPixelSize.setValue(int(tval))
            #
            idx = self.cbGISCalcField.findText(zDict[str(zId)]['calcfield'])
            if idx == -1:
                idx = 0
            self.cbGISCalcField.setCurrentIndex(idx)

    #
    #  GIS - save GIS source after editing

    def gisSaveSource(self):

        if self.GISdebug == True:
            QgsMessageLog.logMessage(self.myself())
        zId = str(self.spbxGISId.value())
        zName = self.leGISName.text().replace('-',' ')
        if self.newGISKey:
            self.workingDict['gis']['lastkey'] += 1
            self.newGISKey = False
        if not zId in self.workingDict['gis']['recs']:
            self.workingDict['gis']['recs'][zId] = {}
        self.workingDict['gis']['recs'][zId]['name'] = zName
        self.workingDict['gis']['recs'][zId]['description'] = self.pteGISDescription.document().toPlainText()
        self.workingDict['gis']['recs'][zId]['dataprovider'] = self.leGISDataProvider.text()
        self.workingDict['gis']['recs'][zId]['status'] = self.cbGISStatus.currentText()
        if self.cbGISStatus.currentIndex() == 3:
            srcIdx = -1
            for x in range(len(self.layerList)):
                if self.layerList[x][0] == self.cbGISLayerType.currentText().lower() and \
                self.layerList[x][1] == self.cbGISLayer.currentText():
                    srcIdx = x
                    break
            if srcIdx <> -1:
                #self.workingDict['gis']['recs'][zId]['gissource'] = self.layerList[srcIdx][2]
                self.workingDict['gis']['recs'][zId]['layertype'] = self.cbGISLayerType.currentText()
                self.workingDict['gis']['recs'][zId]['layername'] = self.cbGISLayer.currentText()
                self.workingDict['gis']['recs'][zId]['singlemulti'] = self.cbGISSingleMulti.currentText()
                self.workingDict['gis']['recs'][zId]['measuretype'] = self.cbGISMeasureType.currentText()
                self.workingDict['gis']['recs'][zId]['calcfield'] = self.cbGISCalcField.currentText()
                self.workingDict['gis']['recs'][zId]['intaction'] = self.cbGISIntAction.currentText()
                self.workingDict['gis']['recs'][zId]['calcmethod'] = self.cbGISCalcMethod.currentText()
                self.workingDict['gis']['recs'][zId]['pixelsize'] = self.spbxGISPixelSize.value()
            else:
                self.workingDict['gis']['recs'][zId]['status'] = 'No Data'
                #self.workingDict['gis']['recs'][zId]['gissource'] = ''
                self.workingDict['gis']['recs'][zId]['layertype'] = ''
                self.workingDict['gis']['recs'][zId]['layername'] = ''
                self.workingDict['gis']['recs'][zId]['singlemulti'] = ''
                self.workingDict['gis']['recs'][zId]['measuretype'] = ''
                self.workingDict['gis']['recs'][zId]['calcfield'] = ''
                self.workingDict['gis']['recs'][zId]['intaction'] = ''
                self.workingDict['gis']['recs'][zId]['calcmethod'] = ''
                self.workingDict['gis']['recs'][zId]['pixelsize'] = ''
        elif self.cbGISStatus.currentIndex() == 2:
            srcIdx = -1
            for x in range(len(self.layerList)):
                if self.layerList[x][1] == self.workingDict['project']['puLyr']:
                    srcIdx = x
                    break
            if srcIdx <> -1:
                #self.workingDict['gis']['recs'][zId]['gissource'] = self.layerList[srcIdx][2]
                self.workingDict['gis']['recs'][zId]['layername'] = self.layerList[srcIdx][1]
                self.workingDict['gis']['recs'][zId]['calcfield'] = self.cbGISCalcField.currentText()
                # set remaining values to blank
                self.workingDict['gis']['recs'][zId]['layertype'] = ''
                self.workingDict['gis']['recs'][zId]['singlemulti'] = ''
                self.workingDict['gis']['recs'][zId]['measuretype'] = ''
                self.workingDict['gis']['recs'][zId]['intaction'] = ''
                self.workingDict['gis']['recs'][zId]['calcmethod'] = ''
                self.workingDict['gis']['recs'][zId]['pixelsize'] = ''
            else:
                self.workingDict['gis']['recs'][zId]['status'] = 'No Data'
                #self.workingDict['gis']['recs'][zId]['gissource'] = ''
                self.workingDict['gis']['recs'][zId]['layertype'] = ''
                self.workingDict['gis']['recs'][zId]['layername'] = ''
                self.workingDict['gis']['recs'][zId]['singlemulti'] = ''
                self.workingDict['gis']['recs'][zId]['measuretype'] = ''
                self.workingDict['gis']['recs'][zId]['calcfield'] = ''
                self.workingDict['gis']['recs'][zId]['intaction'] = ''
                self.workingDict['gis']['recs'][zId]['calcmethod'] = ''
                self.workingDict['gis']['recs'][zId]['pixelsize'] = ''
        else:
            # no data or waiting
            #self.workingDict['gis']['recs'][zId]['gissource'] = ''
            self.workingDict['gis']['recs'][zId]['layertype'] = ''
            self.workingDict['gis']['recs'][zId]['layername'] = ''
            self.workingDict['gis']['recs'][zId]['singlemulti'] = ''
            self.workingDict['gis']['recs'][zId]['measuretype'] = ''
            self.workingDict['gis']['recs'][zId]['calcfield'] = ''
            self.workingDict['gis']['recs'][zId]['intaction'] = ''
            self.workingDict['gis']['recs'][zId]['calcmethod'] = ''
            self.workingDict['gis']['recs'][zId]['pixelsize'] = ''
        self.workingDict['gis']['recs'][zId]['editdate'] = datetime.datetime.now().isoformat()
        self.workingDict['gis']['editdate'] = datetime.datetime.now().isoformat()
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        self.gisDisableEditing()
        self.gisLoadList()

    #
    # GIS - delete GIS source

    def gisDeleteSource(self):
        
        if self.GISdebug == True:
            QgsMessageLog.logMessage(self.myself())
        zId = str(self.spbxGISId.value())
        # do some checks against dependent entries to ensure this is ok
        key = '%04d' % int(zId)
        messageText = ''
        isOk = True
        if key in self.workingDict['features']['recs']:
            isOk = False
            messageText += 'it is used as a feature'
        if key in self.workingDict['costs']['recs']:
            isOk = False
            if messageText == '':
                messageText += 'it is used as a cost'
            else:
                messageText += ' and a cost'
        if isOk:
            res = QtGui.QMessageBox.warning(self, 'Warning',
               "Are you sure you want to delete this GIS source?", QtGui.QMessageBox.Yes|QtGui.QMessageBox.No)
            if res == QtGui.QMessageBox.No:
                isOk = False
        else:
            popupText = "You can not delete this GIS source because %s. " % messageText
            popupText += "GIS sources must be free of dependencies before they are del."
            QtGui.QMessageBox.warning(self, 'Warning', popupText, QtGui.QMessageBox.Ok)
        if isOk:
            del self.workingDict['gis']['recs'][zId]
            self.workingDict['gis']['editdate'] = datetime.datetime.now().isoformat()
            filesDir = os.path.join(self.workingDir,'qmzfiles',key+'*')
            files = glob.glob(filesDir)
            for f in files:
                os.remove(f) 
            f = open(self.workingFile,'w')
            f.write(json.dumps(self.workingDict))
            f.close()
            self.gisLoadList()
        self.gisDisableEditing()

    #
    # GIS - enable GIS source editing

    def gisEnableEditing(self):

        if self.GISdebug == True:
            QgsMessageLog.logMessage(self.myself())
        # working project selection
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)
        # controls
        self.tblGIS.setDisabled(True)
        self.frGISControls1.setEnabled(True)
        self.frGISControls2.setEnabled(True)
        self.frGISControls3.setEnabled(True)
        self.frGISControls4.setEnabled(True)
        # buttons
        self.pbNewGISSource.setDisabled(True)
        self.pbSaveGISSource.setEnabled(True)
        self.pbCancelGISSource.setEnabled(True)
        self.pbDeleteGISSource.setEnabled(True)
        # main form
        self.pbClose.setDisabled(True)
        self.twSettingsGIS.tabBar().setDisabled(True)

    #
    # GIS - set GIS source status

    def gisSetStatus(self):

        if self.recStatus <> 'Load':
            if self.GISdebug == True:
                QgsMessageLog.logMessage(self.myself())
            if self.cbGISStatus.currentIndex() == 3:
                # gis data source
                self.lblGISLayerType.setEnabled(True)
                self.cbGISLayerType.setEnabled(True)
                self.lblGISLayer.setEnabled(True)
                self.cbGISLayer.setEnabled(True)
                self.lblGISSingleMulti.setEnabled(True)
                self.cbGISSingleMulti.setEnabled(True)
                self.lblGISMeasureType.setEnabled(True)
                self.cbGISMeasureType.setEnabled(True)
                self.lblGISIntAction.setEnabled(True)
                self.cbGISIntAction.setEnabled(True)
                self.gisUpdateLayerList()
            elif self.cbGISStatus.currentIndex() == 2:
                # pu layer
                self.lblGISLayerType.setDisabled(True)
                self.cbGISLayerType.setDisabled(True)
                self.lblGISLayer.setDisabled(True)
                self.cbGISLayer.setDisabled(True)
                self.lblGISSingleMulti.setDisabled(True)
                self.cbGISSingleMulti.setDisabled(True)
                self.lblGISCalcField.setEnabled(True)
                self.cbGISCalcField.setEnabled(True)
                self.lblGISMeasureType.setDisabled(True)
                self.cbGISMeasureType.setDisabled(True)
                self.lblGISIntAction.setDisabled(True)
                self.cbGISIntAction.setDisabled(True)
                self.lblGISCalcMethod.setDisabled(True)
                self.cbGISCalcMethod.setDisabled(True)
                self.lblGISPixelSize.setDisabled(True)
                self.spbxGISPixelSize.setDisabled(True)
                self.gisSetOuptut()
                self.gisUpdateCalcFieldList()
            else:
                # no data or waiting
                self.lblGISLayerType.setDisabled(True)
                self.cbGISLayerType.setDisabled(True)
                self.lblGISLayer.setDisabled(True)
                self.cbGISLayer.setDisabled(True)
                self.lblGISSingleMulti.setDisabled(True)
                self.cbGISSingleMulti.setDisabled(True)
                self.lblGISCalcField.setDisabled(True)
                self.cbGISCalcField.setDisabled(True)
                self.lblGISMeasureType.setDisabled(True)
                self.cbGISMeasureType.setDisabled(True)
                self.lblGISIntAction.setDisabled(True)
                self.cbGISIntAction.setDisabled(True)
            
    #
    # GIS - update GIS layer list
    
    def gisUpdateLayerList(self):

        if self.GISdebug == True:
            QgsMessageLog.logMessage(self.myself())
        self.recStatus = 'Load'
        self.cbGISLayer.clear()
        if self.cbGISLayerType.isEnabled():
            if self.cbGISLayerType.currentText() == 'Point':
                self.lblGISCalcMethod.setDisabled(True)
                self.cbGISCalcMethod.setDisabled(True)
                self.lblGISPixelSize.setDisabled(True)
                self.spbxGISPixelSize.setDisabled(True)
                for x in range(len(self.layerList)):
                    if self.layerList[x][0] == 'point':
                        self.cbGISLayer.addItem(self.layerList[x][1])
            elif self.cbGISLayerType.currentText() == 'Line':
                self.lblGISCalcMethod.setDisabled(True)
                self.cbGISCalcMethod.setDisabled(True)
                self.lblGISPixelSize.setDisabled(True)
                self.spbxGISPixelSize.setDisabled(True)
                for x in range(len(self.layerList)):
                    if self.layerList[x][0] == 'line':
                        self.cbGISLayer.addItem(self.layerList[x][1])
            elif self.cbGISLayerType.currentText() == 'Area':
                self.lblGISCalcMethod.setEnabled(True)
                self.cbGISCalcMethod.setEnabled(True)
                for x in range(len(self.layerList)):
                    if self.layerList[x][0] == 'area':
                        self.cbGISLayer.addItem(self.layerList[x][1])
            if self.cbGISLayerType.currentText() == 'Raster':
                self.lblGISSingleMulti.setEnabled(True)
                self.cbGISSingleMulti.setEnabled(True)
                self.lblGISCalcField.setDisabled(True)
                self.cbGISCalcField.setDisabled(True)
                self.lblGISCalcMethod.setDisabled(True)
                self.cbGISCalcMethod.setDisabled(True)
                self.lblGISPixelSize.setDisabled(True)
                self.spbxGISPixelSize.setDisabled(True)
                for x in range(len(self.layerList)):
                    if self.layerList[x][0] == 'raster':
                        self.cbGISLayer.addItem(self.layerList[x][1])
        self.recStatus = 'Edit'
        self.gisUpdateCalcFieldList()
        self.gisSetOuptut()

    #
    # GIS - update GIS calc field list
    
    def gisUpdateCalcFieldList(self):

        if self.recStatus <> 'Load':
            self.cbGISCalcField.clear()
            fields = []
            if self.GISdebug == True:
                QgsMessageLog.logMessage(self.myself())
            proceed = False
            if self.cbGISLayerType.currentText() == 'Raster':
                for x in range(len(self.layerList)):
                    if self.layerList[x][1] == self.cbGISLayer.currentText():
                        pixelSize = min(self.layerList[x][3].rasterUnitsPerPixelX(),self.layerList[x][3].rasterUnitsPerPixelY())
                        self.spbxGISPixelSize.setValue(pixelSize)
            if self.cbGISCalcField.isEnabled() and self.cbGISStatus.currentIndex() == 3:
                for x in range(len(self.layerList)):
                    if self.layerList[x][1] == self.cbGISLayer.currentText():
                        fields = self.layerList[x][3].dataProvider().fields()
                        proceed = True
                        break
            if self.cbGISStatus.currentIndex() == 2:
                for x in range(len(self.layerList)):
                    if self.layerList[x][1] == self.workingDict['project']['puLyr']:
                        fields = self.layerList[x][3].dataProvider().fields()
                        proceed = True
                        break
            if proceed:
                for field in fields:
                    if field.typeName() in ('Integer','Real','Double'):
                        self.cbGISCalcField.addItem(field.name())
                    
    #
    # GIS -set GIS output

    def gisSetOuptut(self):

        if self.cbGISSingleMulti.isEnabled():
            if self.GISdebug == True:
                QgsMessageLog.logMessage(self.myself())
            self.lblGISMeasureType.setEnabled(True)
            self.cbGISMeasureType.setEnabled(True)
            self.recStatus = 'Load'
            self.cbGISMeasureType.clear()
            if self.cbGISLayerType.currentText() == 'Raster':
                # a raster source
                if self.cbGISSingleMulti.currentText() == 'Single Field':
                    # merge all results into a single output field
                    self.cbGISMeasureType.addItems(['Measure','Measure x Value','Value'])
                else:
                    # one output field per unique pixel value
                    self.cbGISMeasureType.addItems(['Measure x Value','Value'])
            else:
                # a vector source
                if self.cbGISSingleMulti.currentText() == 'Single Field':
                    # merge all results into a single output field
                    self.cbGISMeasureType.addItems(['Measure','Measure x Field','Field'])
                else:
                    # one output field per unique field value
                    self.cbGISMeasureType.addItems(['Measure x Field','Field'])
            self.recStatus = 'Edit'
            self.gisSetMeasure()

    #
    # GIS - set GIS measure

    def gisSetMeasure(self):

        if self.recStatus <> 'Load':
            if self.GISdebug == True:
                QgsMessageLog.logMessage(self.myself())
            # the primary determinant here is whether this is a measure only result
            # or something using a pixel or field value
            self.cbGISIntAction.clear()
            if self.cbGISMeasureType.currentText() == 'Measure':
                # spatial measure alones only apply to single field outputs
                self.lblGISCalcField.setDisabled(True)
                self.cbGISCalcField.setDisabled(True)
                if self.cbGISLayerType.currentText() == 'Raster':
                    # a raster source
                    # sum of all pixel areas, count of pixels and presence in PU
                    self.cbGISIntAction.addItems(['Sum','Count','Presence'])
                else:
                    # a vector source
                    # sum -- min of measure, count of features and presence in PU
                    self.cbGISIntAction.addItems(['Sum','Mean','Max','Min','Count','Presence'])
            else:
                # field or pixel value inclusion allows for single or multiple field outputs
                if self.cbGISSingleMulti.currentText() == 'Single Field':
                    # merge all results into a single output field
                    if self.cbGISMeasureType.currentText() in ['Measure x Field','Measure x Value']:
                        # sum -- min of pixel area or measure times pixel or field value
                        self.cbGISIntAction.addItems(['Sum','Mean','Max','Min'])   
                    else:
                        # sum -- min of pixel / field value and count of distinct values
                        self.cbGISIntAction.addItems(['Sum','Mean','Max','Min','Count'])   
                else:
                    # one output field per unique pixel or field value
                    if self.cbGISMeasureType.currentText() == 'Measure x Field':
                        # sum -- min of measure for each distinct field value
                        self.cbGISIntAction.addItems(['Sum','Mean','Max','Min'])   
                    elif self.cbGISMeasureType.currentText() == 'Measure x Value':
                        # sum -- min of measure for each distinct pixel value or count of pixels
                        self.cbGISIntAction.addItems(['Sum','Mean','Max','Min','Count'])   
                    else:
                        # pixel value alone
                        if self.cbGISLayerType.currentText() == 'Raster':
                            # with rasters the number of spatially distinct features is unknown
                            self.cbGISIntAction.addItems(['Presence'])
                        else:
                            # number of spatially distinct features in PU or presence in PU
                            self.cbGISIntAction.addItems(['Count','Presence'])
                # set visibility based on type
                if self.cbGISLayerType.currentText() == 'Raster':
                    self.lblGISCalcField.setDisabled(True)
                    self.cbGISCalcField.setDisabled(True)
                else:
                    self.lblGISCalcField.setEnabled(True)
                    self.cbGISCalcField.setEnabled(True)
                    self.gisUpdateCalcFieldList()
            self.gisSetCalcMethod()

    #
    # GIS - set GIS calc method

    def gisSetCalcMethod(self):

        if self.cbGISCalcMethod.isEnabled():
            if self.GISdebug == True:
                QgsMessageLog.logMessage(self.myself())
            if self.cbGISCalcMethod.currentIndex() == 0:
                self.spbxGISPixelSize.setDisabled(True)
                self.lblGISPixelSize.setDisabled(True)
                self.lblGISIntAction.setEnabled(True)
                self.cbGISIntAction.setEnabled(True)
                self.cbGISMeasureType.setCurrentIndex(0)
                self.lblGISMeasureType.setEnabled(True)
                self.cbGISMeasureType.setEnabled(True)
            else:
                self.spbxGISPixelSize.setEnabled(True)
                self.lblGISPixelSize.setEnabled(True)
                self.lblGISIntAction.setDisabled(True)
                self.cbGISIntAction.setDisabled(True)
                self.cbGISMeasureType.setCurrentIndex(0)
                self.lblGISMeasureType.setDisabled(True)
                self.cbGISMeasureType.setDisabled(True)
        
    #
    # GIS - disable GIS editing

    def gisDisableEditing(self):

        if self.GISdebug == True:
            QgsMessageLog.logMessage(self.myself())
        # working project selection
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)
        # controls
        self.tblGIS.setEnabled(True)
        self.tblGIS.clearSelection()
        self.frGISControls1.setDisabled(True)
        self.frGISControls2.setDisabled(True)
        self.frGISControls3.setDisabled(True)
        self.frGISControls4.setDisabled(True)
        self.spbxGISId.setValue(0)
        self.leGISName.setText('')
        self.pteGISDescription.setPlainText('')
        self.leGISDataProvider.setText('')
        self.cbGISStatus.setCurrentIndex(0)
        self.cbGISLayerType.setCurrentIndex(0)
        self.cbGISLayer.setCurrentIndex(0)
        self.cbGISSingleMulti.setCurrentIndex(0)
        self.cbGISMeasureType.setCurrentIndex(0)
        self.cbGISCalcField.setCurrentIndex(0)
        self.cbGISIntAction.setCurrentIndex(0)
        self.cbGISCalcMethod.setCurrentIndex(0)
        self.spbxGISPixelSize.setValue(0)
        # buttons
        if self.workingLoaded:
            self.pbNewGISSource.setEnabled(True)
        else:
            self.pbNewGISSource.setDisabled(True)
        self.pbSaveGISSource.setDisabled(True)
        self.pbCancelGISSource.setDisabled(True)
        self.pbDeleteGISSource.setDisabled(True)
        # main form
        self.pbClose.setEnabled(True)
        self.twSettingsGIS.tabBar().setEnabled(True)

        
    #
    # Calculation Tab
    #

    #
    # generate actions report

    def calculationsCreateReport(self):

        if self.GISdebug == True:
            QgsMessageLog.logMessage(self.myself())
        # generate calculations list and report
        self.calcList,summary = self.calcCheck.gisCalculationsReport(self.workingDict, \
            self.puLyr,self.layerList,self.workingDir,self.crs)
        self.cbActions.clear()
        self.cbActions.addItem('--None--')
        self.cbActions.addItem('Create GIS Report')
        if len(self.calcList) > 0:
            self.cbActions.addItem('Perform GIS Calculations')
        self.pteActionsReport.setPlainText(summary)
        self.cbActions.setEnabled(True)

    #
    #

    def calculationsSelectAction(self):

        if self.cbActions.currentIndex() > 0:
            self.pbCalculate.setEnabled(True)
        else:
            self.pbCalculate.setDisabled(True)
        

    #
    # reset interface and clear actions

    def calculationsClear(self):

        self.pteActionsReport.setPlainText('')
        self.pbCalculate.setDisabled(True)
        self.cbActions.setDisabled(True)

    #
    # run calculations

    def calculationsPerform(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if self.cbActions.currentIndex() == 1:
            self.calculationsGISReport()
        elif self.cbActions.currentIndex() == 2:
            self.errorText = ''
            # working project selection
            self.lblWorkingProject.setDisabled(True)
            self.cbWorkingProject.setDisabled(True)
            # temporarily disable run and close
            self.pbReport.setDisabled(True)
            self.pbCalculate.setDisabled(True)
            self.pbCancel.setEnabled(True)
            self.twSettingsGIS.tabBar().setDisabled(True)
            self.pbClose.setDisabled(True)
            # instantiate calcContent worker
            worker = calcContent(self.calcList)
            # connect cancel to worker kill
            self.pbCancel.clicked.connect(worker.kill)
            # start the worker in a new thread
            thread = QtCore.QThread(self)
            worker.moveToThread(thread)
            # connect things together
            worker.workerFinished.connect(self.calculationsFinished)
            worker.workerError.connect(self.calculationsError)
            worker.workerStatus.connect(self.calculationsReportStatus)
            worker.progressAll.connect(self.pbAllProgress.setValue)
            worker.progressCalc.connect(self.pbCurrentProgress.setValue)
            worker.progressStep.connect(self.pbStepProgress.setValue)
            thread.started.connect(worker.run)
            # run
            thread.start()
            # manage thread and worker
            self.thread = thread
            self.worker = worker
        
        return()

    #
    # process error

    def calculationsError(self,e, exception_string, messageText):
        
        QgsMessageLog.logMessage('Worker thread raised an exception\n' + str(exception_string), level=QgsMessageLog.CRITICAL)
        self.errorText = str(messageText)

    #
    # process finished

    def calculationsFinished(self,ret):

        # clean up the worker and thread
        self.worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        # report status
        if ret == True:
            # report the result
            if self.processStatus == 'Cancelled':
                QgsMessageLog.logMessage(self.processStatus)
            elif self.processStatus <> 'Completed':
                # notify the user that something went wrong
                QgsMessageLog.logMessage('Something went wrong!')
        # reset the user interface
        self.pbAllProgress.setValue(0)
        self.pbCurrentProgress.setValue(0)
        self.pbStepProgress.setValue(0)
        # working project selection
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)
        # reset interface
        self.lblAllProgress.setText('Overall Progress:')
        self.lblCurrentProgress.setText('Current Process:')
        self.pbReport.setEnabled(True)
        self.pbCalculate.setDisabled(True)
        self.pbCancel.setDisabled(True)
        self.pbClose.setEnabled(True)
        # re-run report
        self.twSettingsGIS.tabBar().setEnabled(True)
        if self.processStatus == 'Completed':
            # update feature and cost dates to prevent errors
            self.calculationsUpdateFeatureCostDates()
            # refresh system
            self.calculationsCreateReport()
        else:
            self.pteActionsReport.setPlainText(self.errorText)

    #
    # report status

    def calculationsReportStatus(self,ret):

        self.processStatus = ret
        self.lblCurrentProgress.setText('Current Process: %s' % ret)

    #
    # update dates of feature and cost definitions when features updated

    def calculationsUpdateFeatureCostDates(self):

        for calc in self.calcList:
            if calc['reason'] <> 'Uncalculated':
                key = '%04d' % int(calc['key'])
                if key in self.workingDict['features']['recs']:
                    self.workingDict['features']['recs'][key]['editdate'] = datetime.datetime.now().isoformat()
                if key in self.workingDict['costs']['recs']:
                    self.workingDict['costs']['recs'][key]['editdate'] = datetime.datetime.now().isoformat()
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()

    #
    # create GIS calculations report

    def calculationsGISReport(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # set output file
        oFName = os.path.join(self.workingDir,'giscalc.csv')
        f = open(oFName,'w')
        # header
        # part 1
        f.write('"QMZ Id","GIS Name","Description","Data Provider","Status"')
        # part 2
        f.write(',"Geometry Type","GIS Layer Name","Assign To"')
        # part 3
        f.write(',"On Intersection","Calculation Field","PU Intersection Action"')
        # part 4
        f.write(',"GIS Method","Pixel Size","Source File"')
        # part 5
        f.write(',"Source File Date","QMZ Configuration Date","QMZ Calculation Date"\n')
        # grab required parts of dictionaries to shorter lines of code
        gisRecs = self.workingDict['gis']['recs']
        # step through features to create list
        outLines = []
        for key, feat in gisRecs.iteritems():
            gRec = gisRecs[key]
            # part 1
            ln = '"%s","%s","%s","%s","%s"' % (key,gRec['name'],\
                gRec['description'],gRec['dataprovider'],gRec['status'])
            if gRec['status'] == 'GIS Source':
                # part 2
                ln += ',"%s","%s","%s"' % (gRec['layertype'],gRec['layername'],gRec['singlemulti'])
                if gRec['measuretype'] == 'Measure':
                    # part 3
                    ln += ',"%s","n/a","%s"' % (gRec['measuretype'],gRec['intaction'])
                else:
                    # part 3
                    ln += ',"%s","n/a","%s"' % (gRec['measuretype'],gRec['calcfield'],gRec['intaction'])
                # prep for part 4
                fileName = ''
                for layer in self.layerList:
                    if layer[1] == gRec['layername']:
                        fileName = layer[2]
                if gRec['calcmethod'] == 'Vector Overlay':
                    # part 4
                    ln += ',"%s","n/a","%s"' % (gRec['calcmethod'],fileName)
                else:
                    # part 4
                    ln += ',"%s","%s","%s"' % (gRec['calcmethod'],gRec['pixelsize'],fileName)
                # prep for part 5
                fileDate = datetime.datetime.fromtimestamp(os.path.getmtime(fileName)).isoformat()
                qmiFile = '%04d.qmi' % int(key)
                calcFName = os.path.join(self.workingDir,'qmzfiles',qmiFile)
                calcDate = datetime.datetime.fromtimestamp(os.path.getmtime(calcFName)).isoformat()
                # part 5
                ln += ',"%s","%s","%s"\n' % (fileDate,gRec['editdate'],calcDate)
            elif gRec['status'] == 'PU Field':
                # part 2
                ln += ',"n/a","%s","Single Field"' % (gRec['layername'])
                # part 3
                ln += ',"n/a","%s","n/a"' % (gRec['calcfield'])
                # prep for part 4
                fileName = self.puLyr.source()
                # part 4
                ln += ',"n/a","n/a","%s"' % fileName
                # prep for part 5
                fileDate = datetime.datetime.fromtimestamp(os.path.getmtime(fileName)).isoformat()
                qmiFile = '%04d.qmi' % int(key)
                calcFName = os.path.join(self.workingDir,'qmzfiles',qmiFile)
                calcDate = datetime.datetime.fromtimestamp(os.path.getmtime(calcFName)).isoformat()
                # part 5
                ln += ',"%s","%s","%s"\n' % (fileDate,gRec['editdate'],calcDate)
            else:
                # part 2,3,4,5
                ln += ',"n/a","n/a","n/a","n/a","n/a","n/a","n/a","n/a","n/a","n/a","n/a","n/a"'
            outLines.append([int(key),ln])
        outLines.sort()
        for line in outLines:
            f.write(line[1])
        f.close()
        popupText = 'Creation of GIS Calculation Report completed. The file giscalc.csv can be found in the folder: %s' % self.workingDir
        QtGui.QMessageBox.information(self, 'Information', popupText, QtGui.QMessageBox.Ok)
        
