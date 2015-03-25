"""
# -*- coding: utf-8 -*-
#
# ========================================================
# 
# Purpose: Create Marxan input files
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
import traceback, time, os, math, sys, inspect, datetime, csv, json, numpy, time
from batch_sort import batch_sort
from processing.tools import dataobjects, vector

#
# create marxan input files
#
class exportContent(QtCore.QObject):
    
    def __init__(self,puLyr,projectDict,actionDict,projectFile,projectDir,*args,**kwargs):

        QtCore.QObject.__init__(self,*args,**kwargs)
        self.calcPercentage = 0
        self.stepPercentage = 0
        self.stepCount = 1
        self.abort = False
        self.puLyr = puLyr
        self.projectDict = projectDict
        self.actionDict = actionDict
        self.projectFile = projectFile
        self.projectDir = projectDir
        self.dateTimeFormat = '%Y-%m-%dT%H:%M:%S.%f'
        
        self.debug = False
        if self.debug == True:
            self.myself = lambda: inspect.stack()[1][3]
            QgsMessageLog.logMessage(self.myself())

    #
    # run process
    
    def run(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
            QgsMessageLog.logMessage(str(self.actionDict))
        try:
            self.workerStatus.emit('Started')
            messageText = ''
            # conduct calculation in specific order
            # spec.dat must be done before puvsp files to ensure
            # that exportnumbers line up
            x = 1
            if 'input' in self.actionDict:
                self.progressUpdateAll(x)
                x += 1
                self.stepCount = 1
                self.progressUpdateCalc(1)
                self.workerStatus.emit('Creating input.dat file')
                self.createInputFile(self.actionDict['input'][1])
            if 'bound' in self.actionDict:
                self.progressUpdateAll(x)
                x += 1
                self.stepCount = 3
                self.workerStatus.emit('Creating bound.dat file')
                errorCount,messageText = self.createBoundFile(self.actionDict['bound'][1])
                if errorCount > 0:
                    raise Exception('Topology error(s)')
            if 'pu' in self.actionDict:
                self.progressUpdateAll(x)
                x += 1
                self.stepCount = 4
                self.workerStatus.emit('Creating pu.dat file')
                status,messageText = self.createPUFile(self.actionDict['pu'][1])
                if status == -1:
                    raise Exception('Invalid status value(s)')
            if 'spec' in self.actionDict:
                self.progressUpdateAll(x)
                x += 1
                self.stepCount = 1
                self.progressUpdateCalc(1)
                self.workerStatus.emit('Creating spec.dat file')
                self.createSpecFile(self.actionDict['spec'][1])
            if 'puvsp' in self.actionDict:
                self.progressUpdateAll(x)
                self.stepCount = 2
                self.workerStatus.emit('Creating puvsp.dat file')
                self.createPUvSPFile(self.actionDict['puvsp'][1])
            self.workerStatus.emit('Completed')
            self.workerFinished.emit(True,messageText)
        except Exception, e:
            import traceback
            if messageText == '':
                messageText == 'An error occurred'
            self.workerError.emit(e, traceback.format_exc(),messageText)
            self.workerFinished.emit(False,messageText)
        self.kill()

    #
    # kill worker

    def kill(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.abort = True

    #
    # Notifications
    #

    #
    # update creation progress
    
    def progressUpdateCalc(self,stepNumber):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.calcPercentage = stepNumber / float(self.stepCount) * 100
        self.progressCalc.emit(self.calcPercentage)

    #
    # update all process

    def progressUpdateAll(self,calcNumber):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.allPercentage = calcNumber / float(len(self.actionDict)) * 100
        self.progressAll.emit(self.allPercentage)

    #
    # create input.dat file

    def createInputFile(self,outFName):

        #
        # formatAsME - format as Marxan Exponent format like 
        #              Input File Editor
        #
        def formatAsME(inVal):
            outStr = "%.14E" % float(inVal)
            parts = outStr.split('E')
            sign = parts[1][:1]
            exponent = "%04d" % float(parts[1][1:])
            outStr = parts[0] + 'E' +  sign + exponent
            return(outStr)
            
        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())

        sDict = self.projectDict['settings']
        #QgsMessageLog.logMessage(str(sDict))
        nl = os.linesep
        f = open(outFName, 'w')
        creditText = "Input file for Annealing program.%s%s" % (nl,nl)
        creditText += "This file generated by QMarxanZ%s" % nl
        creditText += "created by Apropos Information Systems Inc.%s%s" % (nl,nl)
        f.write(creditText)
        f.write("General Parameters%s" % nl)
        f.write("VERSION %s%s" % ('0.1',nl))
        f.write("BLM %s%s" % (formatAsME(sDict['general']['recs']['blm']),nl))
        f.write("PROP %s%s" % (formatAsME(sDict['general']['recs']['proportion']),nl))
        f.write("RANDSEED %d%s" % (sDict['other']['recs']['randseed'],nl))
        f.write("NUMREPS %d%s" % (sDict['general']['recs']['numreps'],nl))
        f.write("%sAnnealing Parameters%s" % (nl,nl))
        f.write("NUMITNS %d%s" % (int(sDict['general']['recs']['numitns']),nl))
        f.write("STARTTEMP %s%s" % (formatAsME(sDict['other']['recs']['starttemp']),nl))
        f.write("COOLFAC %s%s" % (formatAsME(sDict['other']['recs']['coolfac']),nl))
        f.write("NUMTEMP %d%s" % (sDict['other']['recs']['numtemp'],nl))
        f.write("%sCost Threshold%s" % (nl,nl))
        f.write("COSTTHRESH %s%s" % (formatAsME(sDict['other']['recs']['costthresh']),nl))
        f.write("THRESHPEN1 %s%s" % (formatAsME(sDict['other']['recs']['threshpen1']),nl))
        f.write("THRESHPEN2 %s%s" % (formatAsME(sDict['other']['recs']['threshpen2']),nl))
        f.write("%sInput Files%s" % (nl,nl))
        f.write("INPUTDIR %s%s" % ('input',nl))
        f.write("SPECNAME %s%s" % ('spec.dat',nl))
        f.write("PUNAME %s%s" % ('pu.dat',nl))
        f.write("PUVSPRNAME %s%s" % ('puvsp.dat',nl))
        f.write("BOUNDNAME %s%s" % ('bound.dat',nl))
        f.write("MATRIXSPORDERNAME %s%s" % ('puvsp_sporder.dat',nl))
        f.write("%sSave Files%s" % (nl,nl))
        f.write("SCENNAME %s%s" % ('output',nl))
        f.write("SAVERUN %s%s" % (sDict['output']['recs']['saverun'][0],nl))
        f.write("SAVEBEST %s%s" % (sDict['output']['recs']['savebest'][0],nl))
        f.write("SAVESUMMARY %s%s" % (sDict['output']['recs']['savesum'][0],nl))
        f.write("SAVESCEN %s%s" % (sDict['output']['recs']['savescen'][0],nl))
        f.write("SAVETARGMET %s%s" % (sDict['output']['recs']['savetargmet'][0],nl))
        f.write("SAVESUMSOLN %s%s" % (sDict['output']['recs']['savesumsoln'][0],nl))
        f.write("SAVELOG %s%s" % (sDict['output']['recs']['savelog'][0],nl))
        f.write("SAVESNAPSTEPS %d%s" % (sDict['output']['recs']['savesnapsteps'],nl))
        f.write("SAVESNAPCHANGES %d%s" % (sDict['output']['recs']['savesnapchanges'],nl))
        f.write("SAVESNAPFREQUENCY %d%s" % (sDict['output']['recs']['savesnapfrequency'],nl))
        f.write("OUTPUTDIR %s%s" % ('output',nl))
        f.write("%sProgram control.%s" % (nl,nl))
        f.write("RUNMODE %s%s" % (sDict['other']['recs']['runmode'][0],nl))
        f.write("MISSLEVEL %s%s" % (formatAsME(sDict['general']['recs']['misslevel']),nl))
        f.write("ITIMPTYPE %s%s" % (sDict['other']['recs']['itimptype'][0],nl))
        f.write("HEURTYPE %d%s" % (-1,nl))
        f.write("CLUMPTYPE %d%s" % (0,nl))
        f.write("VERBOSITY %s%s" % (sDict['general']['recs']['verbosity'][0],nl))
        f.write("SAVESOLUTIONSMATRIX %s%s" % (sDict['output']['recs']['savesolutionsmatrix'][0],nl))
        f.write("%s" % nl)
        f.close()

    #
    # create bound.dat file

    def createBoundFile(self,outFName):

        # calculate line length
        def LineLength(p1,p2):
            ll = math.sqrt( (float(p1[0]) - float(p2[0]))**2 + \
                (float(p1[1]) - float(p2[1]))**2 )
            return(ll)

        # extract points from polygon
        # modified from ftools_utils.py by Carson Farmer
        def extractPoints( geom ):
            multi_geom = QgsGeometry()
            temp_geom = []
            if geom.isMultipart():
                multi_geom = geom.asMultiPolygon() #multi_geom is a multipolygon
                for i in multi_geom: #i is a polygon
                    for j in i: #j is a line
                        temp_geom.extend( j )
            else:
                multi_geom = geom.asPolygon() #multi_geom is a polygon
                for i in multi_geom: #i is a line
                    temp_geom.extend( i )
            return(temp_geom)

        # adjust boundary length
        def adjBound(inVal,id1,id2):
            if id1 == id2:
                if self.edgeMethod == 'Full Value':
                    retVal = inVal
                elif self.edgeMethod == 'Half Value':
                    retVal = inVal/2.0
                else:
                    retVal = 0.0
            else:
                retVal = inVal
            return(retVal)

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())

        #
        # pre-run setup
        #
        # track # of possible topological errors
        topoErrorCount = 0
        # change to output directory
        path,fname = os.path.split(outFName)
        os.chdir(path)
        nl = os.linesep
        # create temporary file names 
        tempsegfile = 'tempsegfile_%s.txt' % os.getpid()
        tempsortedfile = 'tempsortedfile_%s.txt' % os.getpid()
        tempadjfile = 'tempadjfile_%s.txt' % os.getpid()
        tempsortedadjfile = 'tempsortedadjfile_%s.txt' % os.getpid()
        errorlog = 'topo_error_log_%s.txt' % datetime.date.today().isoformat()
        # set tolerance setting
        tol = int(self.projectDict['settings']['boundary']['recs']['exportprecision'])
        # set action for cost differences
        cAction = self.projectDict['settings']['boundary']['recs']['diffmethod']
        # boundary type
        bType = self.projectDict['settings']['boundary']['recs']['boundmethod']
        # edge response
        self.edgeMethod = self.projectDict['settings']['boundary']['recs']['edgemethod']
        # get field indexes for puid and boundary fields
        puIdx = self.puLyr.dataProvider().fields().indexFromName('puid')
        if self.projectDict['settings']['boundary']['recs']['field'] <> '--Not Selected--':
            fldIdx = self.puLyr.dataProvider().fields().indexFromName(self.projectDict['settings']['boundary']['recs']['field'])
        else:
            fldIdx = -1
        #
        if self.debug == True:
            QgsMessageLog.logMessage('have field indexes')
        #
        # step 1 - build temporary segment file and dictionary
        #
        # notify users
        self.progressUpdateCalc(1)
        self.workerStatus.emit('Extracting line segments')
        # set values
        tsf = open(tempsegfile,'w')
        #pf = open(pFile,'w')
        inGeom = QgsGeometry()
        puFeatures = vector.features(self.puLyr)
        #QgsMessageLog.logMessage('have features')
        x = 0
        segLineCnt = 0
        # loop through features
        lastPercent = 0.0
        fCount = len(puFeatures)
        lineCount = 0
        for feat in puFeatures:
            attr = feat.attributes()
            pid = str(attr[puIdx])
            if fldIdx != -1:
                cost = str(attr[fldIdx])
            else:
                cost = '1.0'
            inGeom = feat.geometry()
            pointList = extractPoints(inGeom)
            prevPoint = 0
            for i in pointList:
                if prevPoint == 0:
                    prevPoint = i
                else:
                    # write line segment
                    segLen = LineLength([prevPoint[0],prevPoint[1]], [i[0],i[1]])
                    # make spatial key to segment file
                    if round(float(prevPoint[0]),tol) < round(float(i[0]),tol) or \
                        (round(float(prevPoint[0]),tol) == round(float(i[0]),tol) \
                        and round(float(prevPoint[1]),tol) < round(float(i[1]),tol) ):
                        skey = str(round(float(prevPoint[0]),tol)) + '|' + \
                            str(round(float(prevPoint[1]),tol)) + '|' + \
                            str(round(float(i[0]),tol)) + '|' +  \
                            str(round(float(i[1]),tol))
                    else:
                        skey = str(round(float(i[0]),tol)) + '|' +  \
                            str(round(float(i[1]),tol)) + '|' + \
                            str(round(float(prevPoint[0]),tol)) + '|' + \
                            str(round(float(prevPoint[1]),tol))
                    if segLen > 0:
                        outLine = '%s,%d,%f,%f %s' %  (skey, int(pid), float(cost), segLen, nl )
                        tsf.write(outLine)
                        lineCount += 1
                    prevPoint = i
            # progress update
            buildPercent = x / float(fCount) * 100
            # limit signals to increase processing speed
            if int(buildPercent) > lastPercent:
                self.progressStep.emit(buildPercent)
                lastPercent = buildPercent
                if self.abort:
                    break
            # increment counter for progress bar
            x += 1
        # clean up
        tsf.close()
        # sort the file
        batch_sort(tempsegfile, tempsortedfile)
        os.remove(tempsegfile)
        #
        if self.debug == True:
            QgsMessageLog.logMessage('segments extracted and sorted')
        #
        # step 2 - loop through sorted file and create adjacency file
        #    
        # notify users
        self.progressUpdateCalc(2)
        self.workerStatus.emit('Creating adjacency file')
        # 
        tsf = open(tempsortedfile,'r')
        taf = open(tempadjfile,'w')
        done = False
        pl = ''
        x = 0
        adjFileLen = 0
        lastPercent = 0.0
        while not done:
            line = tsf.readline()
            if line == '':
                done = True
            else:
                cl = line.rstrip().split(',')
            if pl != '' and pl != ['']:
                if cl != '' and pl[0] == cl[0]:
                    fCost = 1
                    if bType == 'Field':
                        bCost = 1
                        if float(pl[2])== float(cl[2]):
                            bCost = float(pl[2])
                        else:
                            if cAction == 'Maximum':
                                bCost = max([float(pl[2]),float(cl[2])])
                            elif cAction == 'Minimum':
                                bCost = min([float(pl[2]),float(cl[2])])
                            else:
                                bCost = (float(pl[2]) + float(cl[2]))/2.0
                        fCost = str(bCost)
                    elif bType == 'Measure x Field':
                        bCost = 1
                        if float(pl[2])== float(cl[2]):
                            bCost = float(pl[2])
                        else:
                            if cAction == 'Maximum':
                                bCost = max([float(pl[2]),float(cl[2])])
                            elif cAction == 'Minimum':
                                bCost = min([float(pl[2]),float(cl[2])])
                            else:
                                bCost = sum([float(pl[2]),float(cl[2])])/2.0
                        fCost = str(float(pl[3]) * bCost)
                    else:
                        fCost = str(pl[3])
                    # topology error test
                    # check for more matching lines
                    errorLines = True
                    topologyErrorFound = False
                    pids = ''
                    while errorLines:
                        line = tsf.readline()
                        chkLine = line.rstrip().split(',')
                        if chkLine != '' and chkLine[0] == pl[0]:
                            topologyErrorFound = True
                            # an error exists
                            if pids == '':
                                pids = str(pl[1]) + ',' + str(cl[1]) + ',' + str(chkLine[1])
                            else:
                                pids = pids + ',' + str(chkLine[1])
                        else:
                            errorLines = False
                    if topologyErrorFound:
                        if topoErrorCount == 0:
                            el = open(errorlog, 'w')
                            outline = 'There should never be more than 2 overlapping ' + \
                                'line segments. ' + nl + \
                                'Below are listed cases where more than 2 have ' + \
                                'been identified. ' +  nl + 'These should all be ' + \
                                'corrected before using the boundary file' + nl + \
                                '-------' + nl
                            el.write(outline)
                        outline = 'Line segments defined as %s may be topologically invalid.%s' % (str(pl[0]),nl)
                        outline = outline + 'Area ids %s appear to overlap.%s--%s' % (pids,nl,nl) 
                        el.write(outline)
                        topoErrorCount += 1
                    else:
                        # no error proceed
                        if int(pl[1]) < int(cl[1]):
                            taf.write('%020d,%020d,%s %s' % (int(pl[1]),int(cl[1]),fCost,nl))
                        else:
                            taf.write('%020d,%020d,%s %s' % (int(cl[1]),int(pl[1]),fCost,nl))
                        adjFileLen += 1
                elif type(pl) == list:
                    fCost = 1
                    if bType == 'field_value':
                        fCost = str(pl[2])
                    elif bType == 'lxf':
                        fCost = str(float(pl[3]) * float(pl[2]))
                    else:
                        fCost = str(pl[3])
                    taf.write('%020d,%020d,%s %s' % (int(pl[1]),int(pl[1]),fCost,nl))
            pl = line.rstrip().split(',')
            # progress update
            buildPercent = x / float(lineCount) * 100
            # limit signals to increase processing speed
            if int(buildPercent) > lastPercent:
                self.progressStep.emit(buildPercent)
                lastPercent = buildPercent
                if self.abort:
                    break
            # increment counter for progress bar
            x += 1
        tsf.close()
        taf.close()
        os.remove(tempsortedfile)
        # sort adjacency file
        batch_sort(tempadjfile, tempsortedadjfile)
        os.remove(tempadjfile)
        #
        if self.debug == True:
            QgsMessageLog.logMessage('adjacency file created and sorted')
        #
        # step 3 - write boundary file
        #
        # notify users
        self.progressUpdateCalc(3)
        self.workerStatus.emit('Writing boundary file')
        #
        saf = open(tempsortedadjfile,'r')
        faf = open(outFName,'w')
        faf.write("id1\tid2\tboundary%s" % nl)
        done = False
        pl = ''
        x = 0
        lastPercent = 0.0
        while not done:
            line = saf.readline()
            if line == '':
                done = True
                cl = ''
            else:
                cl = line.rstrip().split(',')
            if pl != '':
                if cl != '' and pl[0] == cl[0] and pl[1] == cl[1]:
                    if bType != 'Field':
                        # note that if field value don't sum the line segments
                        pl = [pl[0],pl[1],sum([float(pl[2]),float(cl[2])])]
                else:
                    bound = adjBound(float(pl[2]),pl[0],pl[1])
                    if bType in ('Field','Measure x Field'):
                        boundStr = str(bound)
                    else:
                        boundStr = str(round(float(bound),tol))
                    if float(bound) > 0.0:
                        faf.write('%d\t%d\t%s%s' % (int(pl[0]),int(pl[1]),boundStr,nl))
                    pl = line.rstrip().split(',')
            else:
                pl = cl
            # progress update
            buildPercent = x / float(adjFileLen) * 100
            # limit signals to increase processing speed
            if int(buildPercent) > lastPercent:
                self.progressStep.emit(buildPercent)
                lastPercent = buildPercent
                if self.abort:
                    break
            # increment counter for progress bar
            x += 1
        saf.close()
        faf.close()
        os.remove(tempsortedadjfile)
        if topoErrorCount > 0:
            el.close()
            messageText = '%d possible topological error(s) found. ' % topoErrorCount
            messageText += 'Please check error log in same directory as boundary file.'
        else:
            messageText = 'Export of bound.dat executed without problems'
        if self.debug == True:
            QgsMessageLog.logMessage('bound.dat written')
        return(topoErrorCount,messageText)

    #
    # create pu.dat file

    def createPUFile(self,outFName):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        nl = os.linesep
        #
        # Step 1 - validate status values
        #
        # get value indexes
        statField = self.projectDict['settings']['boundary']['recs']['pustatusfield']
        puIdx = self.puLyr.dataProvider().fields().indexFromName('puid')
        stIdx = self.puLyr.dataProvider().fields().indexFromName(statField)
        self.progressUpdateCalc(1)
        self.workerStatus.emit('Validating status values')
        x = 0
        puFeatures = vector.features(self.puLyr)
        fCount = len(puFeatures)
        lastPercent = 0.0
        for feat in puFeatures:
            # get status
            statusValue = int(feat.attributes()[stIdx])
            if statusValue > 3:
                return(-1,'Invalid status values')
            # progress update
            buildPercent = x / float(fCount) * 100
            # limit signals to increase processing speed
            if int(buildPercent) > lastPercent:
                self.progressStep.emit(buildPercent)
                lastPercent = buildPercent
                if self.abort:
                    break
            # increment counter
            x = x + 1
        # start creating file
        tmpf = file(outFName, 'w')
        tmpf.write("id,cost,status%s" % nl)
        #
        # Step 2 - process costs
        #
        self.progressUpdateCalc(2)
        self.workerStatus.emit('Adding costs together')
        # get cost(s)
        costRecs = self.projectDict['costs']['recs']
        costsCount = len(costRecs)
        costDict = {}
        x = 0
        lastPercent = 0.0
        qmdDir = os.path.join(self.projectDir,'qmzfiles')
        for key, value in costRecs.iteritems():
            qmiFile = os.path.join(qmdDir,key+'.qmd')
            with open(qmiFile,'r') as csvfile:
                qmiReader = csv.reader(csvfile,delimiter=',',quotechar="'")
                header = qmiReader.next()
                for row in qmiReader:
                    if int(row[0]) in costDict:
                        costDict[int(row[0])] += float(row[1])
                    else:
                        costDict[int(row[0])] = float(row[1])
            # progress update
            buildPercent = x / float(costsCount) * 100
            # limit signals to increase processing speed
            if int(buildPercent) > lastPercent:
                self.progressStep.emit(buildPercent)
                lastPercent = buildPercent
                if self.abort:
                    break
            # increment counter
            x += 1
        #
        # Step 3 - calculate pu values
        #
        self.progressUpdateCalc(3)
        self.workerStatus.emit('Creating records')
        x = 0
        outVals = []
        puFeatures = vector.features(self.puLyr)
        fCount = len(puFeatures)
        lastPercent = 0.0
        for feat in puFeatures:
            # get id
            puValue = int(feat.attributes()[puIdx])
            # get cost
            if puValue in costDict:
                costValue = float(costDict[puValue])
            else:
                costValue = 0.0
            # get status
            statusValue = int(feat.attributes()[stIdx])
            # write records
            outVals.append([puValue,costValue,statusValue])
            # progress update
            buildPercent = x / float(fCount) * 100
            # limit signals to increase processing speed
            if int(buildPercent) > lastPercent:
                self.progressStep.emit(buildPercent)
                lastPercent = buildPercent
                if self.abort:
                    break
            # increment counter
            x = x + 1
        #
        # Step 4 - sort and write file
        #
        self.progressUpdateCalc(4)
        self.workerStatus.emit('Sorting records and writing file')
        # sort
        outVals.sort()
        # write to file
        x = 0
        lastPercent = 0.0
        for row in outVals:
            outText = '%d,%f,%d%s' % (row[0],row[1],row[2],nl)
            tmpf.write(outText)
            # progress update
            buildPercent = x / float(fCount) * 100
            # limit signals to increase processing speed
            if int(buildPercent) > lastPercent:
                self.progressStep.emit(buildPercent)
                lastPercent = buildPercent
                if self.abort:
                    break
            # increment counter
            x = x + 1
        tmpf.close()
        return(0,'Export of PU file successful')

    #
    # create spec.dat file

    def createSpecFile(self,outFName):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        nl = os.linesep
        # check if features have been exported before
        featRecs = self.projectDict['features']['recs']
        if 'exportcount' in self.projectDict['features']:
            exportCount = self.projectDict['features']['exportcount']
        else:
            exportCount = 0
        # get list sorted by name to produce alphabetical spec.dat file
        nameList = []
        for key, value in featRecs.iteritems():
            nameList.append([value['name'],key])
        nameList.sort()
        # determine if export numbering exists and needs to be updated
        # this happens in two cases:
        #   1. the data has never been exported before
        #   2. puvsp.dat and puvsp_sporder.dat need to be re-exported
        # In both cases this is indicated by the need to recalculate puvsp.dat
        if 'puvsp' in self.actionDict:
            # get sorted keylist
            keyModDate = datetime.datetime.now().isoformat()
            keyList = featRecs.keys()
            x = 1
            # user notification
            self.progressStep.emit(15)
            for row in nameList:
                key = row[1]
                self.projectDict['features']['recs'][key]['exportnum'] = x
                self.projectDict['features']['recs'][key]['editdate'] = keyModDate
                x += 1
            #NOTE: the features data set date is not updated here because that suggests changes
            #      to the content
            # write to disk
            f = open(self.projectFile,'w')
            f.write(json.dumps(self.projectDict))
            f.close()
        # proceed with export - refresh key list in case numbers were updated
        featRecs = self.projectDict['features']['recs']
        keyList = featRecs.keys()
        exportList = []
        targTypes = set([])
        # user notification
        self.progressStep.emit(35)
        # get the core info and determine which target columns are needed
        for row in nameList:
            key = row[1]
            featName = featRecs[key]['name'].replace(' ','')
            temp = {'id':featRecs[key]['exportnum'],\
                'target':featRecs[key]['target'],\
                'targettype':featRecs[key]['targettype'],\
                'penalty':featRecs[key]['penalty'],\
                'name':featName}
            targTypes = targTypes.union([featRecs[key]['targettype']])
            exportList.append(temp)
        # user notification
        self.progressStep.emit(55)
        # create header
        #QgsMessageLog.logMessage(str(exportList))
        header = 'id\tprop\ttarget\ttargetocc\tspf\tname%s' % nl
        # write file
        # delay by 3 seconds in case the files are on a different machine that is not exactly
        # in sync with the desktop machine
        time.sleep(3)
        f = open(outFName,'w')
        f.write(header)
        for row in exportList:
            # create row
            rowText = '%d\t' % row['id']
            if row['targettype'] == 'Proportion':
                rowText += '%.3f\t' % row['target']
            else:
                rowText += '0.00\t'
            if row['targettype'] == 'Target':
                rowText += '%d\t' % row['target']
            else:
                rowText += '0\t'
            if row['targettype'] == 'Target Occurrrence':
                rowText += '%d\t' % row['target']
            else:
                rowText += '0\t'
            rowText += '%.3f\t%s%s' % (row['penalty'],row['name'],nl)
            f.write(rowText)
        # user notification
        self.progressStep.emit(95)
        f.close()
        
    #
    # create puvsp.dat file

    def createPUvSPFile(self,outFName):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        #
        path,fname = os.path.split(outFName)
        qmzDir = os.path.join(self.projectDir,'qmzfiles')
        spFName = os.path.join(path,'puvsp_sporder.dat')
        nl = os.linesep
        #
        # Step 1 - process costs
        #
        self.progressUpdateCalc(1)
        self.workerStatus.emit('Reading information')
        # get data in unordered fashion
        unOrdered = []
        # walk through qmd files and append to unordered list
        x = 0
        lastPercent = 0
        fCount = len(self.projectDict['features']['recs'])
        for key, value in self.projectDict['features']['recs'].iteritems():
            qmdFile = os.path.join(qmzDir,key+'.qmd')
            with open(qmdFile,'r') as csvfile:
                qmdReader = csv.reader(csvfile,delimiter=',',quotechar="'")
                header = qmdReader.next()
                for row in qmdReader:
                    unOrdered.append((value['exportnum'],row[0],row[1]))
            # progress update
            buildPercent = x / float(fCount) * 100
            # limit signals to increase processing speed
            if int(buildPercent) > lastPercent:
                self.progressStep.emit(buildPercent)
                lastPercent = buildPercent
                if self.abort:
                    break
            # increment counter
            x = x + 1
        #
        # Step 2 - process costs
        #
        self.workerStatus.emit('Sorting and writing to disk')
        self.progressStep.emit(5)
        # use numpy to sort it quickly
        cnt = len(unOrdered)
        dtype = [('species', int),('pu', int),('amount', float)]
        npArray = numpy.array(unOrdered,dtype=dtype)
        self.progressStep.emit(15)
        # create puvsp order
        sList = list(numpy.sort(npArray, order=['pu','species']))
        self.progressStep.emit(25)
        # write results
        puf = file(outFName, 'w')
        puf.write("species\tpu\tamount%s" % nl)
        x = 0
        lastPercent = 0
        for rec in sList:
            puf.write('%d\t%d\t%f%s' % (rec[0],rec[1],rec[2],nl))
            # progress update
            buildPercent = x / float(cnt) * 100 / 3
            # limit signals to increase processing speed
            if int(buildPercent) > lastPercent:
                self.progressStep.emit(buildPercent + 25)
                lastPercent = buildPercent
                if self.abort:
                    break
            # increment counter
            x = x + 1
        puf.close()
        # create puvsp_sporder order
        sList = list(numpy.sort(npArray,order=['species','pu']))
        # write results
        spf = file(spFName, 'w')
        spf.write("species\tpu\tamount%s" % nl)
        x = 0
        lastPercent = 0
        for rec in sList:
            spf.write('%d\t%d\t%f%s' % (rec[0],rec[1],rec[2],nl))
            # progress update
            buildPercent = x / float(cnt) * 100 / 3
            # limit signals to increase processing speed
            if int(buildPercent) > lastPercent:
                self.progressStep.emit(buildPercent + 60)
                lastPercent = buildPercent
                if self.abort:
                    break
            # increment counter
            x = x + 1
        spf.close()
        self.progressStep.emit(100)


    progressAll = QtCore.pyqtSignal(int)
    progressCalc = QtCore.pyqtSignal(int)
    progressStep = QtCore.pyqtSignal(int)
    workerStatus = QtCore.pyqtSignal(str)
    workerError = QtCore.pyqtSignal(Exception, basestring, str)
    workerFinished = QtCore.pyqtSignal(bool,str)
            
