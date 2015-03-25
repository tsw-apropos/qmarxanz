"""
# -*- coding: utf-8 -*-
#
# ========================================================
# 
# Purpose: Use QMZ GIS outputs to define Marxan / Marxan with Zones problem
# Author: Trevor Wiens
# Copyright: Apropos Information Systems Inc.
# Date: 2014-12-31
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
from ui_problem_definition import Ui_dlgProblemDefinition
import math,os,json,shutil,datetime,inspect,glob,csv

class qmzDefine(QtGui.QDialog, Ui_dlgProblemDefinition):

    #
    # initialization, connecting GUI controls to methods

    def __init__(self, iface):

        QtGui.QDialog.__init__(self)
        self.setupUi(self)
        self.iface = iface
        self.qmzDir = None
        self.workingDir = None
        self.workingFile = None
        self.workingType = 'Marxan'
        self.workingDict = {}
        self.featureSortOrder = 'Number'

        self.debug = False
        if self.debug == True:
            self.myself = lambda: inspect.stack()[1][3]
            QgsMessageLog.logMessage(self.myself())

        # enable sorting of tables
        self.tblZones.setSortingEnabled(True)
        self.tblZoneTargs.setSortingEnabled(True)
        self.tblZoneConts.setSortingEnabled(True)
        self.tblZoneBounCosts.setSortingEnabled(True)
        self.tblZoneCosts.setSortingEnabled(True)

        # Dialog control
        QtCore.QObject.connect(self.pbClose, QtCore.SIGNAL("clicked()"), self.closeDialog)
        QtCore.QObject.connect(self.cbWorkingProject, QtCore.SIGNAL("currentIndexChanged(int)"), self.projectLoadWorking)
        # Tab Controls
        # Features Tab
        QtCore.QObject.connect(self.pbSaveFeature, QtCore.SIGNAL("clicked()"), self.featureSave)
        QtCore.QObject.connect(self.pbCancelFeature, QtCore.SIGNAL("clicked()"), self.featureCancel)
        QtCore.QObject.connect(self.tbAddFeature, QtCore.SIGNAL("clicked()"), self.featureAdd)
        QtCore.QObject.connect(self.tbRemoveFeature, QtCore.SIGNAL("clicked()"), self.featureRemove)
        QtCore.QObject.connect(self.cbTargetType, QtCore.SIGNAL("currentIndexChanged(int)"), self.featureSetTargetRanges)
        QtCore.QObject.connect(self.pbSelectAllAvailableFeatures, QtCore.SIGNAL("clicked()"), self.featureSelectAllAvailable)
        QtCore.QObject.connect(self.pbClearAvailableFeatures, QtCore.SIGNAL("clicked()"), self.featureClearAvailable)
        QtCore.QObject.connect(self.pbSelectAllSelectedFeatures, QtCore.SIGNAL("clicked()"), self.featureSelectAllSelected)
        QtCore.QObject.connect(self.pbClearSelectedFeatures, QtCore.SIGNAL("clicked()"), self.featureClearSelected)
        QtCore.QObject.connect(self.lwAvailableFeatureSources, QtCore.SIGNAL("itemSelectionChanged()"), self.featureSelectAvailable)
        QtCore.QObject.connect(self.lwSelectedFeatureSources, QtCore.SIGNAL("itemSelectionChanged()"), self.featureSelectSelected)
        QtCore.QObject.connect(self.tbSortByNumber, QtCore.SIGNAL("clicked()"), self.featureSortByNumber)
        QtCore.QObject.connect(self.tbSortByName, QtCore.SIGNAL("clicked()"), self.featureSortByName)
        # Costs Tab
        QtCore.QObject.connect(self.pbSaveCost, QtCore.SIGNAL("clicked()"), self.costSave)
        QtCore.QObject.connect(self.pbCancelCost, QtCore.SIGNAL("clicked()"), self.costCancel)
        QtCore.QObject.connect(self.tbAddCost, QtCore.SIGNAL("clicked()"), self.costAdd)
        QtCore.QObject.connect(self.tbRemoveCost, QtCore.SIGNAL("clicked()"), self.costRemove)
        QtCore.QObject.connect(self.pbSelectAllAvailableCosts, QtCore.SIGNAL("clicked()"), self.costSelectAllAvailable)
        QtCore.QObject.connect(self.pbClearAvailableCosts, QtCore.SIGNAL("clicked()"), self.costClearAvailable)
        QtCore.QObject.connect(self.pbSelectAllSelectedCosts, QtCore.SIGNAL("clicked()"), self.costSelectAllSelected)
        QtCore.QObject.connect(self.pbClearSelectedCosts, QtCore.SIGNAL("clicked()"), self.costClearSelected)
        QtCore.QObject.connect(self.lwAvailableCostSources, QtCore.SIGNAL("itemSelectionChanged()"), self.costSelectAvailable)
        QtCore.QObject.connect(self.lwSelectedCostSources, QtCore.SIGNAL("itemSelectionChanged()"), self.costSelectSelected)
        # Zones Tab
        QtCore.QObject.connect(self.tblZones, QtCore.SIGNAL("itemSelectionChanged()"), self.zoneSelect)
        QtCore.QObject.connect(self.pbNewZone, QtCore.SIGNAL("clicked()"), self.zoneNew)
        QtCore.QObject.connect(self.pbSaveZone, QtCore.SIGNAL("clicked()"), self.zoneSave)
        QtCore.QObject.connect(self.pbCancelZone, QtCore.SIGNAL("clicked()"), self.zoneCancel)
        QtCore.QObject.connect(self.pbDeleteZone, QtCore.SIGNAL("clicked()"), self.zoneDelete)
        # Zone Costs
        QtCore.QObject.connect(self.tblZoneCosts, QtCore.SIGNAL("itemSelectionChanged()"), self.zoneCostSelect)
        QtCore.QObject.connect(self.pbNewZoneCost, QtCore.SIGNAL("clicked()"), self.zoneCostNew)
        QtCore.QObject.connect(self.pbSaveZoneCost, QtCore.SIGNAL("clicked()"), self.zoneCostSave)
        QtCore.QObject.connect(self.pbCancelZoneCost, QtCore.SIGNAL("clicked()"), self.zoneCostCancel)
        QtCore.QObject.connect(self.pbDeleteZoneCost, QtCore.SIGNAL("clicked()"), self.zoneCostDelete)
        # Zone Targets Tab
        QtCore.QObject.connect(self.tblZoneTargs, QtCore.SIGNAL("itemSelectionChanged()"), self.zoneTargSelect)
        QtCore.QObject.connect(self.pbNewZoneTarg, QtCore.SIGNAL("clicked()"), self.zoneTargNew)
        QtCore.QObject.connect(self.pbSaveZoneTarg, QtCore.SIGNAL("clicked()"), self.zoneTargSave)
        QtCore.QObject.connect(self.pbCancelZoneTarg, QtCore.SIGNAL("clicked()"), self.zoneTargCancel)
        QtCore.QObject.connect(self.pbDeleteZoneTarg, QtCore.SIGNAL("clicked()"), self.zoneTargDelete)
        # Zone Contributions Tab
        QtCore.QObject.connect(self.tblZoneConts, QtCore.SIGNAL("itemSelectionChanged()"), self.zoneContSelect)
        QtCore.QObject.connect(self.pbNewZoneCont, QtCore.SIGNAL("clicked()"), self.zoneContNew)
        QtCore.QObject.connect(self.pbSaveZoneCont, QtCore.SIGNAL("clicked()"), self.zoneContSave)
        QtCore.QObject.connect(self.pbCancelZoneCont, QtCore.SIGNAL("clicked()"), self.zoneContCancel)
        QtCore.QObject.connect(self.pbDeleteZoneCont, QtCore.SIGNAL("clicked()"), self.zoneContDelete)
        # Zone Boundary Costs
        QtCore.QObject.connect(self.tblZoneBounCosts, QtCore.SIGNAL("itemSelectionChanged()"), self.zoneBounCostSelect)
        QtCore.QObject.connect(self.pbNewZoneBounCost, QtCore.SIGNAL("clicked()"), self.zoneBounCostNew)
        QtCore.QObject.connect(self.pbSaveZoneBounCost, QtCore.SIGNAL("clicked()"), self.zoneBounCostSave)
        QtCore.QObject.connect(self.pbCancelZoneBounCost, QtCore.SIGNAL("clicked()"), self.zoneBounCostCancel)
        QtCore.QObject.connect(self.pbDeleteZoneBounCost, QtCore.SIGNAL("clicked()"), self.zoneBounCostDelete)
        # Final Setup
        # Configure GUI
        self.setupGui()
        
    #
    # basic gui setup and loading
    
    def setupGui(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # this populates everything if a proper project is selected
        self.projectReadSettings()
        # set gui appearance
        # remove zones tabs if standard Marxan project
        if self.workingType == 'Marxan':
            x = 0
            self.cbTargetType.clear()
            self.cbTargetType.addItems(['Target Value','Proportion','Target Occurrence'])
            self.twProblemDefinition.setCurrentIndex(x)
            while True:
                label = self.twProblemDefinition.tabText(x)
                if not label in ['Features (R)','Costs (R)']:
                    self.twProblemDefinition.removeTab(x)
                else:
                    x +=1
                if self.twProblemDefinition.count() == 2:
                    break
        else:
            self.cbTargetType.clear()
            self.cbTargetType.addItems(['Target Value','Proportion','Target Occurrence','Proportional Occurrence'])
        # disable editing
        self.zoneDisableEditing()
        self.featureDisableEditing()
        self.zoneTargDisableEditing()
        self.zoneContDisableEditing()
        self.costDisableEditing()
        self.zoneBounCostDisableEditing()
        self.zoneCostDisableEditing()

    #
    # close dialog

    def closeDialog(self):

        #self.iface.newProject()
        self.close()

        
    #
    # Project Settings
    #

    #
    # reading QGIS stored settings for QMZ
    
    def projectReadSettings(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        s = QtCore.QSettings()
        # projects directory
        rv = s.value('QMarxanZ/projectsDir')
        if rv == None:
            self.qmzDir = '.'
        else:
            self.qmzDir = rv
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
        if newDir == '--None--':
            # define globals
            self.workingDir = None
            self.workingName = ''
            self.workingDict = {}
            self.workingFile = ''
            nTitle = 'No project: QMZ Problem Definition'
            self.setWindowTitle(nTitle)
            # disable interface
            self.twProblemDefinition.setDisabled(True)
            # clear values
            self.lwAvailableFeatureSources.clear()
            self.lwSelectedFeatureSources.clear()
            self.lwAvailableCostSources.clear()
            self.lwSelectedCostSources.clear()
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
                    nTitle = '%s: Marxan with Zones Problem Definition' % self.workingName
                else:
                    self.workingType = 'Marxan'
                    nTitle = '%s: Marxan Problem Definition' % self.workingName
                self.setWindowTitle(nTitle)
                # enable interface
                self.twProblemDefinition.setEnabled(True)
                # load values
                self.gisUpdateSourceDict()

    #
    # load gis results from .qmi files

    def gisUpdateSourceDict(self):

        # scan qmi files and create a sources list
        srcList = glob.glob(os.path.join(self.workingDir,'qmzfiles','*.qmi'))
        self.gisSourceDict = {}
        nameList = []
        numberList = []
        for src in srcList:
            with open(src,'r') as csvfile:
                qmiReader = csv.reader(csvfile,delimiter=',',quotechar="'")
                header = qmiReader.next()
                for row in qmiReader:
                    path,fname = os.path.split(src)
                    prefix,ext = os.path.splitext(fname)
                    if int(row[0]) == 0:
                        key = prefix
                    else:
                        key = '%s-%03d' % (prefix,int(row[0]))
                    self.gisSourceDict[key] = {'srcfile':key+'.qmd',\
                    'value':row[0],'name':row[1],'gissrc':row[2],\
                    'calcmethod':row[3],'description':row[4]}
                    nameList.append([row[1],key])
                    numberList.append(key)
        # now add source list to interface
        self.lwAvailableFeatureSources.clear()
        self.lwAvailableCostSources.clear()
        self.lwSelectedFeatureSources.clear()
        self.lwSelectedCostSources.clear()
        fDict = self.workingDict['features']['recs']
        cDict = self.workingDict['costs']['recs']
        # sort lists
        if self.featureSortOrder == 'Number':
            numberList.sort()
            for key in numberList:
                if key in fDict:
                    self.lwSelectedFeatureSources.addItem('%s :: %s' % (key,self.gisSourceDict[key]['name']))
                else:
                    self.lwAvailableFeatureSources.addItem('%s :: %s' % (key,self.gisSourceDict[key]['name']))
                if key in cDict:
                    self.lwSelectedCostSources.addItem('%s :: %s' % (key,self.gisSourceDict[key]['name']))
                else:
                    self.lwAvailableCostSources.addItem('%s :: %s' % (key,self.gisSourceDict[key]['name']))
        else:
            nameList.sort()
            for row in nameList:
                key = row[1]
                if key in fDict:
                    self.lwSelectedFeatureSources.addItem('%s :: %s' % (key,self.gisSourceDict[key]['name']))
                else:
                    self.lwAvailableFeatureSources.addItem('%s :: %s' % (key,self.gisSourceDict[key]['name']))
                if key in cDict:
                    self.lwSelectedCostSources.addItem('%s :: %s' % (key,self.gisSourceDict[key]['name']))
                else:
                    self.lwAvailableCostSources.addItem('%s :: %s' % (key,self.gisSourceDict[key]['name']))

    #
    # Features Tab
    # NOTE: 2014-12-31 - TSW - Code Incomplete
    # 1. Need to add checks to avoid deleting features that may used elsewhere in zones problems
    #

    #
    # load a feature for editing
    
    def featureLoad(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # load values from dictionary record that matches row selected in table
        zDict = self.workingDict['features']['recs']
        itemList = self.lwSelectedFeatureSources.selectedItems()
        key = itemList[0].text().split(' :: ')[0].strip()
        # load values into interface
        # name
        self.leFeatureName.setText(zDict[key]['name'])
        # target type
        idx = self.cbTargetType.findText(zDict[key]['targettype'])
        if idx == -1:
            idx = 0
        self.cbTargetType.setCurrentIndex(idx)
        # target
        tval = zDict[key]['target']
        if tval == '':
            tval = 0
        self.spbxTarget.setValue(float(tval))
        # penalty
        tval = zDict[key]['penalty']
        if tval == '':
            tval = 0
        self.spbxPenalty.setValue(float(tval))
        # description
        self.pteFeatureDescription.setPlainText(zDict[key]['description'])

    #
    # add one or more features
    
    def featureAdd(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['features']['recs']            
        # get selected items from available list
        itemList = self.lwAvailableFeatureSources.selectedItems()
        # add to selected list
        for item in itemList:
            # add record to projectDict
            key = item.text().split(' :: ')[0].strip()
            if not key in  self.workingDict['features']['recs']:
                 self.workingDict['features']['recs'][key] = {}
            self.workingDict['features']['recs'][key]['targettype'] = 'Proportion'
            self.workingDict['features']['recs'][key]['target'] = 0.5
            self.workingDict['features']['recs'][key]['penalty'] = 1.0
            self.workingDict['features']['recs'][key]['name'] = self.gisSourceDict[key]['name']
            self.workingDict['features']['recs'][key]['description'] = self.gisSourceDict[key]['description']
            self.workingDict['features']['recs'][key]['editdate'] = datetime.datetime.now().isoformat()
            # update user interface
            self.lwSelectedFeatureSources.addItem(item.text())
            self.lwAvailableFeatureSources.setCurrentItem(item)
            asdf = self.lwAvailableFeatureSources.takeItem(self.lwAvailableFeatureSources.currentRow())
        # commit to disk
        # NOTE: - the features:editdate is updated so we know when the puvsp.dat
        # and puvsp_sporder.dat files needs to be updated not just the spec.dat file
        self.workingDict['features']['editdate'] = datetime.datetime.now().isoformat()
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        # sort user interface
        self.gisUpdateSourceDict()

    #
    # remove one or more features
    
    def featureRemove(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['features']['recs']            
        # get selected items from available list
        itemList = self.lwSelectedFeatureSources.selectedItems()
        # add to selected list
        for item in itemList:
            # update user interface
            self.lwAvailableFeatureSources.addItem(item.text())
            self.lwSelectedFeatureSources.setCurrentItem(item)
            asdf = self.lwSelectedFeatureSources.takeItem(self.lwSelectedFeatureSources.currentRow())
            # add record to projectDict
            key = item.text().split(' :: ')[0].strip()
            del self.workingDict['features']['recs'][key]
        # commit to disk
        # NOTE: - the features:editdate is updated so we know when the puvsp.dat
        # and puvsp_sporder.dat files needs to be updated not just the spec.dat file
        self.workingDict['features']['editdate'] = datetime.datetime.now().isoformat()
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        self.gisUpdateSourceDict()
            
    #
    # save feature after editing
    
    def featureSave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        itemList = self.lwSelectedFeatureSources.selectedItems()
        if len(itemList) == 1:
            key = itemList[0].text().split(' :: ')[0].strip()
            self.workingDict['features']['recs'][key]['name'] = self.leFeatureName.text()
            self.workingDict['features']['recs'][key]['targettype'] = self.cbTargetType.currentText()
            self.workingDict['features']['recs'][key]['target'] = round(self.spbxTarget.value(),3)
            self.workingDict['features']['recs'][key]['penalty'] = round(self.spbxPenalty.value(),3)
            self.workingDict['features']['recs'][key]['editdate'] = datetime.datetime.now().isoformat()
        elif len(itemList) > 1:
            for item in itemList:
                key = item.text().split(' :: ')[0].strip()
                self.workingDict['features']['recs'][key]['targettype'] = self.cbTargetType.currentText()
                self.workingDict['features']['recs'][key]['target'] = round(self.spbxTarget.value(),3)
                self.workingDict['features']['recs'][key]['penalty'] = round(self.spbxPenalty.value(),3)
                self.workingDict['features']['recs'][key]['editdate'] = datetime.datetime.now().isoformat()
        # Note: features:editdate is not updated so we know that only spec.dat
        # needs to be updated, not puvsp.data and puvsp_sporder.data
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        self.featureClearSelected()

    #
    # cancel editing
    
    def featureCancel(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.featureClearSelected()

    #
    # enable editing of a feature
    
    def featureEnableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.frFeatureWidgets1.setEnabled(True)
        self.pbSaveFeature.setEnabled(True)
        self.pbCancelFeature.setEnabled(True)
        if len(self.lwSelectedFeatureSources.selectedItems()) == 1:
            self.frFeatureWidgets2.setEnabled(True)
            self.featureLoad()
        else:
            self.frFeatureWidgets2.setDisabled(True)
            self.leFeatureName.setText('')
            self.pteFeatureDescription.setPlainText('')
        # main form
        self.pbClose.setDisabled(True)
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)
        self.twProblemDefinition.tabBar().setDisabled(True)

    #
    # disable editing of a feature
    
    def featureDisableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.frFeatureWidgets1.setDisabled(True)
        self.frFeatureWidgets2.setDisabled(True)
        self.pbSaveFeature.setDisabled(True)
        self.pbCancelFeature.setDisabled(True)
        self.leFeatureName.setText('')
        self.pteFeatureDescription.setPlainText('')
        # main form
        self.pbClose.setEnabled(True)
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)
        self.twProblemDefinition.tabBar().setEnabled(True)

    #
    # set target ranges based on target type
    
    def featureSetTargetRanges(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if self.cbTargetType.currentText() in ['Target Value','Target Occurrence']:
            self.spbxTarget.setMinimum(0.0)
            self.spbxTarget.setMaximum(999999999.0)
            self.spbxTarget.setSingleStep(100)
        elif self.cbTargetType.currentText() in ['Proportion','Proportional Occurrence']:
            self.spbxTarget.setMinimum(0.0)
            self.spbxTarget.setMaximum(1.0)
            self.spbxTarget.setSingleStep(0.05)
            if self.spbxTarget.value() > self.spbxTarget.maximum():
                self.spbxTarget.setvalue(self.spbxTarget.maximum())
            
    #
    # select an available feature source

    def featureSelectAvailable(self):

        if len(self.lwAvailableFeatureSources.selectedItems()) > 0:
            self.tbAddFeature.setEnabled(True)
            self.lwSelectedFeatureSources.setDisabled(True)
            self.pbSelectAllSelectedFeatures.setDisabled(True)
            self.pbClearSelectedFeatures.setDisabled(True)
        else:
            self.tbAddFeature.setDisabled(True)
            self.lwSelectedFeatureSources.setEnabled(True)
            self.pbSelectAllSelectedFeatures.setEnabled(True)
            self.pbClearSelectedFeatures.setEnabled(True)

    #
    # select a selected feature source

    def featureSelectSelected(self):

        if len(self.lwSelectedFeatureSources.selectedItems()) > 0:
            self.tbRemoveFeature.setEnabled(True)
            self.lwAvailableFeatureSources.setDisabled(True)
            self.pbSelectAllAvailableFeatures.setDisabled(True)
            self.pbClearAvailableFeatures.setDisabled(True)
            self.featureEnableEditing()
        else:
            self.tbRemoveFeature.setDisabled(True)
            self.lwAvailableFeatureSources.setEnabled(True)
            self.pbSelectAllAvailableFeatures.setEnabled(True)
            self.pbClearAvailableFeatures.setEnabled(True)
            self.featureDisableEditing()

    #
    # select all available feature sources

    def featureSelectAllAvailable(self):

        cnt = self.lwAvailableFeatureSources.count()
        for x in range(cnt):
            item = self.lwAvailableFeatureSources.item(x)
            self.lwAvailableFeatureSources.setItemSelected(item,True)

    #
    # select all available feature sources

    def featureClearAvailable(self):

        cnt = self.lwAvailableFeatureSources.count()
        for x in range(cnt):
            item = self.lwAvailableFeatureSources.item(x)
            self.lwAvailableFeatureSources.setItemSelected(item,False)

    #
    # select all selected feature sources

    def featureSelectAllSelected(self):

        cnt = self.lwSelectedFeatureSources.count()
        for x in range(cnt):
            item = self.lwSelectedFeatureSources.item(x)
            self.lwSelectedFeatureSources.setItemSelected(item,True)

    #
    # clear selection of available features

    def featureClearSelected(self):

        cnt = self.lwSelectedFeatureSources.count()
        for x in range(cnt):
            item = self.lwSelectedFeatureSources.item(x)
            self.lwSelectedFeatureSources.setItemSelected(item,False)

    #
    # sort list of featuers by number

    def featureSortByNumber(self):

        self.featureSortOrder = 'Number'
        self.gisUpdateSourceDict()
        
    #
    # sort list of features by name

    def featureSortByName(self):
    
        self.featureSortOrder = 'Name'
        self.gisUpdateSourceDict()

    #
    # Costs Tab
    # NOTE: 2014-12-31 - TSW - Code Incomplete
    # 1. Need to add checks to avoid deleting costs that may used elsewhere in zones problems
    #

    #
    # load a cost for editing
    
    def costLoad(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # load values from dictionary record that matches row selected in table
        zDict = self.workingDict['costs']['recs']
        itemList = self.lwSelectedCostSources.selectedItems()
        key = itemList[0].text().split(' :: ')[0].strip()
        # load values into interface
        # name
        self.leCostName.setText(zDict[key]['name'])
        # description
        self.pteCostDescription.setPlainText(zDict[key]['description'])

    #
    # add one or more costs
    
    def costAdd(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['costs']['recs']            
        # get selected items from available list
        itemList = self.lwAvailableCostSources.selectedItems()
        # add to selected list
        for item in itemList:
            # add record to projectDict
            key = item.text().split(' :: ')[0].strip()
            if not key in  self.workingDict['costs']['recs']:
                 self.workingDict['costs']['recs'][key] = {}
            self.workingDict['costs']['recs'][key]['name'] = self.gisSourceDict[key]['name']
            self.workingDict['costs']['recs'][key]['description'] = self.gisSourceDict[key]['description']
            self.workingDict['costs']['recs'][key]['editdate'] = datetime.datetime.now().isoformat()
            # update user interface
            self.lwSelectedCostSources.addItem(item.text())
            self.lwAvailableCostSources.setCurrentItem(item)
            asdf = self.lwAvailableCostSources.takeItem(self.lwAvailableCostSources.currentRow())
        # commit to disk
        # NOTE: - the costs:editdate is updated so we know pu.dat needs to be updated
        self.workingDict['costs']['editdate'] = datetime.datetime.now().isoformat()
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        # sort user interface
        self.gisUpdateSourceDict()

    #
    # remove one or more costs
    
    def costRemove(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['costs']['recs']            
        # get selected items from available list
        itemList = self.lwSelectedCostSources.selectedItems()
        # add to selected list
        for item in itemList:
            # update user interface
            self.lwAvailableCostSources.addItem(item.text())
            self.lwSelectedCostSources.setCurrentItem(item)
            asdf = self.lwSelectedCostSources.takeItem(self.lwSelectedCostSources.currentRow())
            # add record to projectDict
            key = item.text().split(' :: ')[0].strip()
            del self.workingDict['costs']['recs'][key]
        # commit to disk
        # NOTE: - the costs:editdate is updated so we know pu.dat needs to be updated
        self.workingDict['costs']['editdate'] = datetime.datetime.now().isoformat()
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        self.gisUpdateSourceDict()
            
    #
    # save cost after editing
    
    def costSave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        itemList = self.lwSelectedCostSources.selectedItems()
        key = itemList[0].text().split(' :: ')[0].strip()
        self.workingDict['costs']['recs'][key]['name'] = self.leCostName.text()
        self.workingDict['costs']['recs'][key]['editdate'] = datetime.datetime.now().isoformat()
        # NOTE: update costs:editdate is not updated so we know that pu.dat does
        # not need to be updated
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        self.costClearSelected()

    #
    # cancel editing
    
    def costCancel(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.costClearSelected()

    #
    # enable editing of a cost
    
    def costEnableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.frCostWidgets.setEnabled(True)
        self.pbSaveCost.setEnabled(True)
        self.pbCancelCost.setEnabled(True)
        self.costLoad()
        # main form
        self.pbClose.setDisabled(True)
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)
        self.twProblemDefinition.tabBar().setDisabled(True)

    #
    # disable editing of a cost
    
    def costDisableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.frCostWidgets.setDisabled(True)
        self.pbSaveCost.setDisabled(True)
        self.pbCancelCost.setDisabled(True)
        self.leCostName.setText('')
        self.pteCostDescription.setPlainText('')
        # main form
        self.pbClose.setEnabled(True)
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)
        self.twProblemDefinition.tabBar().setEnabled(True)

    #
    # select an available cost source

    def costSelectAvailable(self):

        if len(self.lwAvailableCostSources.selectedItems()) > 0:
            self.tbAddCost.setEnabled(True)
            self.lwSelectedCostSources.setDisabled(True)
            self.pbSelectAllSelectedCosts.setDisabled(True)
            self.pbClearSelectedCosts.setDisabled(True)
        else:
            self.tbAddCost.setDisabled(True)
            self.lwSelectedCostSources.setEnabled(True)
            self.pbSelectAllSelectedCosts.setEnabled(True)
            self.pbClearSelectedCosts.setEnabled(True)

    #
    # select a selected cost source

    def costSelectSelected(self):

        if len(self.lwSelectedCostSources.selectedItems()) > 0:
            self.tbRemoveCost.setEnabled(True)
            self.lwAvailableCostSources.setDisabled(True)
            self.pbSelectAllAvailableCosts.setDisabled(True)
            self.pbClearAvailableCosts.setDisabled(True)
            if len(self.lwSelectedCostSources.selectedItems()) == 1:
                self.costEnableEditing()
            else:
                self.costDisableEditing()
        else:
            self.tbRemoveCost.setDisabled(True)
            self.lwAvailableCostSources.setEnabled(True)
            self.pbSelectAllAvailableCosts.setEnabled(True)
            self.pbClearAvailableCosts.setEnabled(True)
            self.costDisableEditing()

    #
    # select all available cost sources

    def costSelectAllAvailable(self):

        cnt = self.lwAvailableCostSources.count()
        for x in range(cnt):
            item = self.lwAvailableCostSources.item(x)
            self.lwAvailableCostSources.setItemSelected(item,True)

    #
    # select all available cost sources

    def costClearAvailable(self):

        cnt = self.lwAvailableCostSources.count()
        for x in range(cnt):
            item = self.lwAvailableCostSources.item(x)
            self.lwAvailableCostSources.setItemSelected(item,False)

    #
    # select all selected cost sources

    def costSelectAllSelected(self):

        cnt = self.lwSelectedCostSources.count()
        for x in range(cnt):
            item = self.lwSelectedCostSources.item(x)
            self.lwSelectedCostSources.setItemSelected(item,True)

    #
    # clear selection of available costs

    def costClearSelected(self):

        cnt = self.lwSelectedCostSources.count()
        for x in range(cnt):
            item = self.lwSelectedCostSources.item(x)
            self.lwSelectedCostSources.setItemSelected(item,False)
        
    #
    # Zones Tab
    # NOTE: 2014-12-31 - TSW - Code Incomplete
    # 1. Need to add checks to avoid deleting zones that may used elsewhere
    # 2. Need to add record level time stamps
    #

    #
    # load list of zones

    def zoneLoadList(self):
        
        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # load data
        zDict = self.workingDict['zoneinfo']['zones']['recs']
        rc = len(zDict)
        # clear zone controls
        self.tblZones.clear()
        self.tblZones.setColumnCount(2)
        self.tblZones.setRowCount(rc)
        self.tblZones.setHorizontalHeaderLabels(['Zone Id','Zone Name'])
        self.tblZones.setColumnWidth(0,100)
        self.tblZones.setColumnWidth(1,225)
        # setup other zone based controls
        self.cbZoneBounCostZone1.clear()
        self.cbZoneBounCostZone1.addItem('0-Not Set')
        self.cbZoneBounCostZone2.clear()
        self.cbZoneBounCostZone2.addItem('0-Not Set')
        self.cbZoneCostZone.clear()
        self.cbZoneCostZone.addItem('0-Not Set')
        self.cbZoneTargZone.clear()
        self.cbZoneTargZone.addItem('0-Not Set')
        self.cbZoneContZone.clear()
        self.cbZontContZone.addItem('0-Not Set')
        x = 0
        for key, value in zDict.iteritems():
            # zone table
            self.zoneAddToTable(x,key,value)
            # other zone based controls
            self.cbZoneBounCostZone1.addItem(key+'-'+value)
            self.cbZoneBounCostZone2.addItem(key+'-'+value)
            self.cbZoneCostZone.addItem(key+'-'+value)
            self.cbZoneTargZone.addItem(key+'-'+value)
            self.cbZoneContZone.addItem(key+'-'+value)
            x += 1

    #
    # add zone record to table

    def zoneAddToTable(self,x,key,value):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # id
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(key))
        item.setToolTip('Zone Id')
        self.tblZones.setItem(x,0,item)
        # user name
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value))
        item.setToolTip('Zone Name')
        self.tblZones.setItem(x,1,item)

    #
    # edit selected zone

    def zoneLoad(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['zoneinfo']['zones']['recs']
        cr = self.tblZones.currentRow()
        zId = int(self.tblZones.item(cr,0).text())
        self.spbxZoneId.setValue(zId)
        self.leZoneName.setText(zDict[str(zId)])

    #
    # select zone for editing
    
    def zoneSelect(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if len(self.tblZones.selectedItems()) > 0:
            self.zoneLoad()
            self.zoneEnableEditing()

    #
    # create new zone record
    
    def zoneNew(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['zoneinfo']['zones']['recs']
        keys = map(int,zDict.keys())
        if len(keys) > 0:
            newId = max(keys)+1
        else:
            newId = 1
        self.spbxZoneId.setValue(newId)
        self.leZoneName.setText('New Zone')
        self.zoneEnableEditing()

    #
    # save zone record
    
    def zoneSave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zId = str(self.spbxZoneId.value())
        zName = self.leZoneName.text().replace('-',' ')
        self.workingDict['zoneinfo']['zones']['recs'][zId] = zName
        self.workingDict['zoneinfo']['zones']['editdate'] = datetime.datetime.now().isoformat()
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.projDict))
        f.close()
        self.zoneDisableEditing()
        self.zoneLoadList()

    #
    # cancel edits to a zone
        
    def zoneCancel(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.disableZoneEditing()

    #
    # delete a zone
    
    def zoneDelete(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zId = str(self.spbxZoneId.value())
        # TO DO
        # do some checks against dependent entries to ensure this is ok
        isOk = True
        if isOk:
            res = QtGui.QMessageBox.warning(self, 'Warning',
               "Are you sure you want to delete this zone?", QtGui.QMessageBox.Yes|QtGui.QMessageBox.No)
            if res == QtGui.QMessageBox.No:
                isOk = False
        else:
            QtGui.QMessageBox.warning(self, 'Warning',
               "You can not delete this zone because other values require it. Delete those records first.", QtGui.QMessageBox.Ok)
        if isOk:
            del self.workingDict['zoneinfo']['zones']['recs'][zId]
            self.workingDict['zoneinfo']['zones']['editdate'] = datetime.datetime.now().isoformat()
            f = open(self.workingFile,'w')
            f.write(json.dumps(self.projDict))
            f.close()
            self.zoneLoadList()
        self.zoneDisableEditing()

    #
    # enable editing of a zone record
    
    def zoneEnableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.tblZones.setDisabled(True)
        self.frZoneWidgets.setEnabled(True)
        # buttons
        self.pbNewZone.setDisabled(True)
        self.pbSaveZone.setEnabled(True)
        self.pbCancelZone.setEnabled(True)
        self.pbDeleteZone.setEnabled(True)
        # main form
        self.pbClose.setDisabled(True)
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)
        
    #
    # disable editing of a zone record
    
    def zoneDisableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.tblZones.setEnabled(True)
        self.tblZones.clearSelection()
        self.frZoneWidgets.setDisabled(True)
        self.spbxZoneId.setValue(0)
        self.leZoneName.setText('')
        # buttons
        self.pbNewZone.setEnabled(True)
        self.pbSaveZone.setDisabled(True)
        self.pbCancelZone.setDisabled(True)
        self.pbDeleteZone.setDisabled(True)
        # main form
        self.pbClose.setEnabled(True)
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)


    #
    # Zone Costs Tab
    #

    #
    # load zone cost records into table
    
    def zoneCostLoadList(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['zoneinfo']['zonecosts']['recs']
        rc = len(zDict)
        self.tblZoneCosts.clear()
        self.tblZoneCosts.setColumnCount(3)
        self.tblZoneCosts.setRowCount(rc)
        self.tblZoneCosts.setHorizontalHeaderLabels(['Zone Id','CostId','Multiplier'])
        self.tblZoneCosts.setColumnWidth(0,100)
        self.tblZoneCosts.setColumnWidth(1,100)
        self.tblZoneCosts.setColumnWidth(2,150)
        x = 0
        for key, value in zDict.iteritems():
            vList = key.split('-')
            vList.append(value)
            self.zoneCostAddToTable(x,vList)
            x += 1

    #
    # add zone cost record to table
    
    def zoneCostAddToTable(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # zone id 1
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[0]))
        item.setToolTip('Zone Id')
        self.tblZoneCosts.setItem(x,0,item)
        # zone id 2
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[1]))
        item.setToolTip('Cost Id')
        self.tblZoneCosts.setItem(x,1,item)
        # zone boundary cost
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[2]))
        item.setToolTip('Multiplier')
        self.tblZoneCosts.setItem(x,2,item)

    #
    # load zone cost record for editing
    
    def zoneCostLoad(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['zoneinfo']['zonecosts']['recs']
        cr = self.tblZoneCosts.currentRow()
        zId1 = self.tblZoneCosts.item(cr,0).text().split('-')[0]
        zId2 = self.tblZoneCosts.item(cr,1).text().split('-')[0]
        key = zId1 + '-' + zId2
        bc = zDict[key]
        zString = zId1+'-'+self.workingDict['zoneinfo']['zones']['recs'][zId1]
        idx = self.cbZoneCostZone.findText(zString)
        if idx <> -1:
            self.cbZoneCostZone.setCurrentIndex(idx)
        else:
            self.cbZoneCostZone.setCurrentIndex(0)
        zString = zId2+'-'+self.workingDict['zoneinfo']['costs']['recs'][zId2]['name']
        idx = self.cbZoneCostCost.findText(zString)
        if idx <> -1:
            self.cbZoneCostCost.setCurrentIndex(idx)
        else:
            self.cbZoneCostCost.setCurrentIndex(0)
        self.spbxZoneCostMultiplier.setValue(float(bc))

    #
    # select a zone cost record from table for editing
        
    def zoneCostSelect(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if len(self.tblZoneCosts.selectedItems()) > 0:
            self.zoneCostLoadList()
            self.zoneCostEnableEditing()

    #
    # create a new zone cost record
     
    def zoneCostNew(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.zoneCostEnableEditing()

    #
    # save zone cost record
    
    def zoneCostSave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zId1 = self.cbZoneCostZone.currentText().split('-')[0]
        zId2 = self.cbZoneCostCost.currentText().split('-')[0]
        key = zId1 + '-' + zId2
        self.workingDict['zoneinfo']['zonecosts']['recs'][key] = str(self.spbxZoneCostMultiplier.value())
        self.workingDict['zoneinfo']['zonecosts']['editdate'] = datetime.datetime.now().isoformat()
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.workingDict))
        f.close()
        self.zoneCostDisableEditing()
        self.zoneCostLoadList()

    #
    # cancel editing a zone cost record
    
    def zoneCostCancel(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.zoneCostDisableEditing()

    #
    # delete the currently selected zone cost record
        
    def zoneCostDelete(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        cr = self.tblZoneCosts.currentRow()
        zId1 = self.tblZoneCosts.item(cr,0).text().split('-')[0]
        zId2 = self.tblZoneCosts.item(cr,1).text().split('-')[0]
        key = zId1 + '-' + zId2
        res = QtGui.QMessageBox.warning(self, 'Warning',
           "Are you sure you want to delete this zone boundary cost?", QtGui.QMessageBox.Yes|QtGui.QMessageBox.No)
        if res == QtGui.QMessageBox.Yes:
            del self.workingDict['zoneinfo']['zonecosts']['recs'][key]
            self.workingDict['zoneinfo']['zonecosts']['editdate'] = datetime.datetime.now().isoformat()
            f = open(self.workingFile,'w')
            f.write(json.dumps(self.workingDict))
            f.close()
            self.zoneCostLoadList()
        self.zoneCostDisableEditing()

    #
    # enable editing of a zone cost record
    
    def zoneCostEnableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.tblZoneCosts.setDisabled(True)
        self.frZoneCostWidgets.setEnabled(True)
        # buttons
        self.pbNewZoneCost.setDisabled(True)
        self.pbSaveZoneCost.setEnabled(True)
        self.pbCancelZoneCost.setEnabled(True)
        self.pbDeleteZoneCost.setEnabled(True)
        # main form
        self.pbClose.setDisabled(True)
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)

    #
    # disable editing of a zone cost record
    
    def zoneCostDisableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.tblZoneCosts.setEnabled(True)
        self.tblZoneCosts.clearSelection()
        self.frZoneCostWidgets.setDisabled(True)
        self.cbZoneCostZone.setCurrentIndex(0)
        self.cbZoneCostCost.setCurrentIndex(0)
        self.spbxZoneCostMultiplier.setValue(0.0)
        # buttons
        self.pbNewZoneCost.setEnabled(True)
        self.pbSaveZoneCost.setDisabled(True)
        self.pbCancelZoneCost.setDisabled(True)
        self.pbDeleteZoneCost.setDisabled(True)
        # main form
        self.pbClose.setEnabled(True)
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)


    #
    # Zone Targets Tab
    # NOTE: 2014-12-31 - TSW - Code Incomplete
    # 1. Need to add record level time stamps
    # 2. The way that zone targets is stored seems overly complex and replacement
    #    dictionary fields would improve code readability
    #

    #
    # load list of zone targets to table
    
    def zoneTargLoadList(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.projDict['zoneinfo']['zonetargets']['recs']
        rc = len(zDict)
        self.tblZoneTargs.clear()
        self.tblZoneTargs.setColumnCount(3)
        self.tblZoneTargs.setRowCount(rc)
        self.tblZoneTargs.setHorizontalHeaderLabels(['Zone Id','Feature Id','Zone Target'])
        self.tblZoneTargs.setColumnWidth(0,100)
        self.tblZoneTargs.setColumnWidth(1,150)
        self.tblZoneTargs.setColumnWidth(2,150)
        x = 0
        for key, value in zDict.iteritems():
            vList = key.split('-')
            vList.append(value[0])
            self.zoneTargAddToTable(x,vList)
            x += 1

    #
    # add zone target record to table
    
    def zoneTargAddToTable(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # zone id
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[0]))
        item.setToolTip('Zone Id')
        self.tblZoneTargs.setItem(x,0,item)
        # feature id
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[1]))
        item.setToolTip('Feature Id')
        self.tblZoneTargs.setItem(x,1,item)
        # zone target
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[2]))
        item.setToolTip('Zone Target')
        self.tblZoneTargs.setItem(x,2,item)

    #
    # load zone target record for editing
    
    def zoneTargLoad(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['zoneinfo']['zonetargets']['recs']
        cr = self.tblZoneTargs.currentRow()
        zId1 = self.tblZoneTargs.item(cr,0).text().split('-')[0]
        zId2 = self.tblZoneTargs.item(cr,1).text().split('-')[0]
        key = zId1 + '-' + zId2
        bc = zDict[key]
        zString = zId1+'-'+self.workingDict['zoneinfo']['zones']['recs'][zId1]
        idx = self.cbZoneTargZone.findText(zString)
        if idx == -1:
            idx = 0
        self.cbZoneTargZone.setCurrentIndex(idx)
        zString = zId2+'-'+self.workingDict['features']['recs'][zId2]['name']
        idx = self.cbZoneTargFeature.findText(zString)
        if idx == -1:
            0
        self.cbZoneTargFeature.setCurrentIndex(idx)
        self.spbxZoneTargTarget.setValue(float(bc[0]))
        idx = self.cbZoneTargType.findText(str(bc[1]))
        if idx == -1:
            idx = 0
        self.cbZoneTargType.setCurrentIndex(idx)

    #
    # select zone in table for editing
    
    def zoneTargSelect(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if len(self.tblZoneTargs.selectedItems()) > 0:
            self.zoneTargLoad()
            self.zoneTargDisableEditing()

    #
    # create new zone target record for editing
    
    def zoneTargNew(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.zoneTargEnableEditing()

    #
    # save current zone target record after editing
    
    def zoneTargSave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zId1 = self.cbZoneTargZone.currentText().split('-')[0]
        zId2 = self.cbZoneTargFeature.currentText().split('-')[0]
        key = zId1 + '-' + zId2
        val = [self.spbxZoneTargTarget.value(),self.cbZoneTargType.currentText()]
        self.workingDict['zoneinfo']['zonetargets']['recs'][key] = val
        self.workingDict['zoneinfo']['zonetargets']['editdate'] = datetime.datetime.now().isoformat()
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.projDict))
        f.close()
        self.disableZTEditing()
        self.loadZTs()

    #
    # cancel edits to a zone target record
    
    def zoneTargCancel(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.zoneTargDisableEditing()

    #
    # delete a zone target record
    
    def zoneTargDelete(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.zoneTargDisableEditing()
        cr = self.tblZoneTargs.currentRow()
        zId1 = self.tblZoneTargs.item(cr,0).text().split('-')[0]
        zId2 = self.tblZoneTargs.item(cr,1).text().split('-')[0]
        key = zId1 + '-' + zId2
        res = QtGui.QMessageBox.warning(self, 'Warning',
           "Are you sure you want to delete this zone target?", QtGui.QMessageBox.Yes|QtGui.QMessageBox.No)
        if res == QtGui.QMessageBox.Yes:
            del self.workingDict['zoneinfo']['zonetargets']['recs'][key]
            self.workingDict['zoneinfo']['zonetargets']['editdate'] = datetime.datetime.now().isoformat()
            f = open(self.workingFile,'w')
            f.write(json.dumps(self.projDict))
            f.close()
            self.zoneTargLoadList()
        self.zoneTargDisableEditing()

    #
    # disable editing of a zone target record
    
    def zoneTargEnableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.tblZoneTargs.setDisabled(True)
        self.frZoneTargWidgets.setEnabled(True)
        # buttons
        self.pbNewZoneTarg.setDisabled(True)
        self.pbSaveZoneTarg.setEnabled(True)
        self.pbCancelZoneTarg.setEnabled(True)
        self.pbDeleteZoneTarg.setEnabled(True)
        # main form
        self.pbClose.setDisabled(True)
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)

    #
    # enable editing of a zone target record
        
    def zoneTargDisableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.tblZoneTargs.setEnabled(True)
        self.frZoneTargWidgets.setEnabled(True)
        self.tblZoneTargs.clearSelection()
        self.cbZoneTargZone.setCurrentIndex(0)
        self.cbZoneTargFeature.setCurrentIndex(0)
        self.spbxZoneTargTarget.setValue(0.0)
        self.cbZoneTargType.setCurrentIndex(0)
        # buttons
        self.pbNewZoneTarg.setEnabled(True)
        self.pbSaveZoneTarg.setDisabled(True)
        self.pbCancelZoneTarg.setDisabled(True)
        self.pbDeleteZoneTarg.setDisabled(True)
        # main form
        self.pbClose.setEnabled(True)
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)


    #
    # Zone Contributions Tab
    # 1. Need to add record level time stamps
    # 2. The way that zone targets is stored seems overly complex and replacement
    #    dictionary fields would improve code readability
    #

    #
    # load list of zone contributions
    
    def zoneContLoadList(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.projDict['zoneinfo']['zonecontributions']['recs']
        rc = len(zDict)
        self.tblZoneConts.clear()
        self.tblZoneConts.setColumnCount(3)
        self.tblZoneConts.setRowCount(rc)
        self.tblZoneConts.setHorizontalHeaderLabels(['Zone Id','Feature Id','Fraction'])
        self.tblZoneConts.setColumnWidth(0,100)
        self.tblZoneConts.setColumnWidth(1,150)
        self.tblZoneConts.setColumnWidth(2,150)
        x = 0
        for key, value in zDict.iteritems():
            vList = key.split('-')
            vList.append(value)
            self.zoneContAddToTable(x,vList)
            x += 1

    #
    # add zone contribution record to table
    
    def zoneContAddToTable(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # zone contributions id
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[0]))
        item.setToolTip('Zone Id')
        self.tblZoneConts.setItem(x,0,item)
        # feature id
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[1]))
        item.setToolTip('Feature Id')
        self.tblZoneConts.setItem(x,1,item)
        # zone contributions target
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[2]))
        item.setToolTip('Fraction')
        self.tblZoneConts.setItem(x,2,item)

    #
    # load a zone contribution record for editing
    
    def zoneContLoad(self):
        
        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['zoneinfo']['zonecontributions']['recs']
        cr = self.tblZoneConts.currentRow()
        zId1 = self.tblZoneConts.item(cr,0).text().split('-')[0]
        zId2 = self.tblZoneConts.item(cr,1).text().split('-')[0]
        key = zId1 + '-' + zId2
        bc = zDict[key]
        zString = zId1+'-'+self.workingDict['zoneinfo']['zones_costs']['recs'][zId1]
        idx = self.cbZoneContZone.findText(zString)
        if idx == -1:
            idx = 0
        self.cbZoneContZone.setCurrentIndex(idx)
        zString = zId2+'-'+self.workingDict['features']['recs'][zId2]['name']
        idx = self.cbZoneContFeature.findText(zString)
        if idx == -1:
            0
        self.cbZoneContFeature.setCurrentIndex(idx)
        self.spbxZoneContFraction.setValue(float(bc))

    #
    # select a zone contribution record from the table for editing
    
    def zoneContSelect(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if len(self.tblZoneConts.selectedItems()) > 0:
            self.zoneContLoad()
            self.zoneContEnableEditing()

    #
    # create new zone contribtuion record
    
    def zoneContNew(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.zoneContEnableEditing()

    #
    # save zone contribution record
    
    def zoneContSave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zId1 = self.cbZoneContZone.currentText().split('-')[0]
        zId2 = self.cbZoneContFeature.currentText().split('-')[0]
        key = zId1 + '-' + zId2
        self.projDict['zoneinfo']['zonecontributions']['recs'][key] = self.spbxZoneContFraction.value()
        self.projDict['zoneinfo']['zonecontributions']['editdate'] = datetime.datetime.now().isoformat()
        f = open(self.workingFile,'w')
        f.write(json.dumps(self.projDict))
        f.close()
        self.zoneContDisableEditing()
        self.zoneContLoadList()

    #
    # cancel zone contribution editing
    
    def zoneContCancel(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.zoneContDisableEditing()

    #
    # delete zone contribution record
    
    def zoneContDelete(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        cr = self.tblZoneConts.currentRow()
        zId1 = self.tblZoneConts.item(cr,0).text().split('-')[0]
        zId2 = self.tblZoneConts.item(cr,1).text().split('-')[0]
        key = zId1 + '-' + zId2
        res = QtGui.QMessageBox.warning(self, 'Warning',
           "Are you sure you want to delete this zone contributions target?", QtGui.QMessageBox.Yes|QtGui.QMessageBox.No)
        if res == QtGui.QMessageBox.Yes:
            del self.workingDict['zoneinfo']['zonecontributions']['recs'][key]
            self.workingDict['zoneinfo']['zonecontributions']['editdate'] = datetime.datetime.now().isoformat()
            f = open(self.workingFile,'w')
            f.write(json.dumps(self.projDict))
            f.close()
            self.zoneContLoadList()
        self.zoneContDisableEditing()

    #
    # enable zone contribution record editing
    
    def zoneContEnableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.tblZoneConts.setDisabled(True)
        self.frZoneContWidgets.setEnabled(True)
        # buttons
        self.pbNewZoneCont.setDisabled(True)
        self.pbSaveZoneCont.setEnabled(True)
        self.pbCancelZoneCont.setEnabled(True)
        self.pbDeleteZoneCont.setEnabled(True)
        # main form
        self.pbClose.setDisabled(True)
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)

    #
    # disable zone contribution record editing
    
    def zoneContDisableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.tblZoneConts.setEnabled(True)
        self.frZoneContWidgets.setDisabled(True)
        self.tblZoneConts.clearSelection()
        self.cbZoneContZone.setCurrentIndex(0)
        self.cbZoneContFeature.setCurrentIndex(0)
        self.spbxZoneContFraction.setValue(0.0)
        # buttons
        self.pbNewZoneCont.setEnabled(True)
        self.pbSaveZoneCont.setDisabled(True)
        self.pbCancelZoneCont.setDisabled(True)
        self.pbDeleteZoneCont.setDisabled(True)
        # main form
        self.pbClose.setEnabled(True)
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)

    #
    # Zone Boundary Costs Tab
    #

    #
    # load list of zone boundary cost records to table
    
    def zoneBounCostLoadList(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.projDict['zoneinfo']['zoneboundarycosts']['recs']
        rc = len(zDict)
        self.tblZoneBounCosts.clear()
        self.tblZoneBounCosts.setColumnCount(3)
        self.tblZoneBounCosts.setRowCount(rc)
        self.tblZoneBounCosts.setHorizontalHeaderLabels(['Zone 1 Id','Zone 2 Id','Boundary Cost'])
        self.tblZoneBounCosts.setColumnWidth(0,100)
        self.tblZoneBounCosts.setColumnWidth(1,100)
        self.tblZoneBounCosts.setColumnWidth(2,150)
        x = 0
        for key, value in zDict.iteritems():
            vList = key.split('-')
            vList.append(value)
            self.zoneBounCostAddToTable(x,vList)
            x += 1

    #
    # add zone boundary cost record to table
    
    def zoneBounCostAddToTable(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # zone id 1
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[0]))
        item.setToolTip('Zone 1 Id')
        self.tblZoneBounCosts.setItem(x,0,item)
        # zone id 2
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[1]))
        item.setToolTip('Zone 2 Id')
        self.tblZoneBounCosts.setItem(x,1,item)
        # zone boundary cost
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        item.setText(str(value[2]))
        item.setToolTip('Boundary Cost')
        self.tblZoneBounCosts.setItem(x,2,item)

    #
    # load zone boundary cost for editing
    
    def zoneBounCostLoad(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zDict = self.workingDict['zoneinfo']['zoneboundarycosts']['recs']
        cr = self.tblZoneBounCosts.currentRow()
        zId1 = self.tblZoneBounCosts.item(cr,0).text().split('-')[0]
        zId2 = self.tblZoneBounCosts.item(cr,1).text().split('-')[0]
        key = zId1 + '-' + zId2
        bc = zDict[key]
        zString = zId1+'-'+self.workingDict['zones_costs']['zones']['recs'][zId1]
        idx = self.cbZoneBounCostZone1.findText(zString)
        if idx <> -1:
            self.cbZoneBounCostZone1.setCurrentIndex(idx)
        else:
            self.cbZoneBounCostZone1.setCurrentIndex(0)
        zString = zId2+'-'+self.workingDict['zones_costs']['zones']['recs'][zId2]
        idx = self.cbZoneBounCostZone2.findText(zString)
        if idx <> -1:
            self.cbZoneBounCostZone2.setCurrentIndex(idx)
        else:
            self.cbZoneBounCostZone2.setCurrentIndex(0)
        self.spbxBoundaryCost.setValue(float(bc))
        
    #
    # select a zone boundary cost record from table for editing
    
    def zoneBounCostSelect(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if len(self.tblZoneBoundaryCosts.selectedItems()) > 0:
            self.zoneBounCostLoad()
            self.zoneBounCostEnableEditing()

    #
    # create a new zone boundary cost record
    
    def zoneBounCostNew(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.zoneBounCostEnableEditing()

    #
    # save zone boundary cost record
    
    def zoneBounCostSave(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        zId1 = self.cbZoneBounCostZone1.currentText().split('-')[0]
        zId2 = self.cbZoneBounCostZone2.currentText().split('-')[0]
        key = zId1 + '-' + zId2
        keyAlt = zId2 + '-' + zId1
        if not keyAlt in self.workingDict['zoneinfo']['zoneboundarycosts']['recs']:
            self.workingDict['zoneinfo']['zoneboundarycosts']['recs'][key] = str(self.spbxBoundaryCost.value())
            self.workingDict['zoneinfo']['zoneboundarycosts']['editdate'] = datetime.datetime.now().isoformat()
            f = open(self.workingFile,'w')
            f.write(json.dumps(self.projDict))
            f.close()
        self.zoneBounCostDisableEditing()
        self.zoneBounCostLoadList()

    #
    # cancel editing of a zone boundary cost record
    
    def zoneBounCostCancel(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.zoneBounCostDisableEditing()

    #
    # delete zone boundary cost record
    
    def zoneBounCostDelete(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        cr = self.tblZoneBounCosts.currentRow()
        zId1 = self.tblZoneBounCosts.item(cr,0).text().split('-')[0]
        zId2 = self.tblZoneBounCosts.item(cr,1).text().split('-')[0]
        key = zId1 + '-' + zId2
        res = QtGui.QMessageBox.warning(self, 'Warning',
           "Are you sure you want to delete this zone boundary cost?", QtGui.QMessageBox.Yes|QtGui.QMessageBox.No)
        if res == QtGui.QMessageBox.Yes:
            del self.workingDict['zoneinfo']['zoneboundarycosts']['recs'][key]
            self.workingDict['zoneinfo']['zoneboundarycosts']['editdate'] = datetime.datetime.now().isoformat()
            f = open(self.workingFile,'w')
            f.write(json.dumps(self.projDict))
            f.close()
            self.zoneBounCostLoadList()
        self.zoneBounCostDisableEditing()

    #
    # enable editing of a zone boundary cost record
    
    def zoneBounCostEnableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.tblZoneBounCosts.setDisabled(True)
        self.frZoneBounCostWidgets.setEnabled(True)
        # buttons
        self.pbNewZoneBounCost.setDisabled(True)
        self.pbSaveZoneBounCost.setEnabled(True)
        self.pbCancelZoneBounCost.setEnabled(True)
        self.pbDeleteZoneBounCost.setEnabled(True)
        # main form
        self.pbClose.setDisabled(True)
        self.lblWorkingProject.setDisabled(True)
        self.cbWorkingProject.setDisabled(True)

    #
    # disable eding of zone boundary cost records
    
    def zoneBounCostDisableEditing(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # controls
        self.tblZoneBounCosts.setEnabled(True)
        self.tblZoneBounCosts.clearSelection()
        self.frZoneBounCostWidgets.setDisabled(True)
        self.cbZoneBounCostZone1.setCurrentIndex(0)
        self.cbZoneBounCostZone2.setCurrentIndex(0)
        self.spbxBoundaryCost.setValue(0.0)
        # buttons
        self.pbNewZoneBounCost.setEnabled(True)
        self.pbSaveZoneBounCost.setDisabled(True)
        self.pbCancelZoneBounCost.setDisabled(True)
        self.pbDeleteZoneBounCost.setDisabled(True)
        # main form
        self.pbClose.setEnabled(True)
        self.lblWorkingProject.setEnabled(True)
        self.cbWorkingProject.setEnabled(True)

