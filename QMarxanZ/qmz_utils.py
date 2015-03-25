"""
# -*- coding: utf-8 -*-
#
# ========================================================
# 
# Purpose: QMZ Utilities
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

import traceback, time, os, math, sys, datetime, glob, inspect
from qgis.core import *
from PyQt4 import QtCore, QtGui

#
# qmzGrid - methods to calculate grid cell count and great a grid
#

class qmzGrid:

    def __init__(self):
        pass
        
    #
    # calculate number of square cells

    def calcSquareCount(self,sideLength,xMin,xMax,yMin,yMax):

        xRange = xMax - xMin
        xRows = xRange / float(sideLength)
    #    QgsMessageLog.logMessage('xRange: %f, xRows: %f' % (xRange,xRows))
        if xRows > int(xRows):
            xRows = int(xRows) + 1
        else:
            xRows = int(xRows)
        yRange = yMax - yMin
        yRows = yRange / float(sideLength)
    #    QgsMessageLog.logMessage('yRange: %f, yRows: %f' % (yRange,yRows))
        if yRows > int(yRows):
            yRows = int(yRows) + 1
        else:
            yRows = int(yRows)
        cellCount = xRows * yRows
    #    QgsMessageLog.logMessage('xRows: %d, yRows: %d, cellCount %d' % (xRows,yRows,cellCount))
        return(cellCount)

    #
    # calculate square side length based on area

    def calcSquareSideLength(self,unitArea):

        squareSideLength = math.sqrt(unitArea)
        return(squareSideLength)

    #
    # calculate square area based on side length

    def calcSquareArea(self,sideLength):

        squareArea = sideLength * sideLength
        return(squareArea)

    #
    # hexagon trig

    def hexagonTrig(self,sideLength):
        
        # basic trig
        angle_a = math.radians(30)
        hyp = sideLength
        side_a = hyp * math.sin(angle_a)
        side_b = hyp * math.cos(angle_a)
        return(hyp,side_a,side_b)

    #
    # calculate number of hexagon cells

    def calcHexagonCount(self,sideLength,xMin,xMax,yMin,yMax):

        hyp, side_a, side_b = self.hexagonTrig(sideLength)
        xUnits = hyp + side_a
        yUnits = side_b * 2
        xRange = xMax - xMin
        yRange = yMax - yMin
        xRows = xRange / float(xUnits)
    #    QgsMessageLog.logMessage('xRange: %f, yRange: %f' % (xRange,yRange))
    #    QgsMessageLog.logMessage('xUnits: %f, yUnits: %s' % (xUnits,yUnits))
    #    QgsMessageLog.logMessage('xRows: %f ' % xRows)
        if xRows > int(xRows):
            xRows = int(xRows) + 1
        else:
            xRows = int(xRows)
        yRows = yRange / float(yUnits)
    #    QgsMessageLog.logMessage('yRows: %f ' % yRows)
        if yRows > int(yRows):
            yRows = int(yRows) + 1
        else:
            yRows = int(yRows)
        cellCount = xRows * yRows
    #    QgsMessageLog.logMessage('xRows: %d, yRows: %d, cellCount %d' % (xRows,yRows,cellCount))
        return(cellCount)

    #
    # calculate hexagon side length based on area

    def calcHexagonSideLength(self,unitArea):   

        triangleArea = unitArea/6.0
        #
        # area of an equilateral triangle = length^2 * sqrt(3)/4 
        # sqrt(3)/4 * area = length^2
        # sqrt( sqrt(3)/4 * area) = length
        #
        hexagonSideLength = math.sqrt( triangleArea / (math.sqrt(3.0)/4.0) )
        return(hexagonSideLength)

    #
    # calcualte hexagon area based on side length

    def calcHexagonArea(self,sideLen):

        #
        # area of an equilateral triangle = length^2 * sqrt(3)/4 
        # sqrt(3)/4 * area = length^2
        # sqrt( sqrt(3)/4 * area) = length
        #
        tarea = float(sideLen)**2 * math.sqrt(3)/4
        return(tarea*6)

    #
    # create hexagon points

    def createHexagon(self,x, y, sideLen):

        hyp, side_a, side_b = self.hexagonTrig(sideLen)
        # create points
        pt1 = QgsPoint(x, y)
        pt2 = QgsPoint(x + hyp, y)
        pt3 = QgsPoint(x + hyp + side_a, y - side_b)
        pt4 = QgsPoint(x + hyp, y - (2 * side_b))
        pt5 = QgsPoint(x, y - (2 * side_b))
        pt6 = QgsPoint(x - side_a, y - side_b)
        pt7 = QgsPoint(x, y)
        hexagon = [[pt1, pt2, pt3, pt4, pt5, pt6, pt7]]
        return(hexagon)

    #
    # create square

    def createSquare(self,x, y, sideLen):

        pt1 = QgsPoint(x,y)
        pt2 = QgsPoint(x+sideLen,y)
        pt3 = QgsPoint(x+sideLen,y-sideLen)
        pt4 = QgsPoint(x,y-sideLen)
        pt5 = QgsPoint(x,y)
        square = [[pt1, pt2, pt3, pt4, pt5]]
        return(square)


#
# qmzCalcChecks - methods to create determine what needs to be calculated for
#                 GIS, file export, etc
#

class qmzCalcChecks:

    def __init__(self):

        self.dateTimeFormat = '%Y-%m-%dT%H:%M:%S.%f'
        self.debug = False
        self.puid = None
        if self.debug == True:
            self.myself = lambda: inspect.stack()[1][3]
            QgsMessageLog.logMessage(self.myself())

    #
    # create gis calculation report

    def gisCalculationsReport(self,projectDict,puLyr,layerList,defaultDir,crs):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        calcList = []
        self.puid = projectDict['project']['puid']
        # determine if PU layer is set for the default project
        if projectDict['project']['puLyr'] == '--Not Set--':
            summary = 'No Planning Unit Layer set for this project. '
            summary += 'This must be set to perform GIS calculations.\n'
        else:
            # get list of GIS sources that require calculation
            gisDict = projectDict['gis']['recs']
            for key, value in gisDict.iteritems():
                calcInfo = self.gisCalculationsCheck(key,value,puLyr,layerList,defaultDir,crs)
                if calcInfo <> {}:
                    calcList.append(calcInfo)
            # create report
            # calculations
            calcCount = len(calcList)
            if calcCount > 0:
                summary = 'GIS calculations are incomplete or need updating\n'
                summary += 'The following %d calculations are needed:\n' % calcCount
                for rec in calcList:
                    summary += '%s: %s\n' % (rec['name'],rec['reason'])
            else:
                summary = 'GIS calculations are complete and appear current\n'
        return(calcList,summary)
    
    #
    # check gis calculation status

    def gisCalculationsCheck(self,gisId,gisRec,puLyr,layerList,defaultDir,crs):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        calcInfo = {}
        if gisRec['status'] == 'PU Field':
            # confirm PU Layer is available
            reason = ''
            if puLyr <> None:
                srcFile = puLyr.source()
                # confirm field exists
                fieldOk = False
                fields = puLyr.dataProvider().fields()
                for field in fields:
                    if field.name() == gisRec['calcfield']:
                        fieldOk = True
                        break
                if fieldOk:
                    # check exports to test recency
                    # get most recent modify date of file source
                    fName = os.path.splitext(srcFile)[0]
                    shpDate = datetime.datetime.fromtimestamp(os.path.getmtime(fName+'.shp'))
                    dbfDate = datetime.datetime.fromtimestamp(os.path.getmtime(fName+'.dbf'))
                    srcDate = max(shpDate,dbfDate)
                    # get date of GIS source last configuration change
                    configDate = datetime.datetime.strptime(gisRec['editdate'],self.dateTimeFormat)
                    # check if export exists
                    outFName = os.path.join(defaultDir,'qmzfiles','%04d' % int(gisId))
                    calcNeeded = False
                    if os.path.exists(outFName+'.qmi'):
                        # get recent date of exported source
                        calcDate = datetime.datetime.fromtimestamp(os.path.getmtime(outFName+'.qmi'))
                        # check if either GIS source of GIS config are alter than calc file dates
                        if srcDate > calcDate:
                            calcNeeded = True
                            reason = 'Source was modified after calculation was completed'
                        elif configDate > calcDate:
                            calcNeeded = True
                            reason = 'QMZ configuration was modified after calculation was completed'
                    else:
                        calcNeeded = True
                        reason = 'Uncalculated'
            else:
                calcNeeded = False
            # add if needed
            if calcNeeded:
                # notification use
                calcInfo['name'] = gisRec['name']
                calcInfo['reason'] = reason
                # calculation use
                calcInfo['key'] = gisId
                calcInfo['puLyr'] = puLyr
                calcInfo['idField'] = self.puid
                calcInfo['geomType'] = 'pufield'
                calcInfo['srcLyr'] = None
                calcInfo['singleField'] = True
                calcInfo['useRaster'] = False
                calcInfo['calcType'] = 'measure'
                calcInfo['calcField'] = gisRec['calcfield']
                calcInfo['intersectOp'] = 'sum'
                calcInfo['destType'] = 'file'
                calcInfo['destName'] = outFName
                calcInfo['pixelSize'] = 0
                calcInfo['crs'] = crs
                calcInfo['srcNDValue'] = 0
                calcInfo['description'] = gisRec['description']
        elif gisRec['status'] == 'GIS Source':
            # confirm src Layer is available
            srcLyr = None
            srcFile = ''
            for lyr in layerList:
                if lyr[1] == gisRec['layername']:
                    srcLyr = lyr[3]
                    break
            if srcLyr <> None:
                srcFile = srcLyr.source()
                proceed = False
                if gisRec['layertype'] <> 'Raster' and \
                gisRec['measuretype'] == 'Measure x Field' and \
                gisRec['calcfield'] <> '':
                    # confirm field exists
                    fields = srcLyr.dataProvider().fields()
                    for field in fields:
                        if field.name() == gisRec['calcfield']:
                            proceed = True
                            break
                else:
                    proceed = True
                if proceed:
                    # check exports to test recency
                    # get most recent modify date of file source
                    if gisRec['layertype'] == 'Raster':
                        srcDate = datetime.datetime.fromtimestamp(os.path.getmtime(srcFile))
                    else:
                        fName = os.path.splitext(srcFile)[0]
                        shpDate = datetime.datetime.fromtimestamp(os.path.getmtime(fName+'.shp'))
                        dbfDate = datetime.datetime.fromtimestamp(os.path.getmtime(fName+'.dbf'))
                        srcDate = max(shpDate,dbfDate)
                    # get date of GIS source last configuration change
                    configDate = datetime.datetime.strptime(gisRec['editdate'],self.dateTimeFormat)
                    # check if export exists
                    outFName = os.path.join(defaultDir,'qmzfiles','%04d' % int(gisId))
                    calcNeeded = False
                    if os.path.exists(outFName+'.qmi'):
                        # get recent date of exported source
                        calcDate = datetime.datetime.fromtimestamp(os.path.getmtime(outFName+'.qmi'))
                        # check if either GIS source of GIS config are alter than calc file dates
                        if srcDate > calcDate:
                            calcNeeded = True
                            reason = 'Source was modified after calculation was completed'
                        elif configDate > calcDate:
                            calcNeeded = True
                            reason = 'QMZ configuration was modified after calculation was completed'
                    else:
                        calcNeeded = True
                        reason = 'Uncalculated'
            else:
                calcNeeded = False
            # add if needed
            if calcNeeded:
                # notification use
                calcInfo['name'] = gisRec['name']
                calcInfo['reason'] = reason
                # calculation use
                calcInfo['key'] = gisId
                calcInfo['puLyr'] = puLyr
                calcInfo['idField'] = self.puid
                calcInfo['geomType'] = gisRec['layertype'].lower()
                calcInfo['srcLyr'] = srcLyr
                #
                if gisRec['singlemulti'] == 'Single Field':
                    calcInfo['singleField'] = True
                else:
                    calcInfo['singleField'] = False
                    #outFName = os.path.join(self.defaultDir,'qmzfiles','%s' % fPrefix)
                #
                if gisRec['calcmethod'] == 'Raster Estimation' or gisRec['layertype'] == 'Raster':
                    calcInfo['useRaster'] = True
                else:
                    calcInfo['useRaster'] = False
                #
                if gisRec['measuretype'] == 'Measure':
                    calcInfo['calcType'] = 'measure'
                elif gisRec['measuretype'] in ['Measure x Field','Measure x Value']:
                    calcInfo['calcType'] = 'calculate'
                else:
                    calcInfo['calcType'] = 'value'
                #
                calcInfo['calcField'] = gisRec['calcfield']
                calcInfo['intersectOp'] = gisRec['intaction'].lower()
                calcInfo['destType'] = 'file'
                calcInfo['destName'] = outFName
                calcInfo['pixelSize'] = gisRec['pixelsize']
                calcInfo['crs'] = crs
                calcInfo['description'] = gisRec['description']
                # get ND value from raster if available
                if calcInfo['geomType'] == 'raster':
                    if calcInfo['srcLyr'].dataProvider().srcHasNoDataValue(1):
                        srcNDValue = calcInfo['srcLyr'].dataProvider().srcNoDataValue(1)
                    else:
                        srcNDValue = 0
                else:
                    srcNDValue = 0
                calcInfo['srcNDValue'] = srcNDValue
        return(calcInfo)
        
    #
    # check if problem definition in relation to gis calculations

    def definitionStatus(self,projectDir,projectDict):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        status = True
        actionList = []
        summary = ''
        qmiDir = os.path.join(projectDir,'qmzfiles')
        if os.path.exists(qmiDir):
            featDict = projectDict['features']['recs']
            if featDict == {}:
                summary += 'No Features defined.\n'
                status = False
            costDict = projectDict['costs']['recs']
            if costDict == {}:
                summary += 'No Costs defined.\n'
                status = False
            if status:
                qmdList = glob.glob(os.path.join(qmiDir,'*.qmd'))
                usedCount = len(featDict) + len(costDict)
                if len(qmdList) > usedCount:
                    for qmdFile in qmdList:
                        path,fName = os.path.split(qmdFile)
                        key,ext = os.path.splitext(fName)
                        if not key in featDict and not key in costDict:
                            actionList.append('%s is not used\n' % key)
                    actionList.sort()
                    if len(actionList) > 0:
                        summary = 'WARNING: There are more GIS outputs than the total number of '
                        summary += 'defined features and costs.\n'
                        summary += 'The following GIS outputs were not used as costs or features:\n'
                        for action in actionList:
                            summary += action
                        summary += 'You can proceed but are  '
                        summary += 'encouraged to check the completeness of your problem '
                        summary += 'definition before proceeding; this can be done by '
                        summary += 'closing this window and opening the Marxan Problem '
                        summary += 'Definition window.\n\n'
                actionList = []
                additionalText = False
                for key, value in featDict.iteritems():
                    fName = key.split('-')[0]
                    outFName = os.path.join(qmiDir,fName)
                    qmiDate = datetime.datetime.fromtimestamp(os.path.getmtime(outFName+'.qmi'))
                    configDate = datetime.datetime.strptime(value['editdate'],self.dateTimeFormat)
                    if qmiDate > configDate:
                        actionList.append('%s (%s)\n' % (key,value['name']))
                actionList.sort()
                if len(actionList) > 0:
                    summary += 'The following feature calculations were updated after definition:\n'
                    for action in actionList:
                        summary += action
                    additionalText = True
                actionList = []
                for key, value in costDict.iteritems():
                    fName = key.split('-')[0]
                    outFName = os.path.join(qmiDir,fName)
                    qmiDate = datetime.datetime.fromtimestamp(os.path.getmtime(outFName+'.qmi'))
                    configDate = datetime.datetime.strptime(value['editdate'],self.dateTimeFormat)
                    if qmiDate > configDate:
                        actionList.append('%s (%s)\n' % (key,value['name']))
                actionList.sort()
                if len(actionList) > 0:
                    summary += 'The following cost calculations were updated after definition:\n'
                    for action in actionList:
                        summary += action
                    additionalText = True
                if summary == '':
                    summary = 'All GIS sources are used and definitions appear up-to-date.\n'
        return(status,summary)

    #
    # check if export files are up to date

    def exportStatus(self,projectDir,projectDict,puLyr):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        actionDict = {}
        summary = ''
        marxanDir = os.path.join(projectDir,'marxan')
        puDate = datetime.datetime.fromtimestamp(os.path.getmtime(puLyr.source()))
        # check if input.dat is up to date
        # the output should be newer than the settings
        fName = os.path.join(marxanDir,'input.dat')
        if os.path.exists(fName):
            fileDate = datetime.datetime.fromtimestamp(os.path.getmtime(fName))
            configDate = datetime.datetime.strptime(projectDict['settings']['editdate'],self.dateTimeFormat)
            if fileDate < configDate:
                actionDict['input'] = ['update',fName]
                summary += 'input.dat needs to be updated\n'
        else:
            actionDict['input'] = ['create',fName]
            summary += 'input.dat needs to be created\n'
        # check if bound.dat is up-to-date
        # the output should be newer than the boundary settings and the planning unit shapefile edit dates
        inputDir = os.path.join(marxanDir,'input')
        fName = os.path.join(inputDir,'bound.dat')
        if os.path.exists(fName):
            fileDate = datetime.datetime.fromtimestamp(os.path.getmtime(fName))
            configDate = datetime.datetime.strptime(projectDict['settings']['boundary']['editdate'],self.dateTimeFormat)
            if fileDate < configDate or fileDate < puDate:
                actionDict['bound'] = ['update',fName]
                summary += 'bound.dat needs to be updated\n'
        else:
            actionDict['bound'] = ['create',fName]
            summary += 'bound.dat needs to be created\n'
        # check if pu.dat is up-to-date
        # the output should be newer than the pu status setting, costs and the planning unit shapefile 
        fName = os.path.join(inputDir,'pu.dat')
        if os.path.exists(fName):
            fileDate = datetime.datetime.fromtimestamp(os.path.getmtime(fName))
            boundDate = datetime.datetime.strptime(projectDict['settings']['boundary']['editdate'],self.dateTimeFormat)
            costsDate = datetime.datetime.strptime(projectDict['costs']['editdate'],self.dateTimeFormat)
            if fileDate < boundDate or fileDate < costsDate or fileDate < puDate:
                actionDict['pu'] = ['update',fName]
                summary += 'pu.dat needs to be updated\n'
        else:
            actionDict['pu'] = ['create',fName]
            summary += 'pu.dat needs to be created\n'
        # check if spec.dat is up-to-date
        # the output should be newer than either the entire features data set
        # or any individual feature description
        fName = os.path.join(inputDir,'spec.dat')
        if os.path.exists(fName):
            fileDate = datetime.datetime.fromtimestamp(os.path.getmtime(fName))
            featDate = datetime.datetime.strptime(projectDict['features']['editdate'],self.dateTimeFormat)
            featsDate = featDate
            for key,value in projectDict['features']['recs'].iteritems():
                nDate = datetime.datetime.strptime(value['editdate'],self.dateTimeFormat)
                if nDate > featsDate:
                    featsDate = nDate
            if fileDate < featDate or fileDate < featsDate:
                actionDict['spec'] = ['update',fName]
                summary += 'spec.dat needs to be updated\n'
        else:
            actionDict['spec'] = ['create',fName]
            summary += 'spec.dat needs to be created\n'
        # check if puvspr.dat is up-to-date
        # the output should be newer than the entire features data set
        # this means that features have been added or removed
        # also update if the puDate is newer in case there are updates to the field
        fName = os.path.join(inputDir,'puvsp.dat')
        if os.path.exists(fName):
            fileDate = datetime.datetime.fromtimestamp(os.path.getmtime(fName))
            featDate = datetime.datetime.strptime(projectDict['features']['editdate'],self.dateTimeFormat)
            if fileDate < featDate or fileDate < puDate:
                actionDict['puvsp'] = ['update',fName]
                summary += 'puvsp.dat needs to be updated\n'
        else:
            actionDict['puvsp'] = ['create',fName]
            summary += 'puvsp.dat needs to be created\n'
        if summary <> '':
            summary = 'The following Marxan input files are missing or out of date:\n' + summary
        else:
            summary = 'All export files are up to date'
        return(actionDict,summary)

    #
    # check if output files are up to date

    def outputStatus(self,projectDir):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        actionDict = {}
        status = True
        summary = ''
        # set directories
        marxanDir = os.path.join(projectDir,'marxan')
        inputDir = os.path.join(marxanDir,'input')
        outputDir = os.path.join(marxanDir,'output')
        # get input dates
        infName = os.path.join(marxanDir,'input.dat')
        infDate = datetime.datetime.fromtimestamp(os.path.getmtime(infName))
        bdfName = os.path.join(inputDir,'bound.dat')
        bdfDate = datetime.datetime.fromtimestamp(os.path.getmtime(bdfName))
        pufName = os.path.join(inputDir,'pu.dat')
        pufDate = datetime.datetime.fromtimestamp(os.path.getmtime(pufName))
        spfName = os.path.join(inputDir,'spec.dat')
        spfDate = datetime.datetime.fromtimestamp(os.path.getmtime(spfName))
        pvfName = os.path.join(inputDir,'puvsp.dat')
        pvfDate = datetime.datetime.fromtimestamp(os.path.getmtime(pvfName))
        # get output dates
        olfName = os.path.join(marxanDir,'output','output_mvbest.csv')
        if os.path.exists(olfName):
            olfDate = datetime.datetime.fromtimestamp(os.path.getmtime(olfName))
        else:
            olfName = os.path.join(marxanDir,'output','output_mvbest.dat')
            if os.path.exists(olfName):
                olfDate = datetime.datetime.fromtimestamp(os.path.getmtime(olfName))
            else:
                status = False
                summary = 'Output files cannot be found or are incomplete\n'
        if status:
            if max(infDate,bdfDate,pufDate,spfDate,pvfDate) > olfDate:
                status = False
                summary = 'Input files are newer than output files\n'
            else:
                summary = 'Output files are up to date\n'
        return(status,summary)
#
# qmzReports - create reports as csv or text files to track status of project
#
