"""
# -*- coding: utf-8 -*-
#
# ========================================================
# 
# Purpose: Import Marxan Results
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

from qgis.core import *
from PyQt4 import QtCore, QtGui
import traceback, time, os, math, sys
from qmz_utils import qmzGrid
from processing.tools import dataobjects, vector
from collections import Counter
import ogr, gdal, inspect, glob, csv
import numpy as np


class importContent(QtCore.QObject):

    #
    # Class Initialization
    #
    
    def __init__(self, puLyr, txtFile, puKey, txtKey, delim, destField, *args, **kwargs):
        QtCore.QObject.__init__(self, *args, **kwargs)
        self.allPercentage = 0
        self.calcPercentage = 0
        self.stepPercentage = 0
        self.stepCount = 1
        self.abort = False
        self.encoding = u'UTF-8'
        self.tempPrefix = 'qmz%d_' % os.getpid()
        self.puLyr = puLyr
        self.txtFile = txtFile
        self.puKey = puKey
        self.txtKey = txtKey
        self.delim = delim
        self.destField = destField
        #
        self.debug = False
        if self.debug == True:
            self.myself = lambda: inspect.stack()[1][3]
            QgsMessageLog.logMessage(self.myself())


    #
    # Starting and Stopping
    #

    #
    # run process
    
    def run(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        try:
            messageText = ''
            self.workerStatus.emit('Started')
            # get text file as dictionary
            self.progressAll.emit(100)
            self.stepCount = 2
            self.progressUpdateImport(1)
            self.workerStatus.emit('Reading text file')
            f = open(self.txtFile,'rb')
            inputVals = {}
            reader = csv.reader(f, delimiter = self.delim)
            header = reader.next()
            if (header[0].upper() == 'PUID' or header[0].upper() == 'PLANNING_UNIT') and \
                ( header[1].upper() == 'SOLUTION' or header[1].upper() == 'NUMBER'):
                for row in reader:
                    inputVals[int(row[0])] = float(row[1])
            else:
                self.workerStatus.emit('Invalid File')
                self.kill()
            f.close()
            # import file
            self.progressUpdateImport(2)
            self.workerStatus.emit('Importing records')
            if self.puLyr.isValid():
                # ensure destination field exists and create if needed
                fields = self.puLyr.dataProvider().fields()
                puidIdx = fields.indexFromName(self.puKey)
                destIdx = fields.indexFromName(self.destField)
                if destIdx == -1:
                    try:
                        res = self.puLyr.dataProvider().addAttributes([QgsField(self.destField, QtCore.QVariant.Double, "real", 19, 10)])
                        self.puLyr.updateFields()
                        fields = self.puLyr.dataProvider().fields()
                        destIdx = fields.indexFromName(self.destField)
                    except:
                        pass 
                    if destIdx == -1:
                        self.workerStatus.emit('Can not create field')
                        self.abort = True
                        return
                total = self.puLyr.featureCount()
                current = 1
                lastPercent = 0.0
                self.progressStep.emit(lastPercent)
                featIter = self.puLyr.getFeatures(QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry))
                updateMap = {}
                for feat in featIter:
                    puid = feat.attributes()[puidIdx]
                    if puid in inputVals:
                        updateMap[feat.id()] = {destIdx : inputVals[puid]}
                    else:
                        updateMap[feat.id()] = {destIdx : 0.0}
                    current += 1
                    buildPercent = float(current) / float(total) * 100
                    # limit signals to increase processing speed
                    if int(buildPercent) > lastPercent and buildPercent <= 99.0:
                        self.progressStep.emit(buildPercent)
                        lastPercent = buildPercent
                        if self.abort:
                            break 
                self.puLyr.dataProvider().changeAttributeValues(updateMap)
            if self.abort == False:
                self.workerStatus.emit('Completed')
                self.workerFinished.emit(True,'Import Completed')
            else:
                self.workerStatus.emit('Cancelled')
                self.workerFinished.emit(True,'Import Cancelled')
        except Exception, e:
            import traceback
            if messageText == '':
                messageText == 'An error occurred'
            self.workerError.emit(e, traceback.format_exc(),messageText)
            self.workerFinished.emit(False,'Import Failed')
        self.kill()

    #
    # kill worker

    def kill(self):

        #self.workerStatus.emit('Cancelled')
        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.abort = True
        #self.workerFinished.emit(True)

    #
    # Notifications
    #

    #
    # update creation progress
    
    def progressUpdateImport(self, stepNumber):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.importPercentage = stepNumber / float(self.stepCount) * 100
        self.progressImport.emit(self.importPercentage)

    #
    # update all process

    def progressUpdateAll(self, calcNumber):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.allPercentage = calcNumber / float(len(self.calcList)) * 100
        self.progressAll.emit(self.allPercentage)


    progressAll = QtCore.pyqtSignal(int)
    progressImport = QtCore.pyqtSignal(int)
    progressStep = QtCore.pyqtSignal(int)
    workerStatus = QtCore.pyqtSignal(str)
    workerError = QtCore.pyqtSignal(Exception, basestring, str)
    workerFinished = QtCore.pyqtSignal(bool,str)
