"""
# -*- coding: utf-8 -*-
#
# ========================================================
# 
# Purpose: Execute Marxan Processes
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
import traceback, time, os, math, sys, inspect, numpy
import datetime, csv, shutil, subprocess, json

#
# run marxan
#
class runMarxan(QtCore.QObject):
    
    def __init__(self,projectFile,projectDir,projectDict,actionDict,mExec,rExec,*args,**kwargs):

        QtCore.QObject.__init__(self,*args,**kwargs)
        # process management
        self.calcPercentage = 0
        self.stepPercentage = 0
        self.stepCount = 1
        self.abort = False
        # passed variables
        self.projectFile = projectFile
        self.projectDir = projectDir
        self.projectDict = projectDict
        self.actionDict = actionDict
        self.mExec = mExec
        self.rExec = rExec
        # executable and paths
        self.marxanDir = os.path.join(self.projectDir,'marxan')
        self.scenName = 'output'
        self.outputDir = os.path.join(self.marxanDir,self.scenName)
        self.inputDir = os.path.join(self.marxanDir,'input')
        self.proc = None
        self.runStatus = 'i'
        # calibration variables
        self.numReps = self.projectDict['settings']['general']['recs']['numreps']
        self.successTarget = self.projectDict['settings']['general']['recs']['solutionTarget']
        self.spfStep = float(self.projectDict['settings']['general']['recs']['spfStep'])
        self.spfCalMethod = self.projectDict['settings']['general']['recs']['spfMethod']
        self.iterationList = self.projectDict['settings']['general']['recs']['iterationList']
        
        self.debug = False
        if self.debug == True:
            self.myself = lambda: inspect.stack()[1][3]
            QgsMessageLog.logMessage(self.myself())

    def formatAsME(self,inVal):
        outStr = "%.14E" % inVal
        parts = outStr.split('E')
        sign = parts[1][:1]
        exponent = "%04d" % float(parts[1][1:])
        outStr = parts[0] + 'E' +  sign + exponent
        return(outStr)

    #
    # run process
    
    def run(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
            QgsMessageLog.logMessage(str(self.actionDict))
        try:
            self.workerStatus.emit('Started')
            messageText = ''
            x = 1
            if 'run' in self.actionDict:
                self.runStatus = 'i'
                self.progressUpdateAll(x)
                x += 1
                self.stepCount = 1
                self.progressUpdateCalc(1)
                self.workerStatus.emit('Running Marxan')
                aborted,messageText = self.runMarxanOnce()
                if aborted:
                    raise Exception('run error')
            elif 'spfblm' in self.actionDict:
                self.runStatus = 'c'
                self.progressUpdateAll(x)
                x += 1
                self.stepCount = 5
                self.progressUpdateCalc(1)
                self.workerStatus.emit('Calibrating SPF Values')
                missingCount,spfText = self.calibrateSPF()
                if missingCount > 0:
                    raise Exception('spf calibration error')
                self.progressUpdateCalc(2)
                self.workerStatus.emit('Calibrating BLM Values')
                rVal, blmText = self.calibrateBLM()
                if rVal <> 0:
                    raise Exception('blm calibration error')
                messageText = spfText + blmText
            elif 'iter' in self.actionDict:
                self.runStatus = 'c'
                self.progressUpdateAll(x)
                x += 1
                self.stepCount = 1
                self.progressUpdateCalc(1)
                self.workerStatus.emit('Calibrating Iterations')
                itList = self.projectDict['settings']['general']['recs']['iterationList']
                if not itList is None and itList <> '':
                    itList = itList.split(',')
                if len(itList) > 0:
                    rVal, messageText = self.calibrateIterations(itList)
                    if rVal <> 0:
                        raise Exception('iteration calibration error')
                else:
                    messageText = 'Iteration Calibration could not be conducted. No iteration values listed.\n'
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
        try:
            self.proc.terminate()
        except:
            pass 

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
    # running Marxan
    #

    #
    # run marxan once
    
    def runMarxanOnce(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # clear old results
        temp = [os.remove(self.outputDir+'/'+i) for i in os.listdir(self.outputDir)]
        # function variables
        abort = False
        currentRun = -1
        lastRun = currentRun
        loadStart = None
        runStart = None
        runFinish = None
        status = 'load'
        startNotified = False
        pStat = None
        runPercent = 0.0
        lastPercent = 0.0
        messageText = ''

        loadStart = datetime.datetime.now()
        if self.runStatus == 'i':
            self.workerStatus.emit('Attempting to start Marxan')
        self.proc = subprocess.Popen([self.mExec],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=4096,cwd=self.marxanDir)

        time.sleep(1)
        logFName = os.path.join(self.outputDir,self.scenName+'_log.dat')
        # look for log file to see if output directory is valid
        if os.path.exists(logFName):
            time.sleep(3)
            scenFName = os.path.join(self.outputDir,self.scenName+'_sen.dat')
            # look for scenario file to check for missing files
            if os.path.exists(scenFName):
                while currentRun < self.numReps and not abort:
                    if currentRun == -1:
                        if self.runStatus == 'i':
                            self.workerStatus.emit('Marxan started successfully')
                    fileList = os.listdir(self.outputDir)
                    currentRun = sum([i.find(self.scenName+'_r')+1 for i in fileList])
                    if status == 'load' and currentRun > 0:
                        runStart = datetime.datetime.now()
                        if self.runStatus == 'i':
                            self.workerStatus.emit('Marxan running...')
                        status = 'run'
                    if status == 'load' and not startNotified:
                        if self.runStatus == 'i':
                            self.workerStatus.emit('Marxan loading and pre-processing data...')
                        startNotified = True
                        f = open(logFName,'r')
                        logLines = f.readlines()
                        f.close()
                        for line in logLines:
                            if 'species cannot meet' in line:
                                abort = True
                                if self.runStatus == 'i':
                                    self.workerStatus.emit('Some species cannot meet targets')
                                messageText = 'Some species cannot meet targets. Check log file.'
                                try:
                                    results = self.proc.terminate()
                                except:
                                    pass 
                    elif status == 'run' and lastRun <> currentRun:
                        # progress update
                        runPercent = currentRun / float(self.numReps) * 100
                        # limit signals to increase processing speed
                        if int(runPercent) > lastPercent:
                            self.progressStep.emit(runPercent)
                            lastPercent = runPercent
                            if self.abort:
                                break
                        lastRun = currentRun
                    time.sleep(1)
                    # check for status to find seg faults or other failures
                    pStat = self.proc.poll()
                    if not pStat is None:
                        abort = True
                        if self.runStatus == 'i':
                            self.workerStatus.emit('Inputs failure. Check log file.')
                        messageText = 'Inputs failure. Check log file.'
                        try:
                            results = self.proc.communicate(input='\n')
                            f = open(logFName+'.stdout','w')
                            f.write(results[0])
                            f.close()
                        except:
                            pass 
            else:
                abort = True
                results = self.proc.communicate(input='\n')
                f = open(logFName+'.stdout','w')
                f.write(results[0])
                f.close()
                self.workerStatus.emit('Load failure. Check log file.')
                messageText = 'Check log file for information to identify the source of the problem. If source of problem is not clear then check input path, parameters and files.'
        else:
            #print('no log found')
            self.proc.terminate()
            self.workerStatus.emit('System detected failure. Check output path and parameters.')
            messageText = 'System detected failure. Check output path and parameters.'
            abort = True
        # if execution was successful...
        if not abort:
            # grab screen output and commit to disk because log file is not reliable
            results = self.proc.communicate(input='\n')
            f = open(logFName+'.stdout','w')
            f.write(results[0])
            f.close()
            runFinish = datetime.datetime.now()
            hasWarnings = False
            specCount = 0
            logLines = results[0].split('\n')
            # scan output for warnings or absence of features (species)
            for line in logLines:
                lText = line.lower()
                if 'abort' in lText or 'warning' in lText:
                    hasWarnings = True
                if lText.find('species read in') > -1:
                    temp = lText.strip()
                    specCount = int(temp.split(' ')[0])
            # output summary and warnings
            messageText = 'Marxan execution completed\n'
            tt = time.strftime("%H:%M:%S", time.gmtime((runFinish-loadStart).seconds))
            lt = time.strftime("%H:%M:%S", time.gmtime((runStart-loadStart).seconds))
            rt = time.strftime("%H:%M:%S", time.gmtime((runFinish-runStart).seconds))
            messageText += 'Load time: %s\n' % lt
            messageText += 'Runs time: %s\n' % rt
            messageText += 'Total time: %s\n' % tt
            if hasWarnings:
                messageText += 'WARNING: The log file has warnings. Please check before using results!!\n'
            if specCount == 0:
                messageText += 'WARNING: Number of species registered appears to be zero. Check results and log file before using!\n'
            if hasWarnings == False and specCount > 0:
                messageText += 'No warnings or errors detected\n'

        return(abort,messageText)


    #
    # SPF Calibration Functions
    #

    #
    # calibrate spf values

    def calibrateSPF(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        modifiedFeatures = {}
        x = 0
        moreToDo = True
        self.workerStatus.emit('SPF Calibration starting...')
        self.setBLM(0)
        while moreToDo:
            abort, messageText = self.runMarxanOnce()
            self.progressStep.emit(0.0)
            if abort:
                break
            # determine if target success rate achieved
            # get results
            messageText, results = self.assessSuccess()
            # tally results
            successCount = 0
            successList = []
            failureCount = 0
            failureList = []
            missingCount = 0
            missingList = []
            if results == {}:
                moreToDo = False
            else:
                for cfk in results.keys():
                    if results[cfk][0] == -1:
                        missingCount += 1
                        missingList.append(cfk)
                    elif results[cfk][2] >= self.successTarget:
                        successCount +=1
                        successList.append(cfk)
                    else:
                        failureCount +=1
                        failureList.append(cfk)
                failureList.sort()
                successList.sort()
                if x == 0:
                    self.workerStatus.emit("Checking if feasible solutions are possible...")
                    missingCount,messageText = self.checkRepresentation()
                    if missingCount == 0:
                        self.workerStatus.emit("Feasible solutions are possible")
                self.workerStatus.emit("SPF Calibration %d of %d species ok" % (successCount,len(results)))
                if missingCount > 0:
                    moreToDo = False
                    self.workerStatus.emit('Some targets can not be met')
                elif failureCount == 0:
                    moreToDo = False
                else:
                    # adjust first spf in list and retry
                    if 'Group' in self.spfCalMethod:
                        for spec in failureList:
                            newSPF = self.adjustSPF(spec)
                            modifiedFeatures[spec] = newSPF
                    elif 'All' in self.spfCalcMethod:
                        newSPF = self.adjustSPF('--All--')
                        modifiedFeatures[spec] = newSPF
                    else:
                        newSPF = self.adjustSPF(failureList[0])
                        modifiedFeatures[spec] = newSPF
                x += 1
        if missingCount == 0:
            self.workerStatus.emit('SPF Calibration Completed Successfully')
            if len(modifiedFeatures) > 0:
                messageText = "SPF Calibration Completed.\n"
                messageText += "Some SPF modifications required to meet success threshold of %.02f\n" % self.successTarget
                messageText += "SPF Increment: %.02f using %s method.\n" % (self.spfStep, self.spfCalMethod)
                messageText += "Number of runs: %d\n" % x
                messageText += "Species with modified SPF values are:\n"
                for key,value in modifiedFeatures.iteritems():
                    messageText += 'Species: %d, New SPF: %.02f\n' % (key,value)
                    tDict = self.projectDict['features']['recs']
                    for dkey, dvalue in tDict.iteritems():
                        if dvalue['exportnum'] == key:
                            self.projectDict['features']['recs'][dkey]['penalty'] = value
                f = open(self.projectFile,'w')
                f.write(json.dumps(self.projectDict))
                f.close()
            else:
                messageText = "SPF Calibration Completed.\n"
                messageText += "No SPF modifications required to meet success threshold of %.02f\n" % self.successTarget
        else:
            self.workerStatus.emit('SPF Calibration Failed')
            messageText = "SPF Calibration completed with failures\n"
        
        return(missingCount,messageText)

    #
    # checkRepresentation - determines if feasible solutions are possible by checking
    #                       the targets againt the total available.

    def checkRepresentation(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        missingFeatures = 0
        # read the spec.dat file to get species list
        header = None
        specData = {}
        csvFile = os.path.join(self.inputDir, 'spec.dat')
        f = open(csvFile, 'r')
        reader=csv.reader(f, delimiter='\t')
        for row in reader:
            if reader.line_num == 1:
                header = row
            else:
                specData[int(row[0])] = dict(zip(header, row))
        f.close()

        # determine how much stuff is available
        # read in MarOptTotalAreas.csv
        header = None
        availData = {}
        fname = 'MarOptTotalAreas.csv'
        csvFile = os.path.join(self.marxanDir,fname)
        f = open(csvFile, 'r')
        reader=csv.reader(f, delimiter=',')
        for row in reader:
            if reader.line_num == 1:
                header = row
            else:
                availData[int(row[0])] = dict(zip(header, row))
        f.close()

        # determine what the targets were
        # read in one of the _mv files
        header = None
        resultsData = {}
        if 'CSV' in self.projectDict['settings']['output']['recs']['saverun']:
            csvFile = os.path.join(self.outputDir,'output_mv%05d.csv' % 1)
            f = open(csvFile, 'r')
            reader=csv.reader(f, delimiter=',')
        else:
            csvFile = os.path.join(self.outputDir,'output_mv%05d.dat' % 1)
            f = open(csvFile, 'r')
            reader=csv.reader(f, delimiter='\t')
        for row in reader:
            if reader.line_num == 1:
                header = row
            else:
                resultsData[int(row[0])] = dict(zip(header, row))
        f.close()
        # assess if targets are viable
        results = ''
        for row in availData:
            targetCanBeMet = True
            if float(availData[row]['totalarea']) == 0:
                targetCanBeMet = False
                available = 0
                target = float(resultsData[row]['Target'])
            else:
                available = float(availData[row]['totalarea']) - float(availData[row]['excludedarea'])
                target = float(resultsData[row]['Target'])
                propMax = available / float(availData[row]['totalarea'])
                if target > available:
                    targetCanBeMet = False
            if not targetCanBeMet:
                templine = 'Species %d (%s) can not meet ' % (row,specData[row]['name'])
                if target > 0:
                    templine = templine + 'target of %.02f. Only %.02f available or a maximum proportion of %.04f.\n' % (target,available, propMax)
                else:
                    templine = templine + 'uncalculated target. Data for this species appears to be missing.\n'
                results = results + templine
                missingFeatures += 1
        return(missingFeatures,results)

    #
    # assessSuccess - determines if proportion of runs meets target success rate

    def assessSuccess(self):
        
        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # read the spec.dat file to get species list
        messageText = ''
        header = None
        specData = {}
        csvFile = os.path.join(self.inputDir, 'spec.dat')
        f = open(csvFile, 'r')
        reader=csv.reader(f, delimiter='\t')
        for row in reader:
            if reader.line_num == 1:
                header = row
            else:
                specData[row[0]] = dict(zip(header, row))
        f.close()
        
        # create a success summary dictionary
        # structure is key: [# of successes, # of runs, % success]
        successSummary = dict(zip([int(x) for x in specData.keys()], [[0,0,0] for number in range(len(specData.keys()))]))

        header = None
        resultsData = []
        for x in range(int(self.numReps)):
            if 'CSV' in self.projectDict['settings']['output']['recs']['saverun']:
                fname = 'output_mv%05d.csv' % (x+1)
                csvFile = os.path.join(self.outputDir, fname)
                f = open(csvFile, 'r')
                reader=csv.reader(f, delimiter=',')
            else:
                fname = 'output_mv%05d.dat' % (x+1)
                csvFile = os.path.join(self.outputDir,fname)
                f = open(csvFile, 'r')
                reader=csv.reader(f, delimiter='\t')
            for row in reader:
                if reader.line_num == 1:
                    header = row
                else:
                    try:
                        if row[8] == 'yes':
                            successSummary[int(row[0])][0] += 1
                            successSummary[int(row[0])][1] += 1
                            successSummary[int(row[0])][2] = float(successSummary[int(row[0])][0])/float(successSummary[int(row[0])][1])*100
                        elif row[8] == 'no':
                            successSummary[int(row[0])][1] += 1
                            if successSummary[int(row[0])][0] > 0:
                                successSummary[int(row[0])][2] = float(successSummary[int(row[0])][0])/float(successSummary[int(row[0])][1])*100
                        else:
                            if float(row[2]) > 0.0:
                                successSummary[int(row[0])][0] = -1
                            else:
                                successSummary[int(row[0])][0] += 1
                                successSummary[int(row[0])][1] += 1
                                successSummary[int(row[0])][2] = float(successSummary[int(row[0])][0])/float(successSummary[int(row[0])][1])*100
                    except:
                        messageText = "spec.dat file doesn't match output results. Please correct before proceeding"
                        return(messageText,{})
            f.close()
                        
        return(messageText, successSummary)

    #
    # adjustSPF - adjust SPF value for a species

    def adjustSPF(self,specId):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        newSPF = 0
        messageText = ''
        header = None
        specData = {}
        csvFile = os.path.join(self.inputDir, 'spec.dat')
        f = open(csvFile, 'r')
        reader=csv.reader(f, delimiter='\t')
        for row in reader:
            if reader.line_num == 1:
                header = row
            else:
                specData[int(row[0])] = dict(zip(header, row))
        f.close()
        if specId == '--All--':
            for x in range(len(specData)):
                newSPF = float(specData[x]['spf']) + self.spfStep
                specData[x]['spf'] = newSPF
        else:
            # increment spf value
            newSPF = float(specData[specId]['spf']) + self.spfStep
            specData[specId]['spf'] = newSPF
        
        f = open(csvFile, 'w')
        writer = csv.writer(f, delimiter='\t', lineterminator=os.linesep)
        writer.writerow(header)
        rlist = sorted(specData, key=specData.get)
        rlist.sort()
        for row in rlist:
            outlist = []
            for fn in header:
                outlist.append(str(specData[row][fn]))
            writer.writerow(outlist)
        f.close()
        
        return(newSPF)


    #
    # BLM Calibration Functions
    #

    #
    # calibrate BLM

    def calibrateBLM(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        messageText = ''
        # Step 1 - get minimum cost solution    
        # a. set blm to zero
        self.workerStatus.emit('Starting BLM Calibration...')
        self.setBLM(0.0)
        # b. do run
        self.workerStatus.emit('BLM calibration first Marxan execution')
        abort, temp = self.runMarxanOnce()
        if abort:
            return()
        # c. get cost and boundary length
        rXcost, rXboundary = self.getCostBoundaryLength('cost')
        
        self.progressUpdateCalc(3)
        self.progressStep.emit(0.0)
        self.workerStatus.emit('BLM calibration second Marxan execution')
        # Step 2 - Get minimum boundary solution
        # a. set costs to zero
        self.setCostToZero()
        self.setBLM(1.0)
        # c. do run
        abort, temp = self.runMarxanOnce()
        if abort:
            return()
        # d. get cost and boundary length
        rYcost, rYboundary = self.getCostBoundaryLength('boundary')
        
        self.progressUpdateCalc(4)
        self.progressStep.emit(0.0)
        # Step 3 - Calculate "slope"
        # a. (step 1 cost - step 2 cost [actually zero]) / (step 1 boundary - step 2 boundary)
        calSlope = abs((rXcost - rYcost)/(rXboundary - rYboundary))
        # b. set blm to "slope"
        self.setBLM(calSlope)
        
        # save settings in qmz file
        self.projectDict['settings']['general']['recs']['blm'] = calSlope
        f = open(self.projectFile,'w')
        f.write(json.dumps(self.projectDict))
        f.close()
        
        self.progressUpdateCalc(5)
        self.progressStep.emit(0.0)
        self.workerStatus.emit('BLM calibration final Marxan execution')
        # Step 4 - Restore costs
        self.restoreCosts()
        abort, temp = self.runMarxanOnce()
        messageText += '\nBLM Calibration Completed\n'
        messageText += 'X: Cost %.01f, Boundary %.01f\n' % (rXcost,rXboundary)
        messageText += 'Y: Cost %.01f, Boundary %.01f\n' % (rYcost,rYboundary)
        messageText += 'New BLM: %.05f\n' % calSlope

        return(0,messageText)

    #
    # set BLM value

    def setBLM(self,newBLM):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        inputFile = os.path.join(self.marxanDir, 'input.dat')
        f = open(inputFile, 'r')
        inputData = f.read().split(os.linesep)
        f.close()
        outputData = []
        for line in inputData:
            if line.find('BLM') > -1:
                outputData.append('BLM %s' % self.formatAsME(newBLM))
            else:
                outputData.append(line)
        f = open(inputFile, 'w')
        for line in outputData:
            f.write(line+os.linesep)
        f.close()

    #
    # get cost and boundary length 

    def getCostBoundaryLength(self,param):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # read file
        header = None
        resultsData = {}
        summaryData = {}
        if 'CSV' in self.projectDict['settings']['output']['recs']['savesum']:
            csvFile = os.path.join(self.outputDir,'output_sum.csv')
            f = open(csvFile, 'r')
            reader=csv.reader(f, delimiter=',')
        else:
            csvFile = os.path.join(self.outputDir,'output_sum.dat')
            f = open(csvFile, 'r')
            reader=csv.reader(f, delimiter='\t')
        for row in reader:
            if reader.line_num == 1:
                header = row
            else:
                summaryData[row[0]] = dict(zip(header, row))
        f.close()

        # process information
        cost = None
        boundary = None
        if param == 'cost':
            for row in summaryData:
                if cost == None:
                    cost = summaryData[row]['Cost']
                    boundary = summaryData[row]['Connectivity']
                elif summaryData[row]['Cost'] < cost:
                    cost = summaryData[row]['Cost']
                    boundary = summaryData[row]['Connectivity']
        elif param == 'boundary':
            solnId = 1
            for row in summaryData:
                if boundary == None:
                    cost = summaryData[row]['Cost']
                    boundary = summaryData[row]['Connectivity']
                    solnId = int(summaryData[row]['Run_Number'])
                elif summaryData[row]['Connectivity'] < boundary:
                    cost = summaryData[row]['Cost']
                    boundary = summaryData[row]['Connectivity']
                    solnId = int(summaryData[row]['Run_Number'])
            cost = self.getRealCost(solnId)
                        
        return(float(cost),float(boundary))

    #
    # get real cost - for solutions where cost has been artificially set to zero

    def getRealCost(self,solnId):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        realCost = 0.0
        # open costs file
        costFN = os.path.join(self.inputDir,'pu.dat.old')
        cf = open(costFN,'r')
        costReader = csv.reader(cf, delimiter=',')
        # open solution file
        if 'CSV' in self.projectDict['settings']['output']['recs']['saverun']:
            fname = 'output_r%05d.csv' % solnId
            csvFile = os.path.join(self.outputDir, fname)
            f = open(csvFile, 'r')
            solnReader=csv.reader(f, delimiter=',')
        else:
            fname = 'output_r%05d.dat' % solnId
            csvFile = os.path.join(self.outputDir,fname)
            f = open(csvFile, 'r')
            solnReader=csv.reader(f, delimiter='\t')
        # convert costs to dictionary
        costData = {}
        for row in costReader:
            if costReader.line_num == 1:
                header = row
            else:
                costData[row[0]] = dict(zip(header, row))
        cf.close()
        for row in solnReader:
            if solnReader.line_num == 1:
                header = row
            else:
                if int(row[1]) == 1:
                    realCost += float(costData[row[0]]['cost'])
        f.close()
        return(realCost)
    
    #
    # restore scenario costs
    
    def restoreCosts(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # remove old file
        puFName = os.path.join(self.inputDir,'pu.dat')
        os.remove(puFName)
        # rename copy
        puFNCopy = os.path.join(self.inputDir,'pu.dat.old')
        shutil.move(puFNCopy,puFName)

    #
    # set costs to zero

    def setCostToZero(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # make a copy to restore later
        puFName = os.path.join(self.inputDir,'pu.dat')
        puFNCopy = os.path.join(self.inputDir,'pu.dat.old')
        shutil.copyfile(puFName,puFNCopy)
        # read in file
        header = None
        puData = {}
        f = open(puFName, 'r')
        # check if tab or comma delimited
        lineOne = f.readline()
        f.close()
        f = open(puFName, 'r')
        if lineOne.find('\t') > -1:
            reader=csv.reader(f, delimiter='\t')
            fD = '\t'
        else:
            reader=csv.reader(f, delimiter=',')
            fD = ','
        for row in reader:
            if reader.line_num == 1:
                header = row
            else:
                puData[row[0]] = dict(zip(header, row))
        f.close()
        # write new file
        f = open(puFName, 'w')
        writer = csv.writer(f, delimiter=fD, lineterminator=os.linesep)
        writer.writerow(header)
        for row in puData:
            outlist = []
            for fn in header:
                if fn == 'cost':
                    outlist.append(str(0.0))
                else:
                    outlist.append(str(puData[row][fn]))
            writer.writerow(outlist)
        f.close()


    #
    # Iteration Calibration Functions
    #

    #
    # adjust annealing iteration value

    def adjustIterationValue(self,newItVal):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        inputFile = os.path.join(self.marxanDir, 'input.dat')
        f = open(inputFile, 'r')
        inputData = f.read().split(os.linesep)
        f.close()
        outputData = []
        for line in inputData:
            if line.find('NUMITNS') > -1:
                outputData.append('NUMITNS %s' % int(newItVal))
            else:
                outputData.append(line)
        f = open(inputFile, 'w')
        for line in outputData:
            f.write(line+os.linesep)
        f.close()
        

    def calibrateIterations(self, itValList):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        abort = False
        x = 1
        itvLen = len(itValList)
        for iVal in itValList:
            self.workerStatus.emit('Calibrating iterations. Executing Marxan %d of %d times' % (x,itvLen))
            self.adjustIterationValue(float(iVal))
            abort, temp = self.runMarxanOnce()
            self.progressStep.emit(0.0)
            if abort:
                return(-1,'Error in running marxan')
            if 'CSV' in self.projectDict['settings']['output']['recs']['savesum']:
                ifname = os.path.join(self.outputDir,'output_sum.csv')
            else:
                ifname = os.path.join(self.outputDir,'output_sum.txt')
            ofname = os.path.join(self.marxanDir,'output_sum_i'+str(x)+'.txt')
            shutil.copy2(ifname,ofname)
            x = x + 1
        # calculate means and variances
        self.workerStatus.emit('Calibrating iterations. Comparing results.')
        results = {}
        recIt = None
        recMean = 0.0
        for x in range(len(itValList)):
            fName = os.path.join(self.marxanDir,'output_sum_i'+str(x+1)+'.txt')
            #QgsMessageLog.logMessage(fName)
            f = open(fName,'r')
            reader = csv.reader(f,delimiter=',')
            costs = []
            for row in reader:
                if reader.line_num == 1:
                    header = row
                else:
                    costs.append(float(row[2]))
            f.close()
            a = numpy.array(costs)
            a1 = a/min(a)*100
            results[itValList[x]] = [numpy.mean(a1),numpy.var(a1)]
            #QgsMessageLog.logMessage(str(itValList[x]))
            #QgsMessageLog.logMessage(str(results[itValList[x]]))
            if recIt == None:
                recIt = itValList[x]
                recMean = numpy.mean(a1)
            elif numpy.mean(a1) < recMean:
                recIt = itValList[x]
                recMean = numpy.mean(a1)
        #QgsMessageLog.logMessage(recIt)
        messageText = 'Iteration Calibration Completed\n'
        for x in itValList:
            itMean = results[x][0]
            itVar = results[x][1]
            messageText += 'With %s iterations the CDF mean is %.05f and the variance is %.05f\n' % (x, itMean, itVar)
        messageText += "The iteration is value has been set to %s\n" % recIt
        #QgsMessageLog.logMessage(messageText)
        # set value to recommended iteration
        self.projectDict['settings']['general']['recs']['numitns'] = float(recIt)
        f = open(self.projectFile,'w')
        f.write(json.dumps(self.projectDict))
        f.close()
        if recIt <> itValList[len(itValList)-1]:
            self.workerStatus.emit('Calibrating iterations. Executing Marxan once more with new iteration value.')
            self.adjustIterationValue(float(recIt))
            abort, temp = self.runMarxanOnce()
            self.progressStep.emit(0.0)
            if abort:
                return(-1,'Error in running marxan')

        return(0,messageText)

    progressAll = QtCore.pyqtSignal(int)
    progressCalc = QtCore.pyqtSignal(int)
    progressStep = QtCore.pyqtSignal(int)
    workerStatus = QtCore.pyqtSignal(str)
    workerError = QtCore.pyqtSignal(Exception, basestring, str)
    workerFinished = QtCore.pyqtSignal(bool,str)
            
