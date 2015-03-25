"""
# -*- coding: utf-8 -*-
#
# ========================================================
# 
# Purpose: Calculate content within a planning unit
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
import ogr, gdal, inspect, glob
import numpy as np


wkbTypeGroups = {
    'Point': (QGis.WKBPoint, QGis.WKBMultiPoint, QGis.WKBPoint25D, QGis.WKBMultiPoint25D,),
    'LineString': (QGis.WKBLineString, QGis.WKBMultiLineString, QGis.WKBLineString25D, QGis.WKBMultiLineString25D,),
    'Polygon': (QGis.WKBPolygon, QGis.WKBMultiPolygon, QGis.WKBPolygon25D, QGis.WKBMultiPolygon25D,),
}
for key, value in wkbTypeGroups.items():
    for const in value:
        wkbTypeGroups[const] = key

#
# function to grid layer
#

class calcContent(QtCore.QObject):

    #
    # Class Initialization
    #
    
    def __init__(self, calcList, *args, **kwargs):
        QtCore.QObject.__init__(self, *args, **kwargs)
        self.allPercentage = 0
        self.calcPercentage = 0
        self.stepPercentage = 0
        self.stepCount = 1
        self.abort = False
        self.calcList = calcList
        self.encoding = u'UTF-8'
        self.tempPrefix = 'qmz%d_' % os.getpid()
        if len(calcList) > 0:
            self.crs = calcList[0]['crs']
        self.gridTools = qmzGrid()
        #
        self.debug = False
        self.checkResults = False
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
            x = 0
            for item in self.calcList:
                self.uniqueValues = set([])
                x += 1
                self.progressUpdateAll(x)
                path,fname = os.path.split(item['puLyr'].source())
                tfn = os.path.join(path, self.tempPrefix + 'int.shp')
                tsn = os.path.join(path, self.tempPrefix + 'single.shp')
                tgn = os.path.join(path, self.tempPrefix + 'grid.shp')
                tsgn = os.path.join(path, self.tempPrefix + 'singlegrid.shp')
                trg = os.path.join(path, self.tempPrefix + 'grid.tif')
                trs = os.path.join(path, self.tempPrefix + 'srce.tif')
                # conduct calculation
                # pu field - simply export attributes
                if item['geomType'] == 'pufield':
                    self.stepCount = 2
                    self.progressUpdateCalc(1)
                    self.workerStatus.emit('Extracting records')
                    results = self.puRecordsExtract(item['puLyr'],item['idField'],item['calcField'])
                    self.progressUpdateCalc(2)
                # point source
                elif item['geomType'] == 'point':
                    self.stepCount = 3
                    self.progressUpdateCalc(1)
                    self.workerStatus.emit('Intersecting layers')
                    self.vectorIntersectLayers(item['puLyr'], item['srcLyr'], 'a', item['calcField'], tfn, item['geomType'], item['idField'])
                    if self.abort == False:
                        self.progressUpdateCalc(2)
                        self.workerStatus.emit('Counting points')
                        results = self.vectorMeasure(tfn, item['geomType'])
                        self.progressUpdateCalc(3)
                # line source
                elif item['geomType'] == 'line':
                    self.stepCount = 3
                    self.progressUpdateCalc(1)
                    self.workerStatus.emit('Intersecting layers')
                    self.vectorIntersectLayers(item['puLyr'], item['srcLyr'], 'a', item['calcField'], tfn, item['geomType'],item['idField'])
                    if self.abort == False:
                        self.progressUpdateCalc(2)
                        self.workerStatus.emit('Measuring lines')
                        results = self.vectorMeasure(tfn, item['geomType'])
                        self.progressUpdateCalc(3)
                # area source
                elif item['geomType'] == 'area':
                    self.stepCount = 3
                    # use raster estimation
                    if item['useRaster'] == True:
                        self.progressUpdateCalc(1)
                        self.workerStatus.emit('Creating temporary files')
                        self.rasterCreateMatchingPair(trg,trs,item['calcField'],item['puLyr'],item['srcLyr'],item['idField'],item['pixelSize'],item['calcType'])
                        if self.abort == False:
                            self.progressUpdateCalc(2)
                            self.workerStatus.emit('Estimating overlaps')
                            results = self.rasterMeasure(trg,trs,True,item['srcNDValue'],item['pixelSize'])
                            self.progressUpdateCalc(3)
                    # user vector methods
                    else:
                        self.stepCount = 6
                        self.progressUpdateCalc(1)
                        self.workerStatus.emit('Converting multipolyons to singles')
                        tempLyr = self.vectorMultiToSingle(item['srcLyr'],item['calcField'],tsn)
                        if self.abort == False:
                            self.progressUpdateCalc(2)
                            self.workerStatus.emit('Creating temporary grid')
                            grdLyr = self.gridCreate(tgn,item['srcLyr'])
                        if self.abort == False:
                            self.progressUpdateCalc(3)
                            self.workerStatus.emit('Intersecting single with grid')
                            self.vectorIntersectLayers(tempLyr, grdLyr, 'b', 'calcField', tsgn, item['geomType'],item['idField'])
                            sgLyr = QgsVectorLayer(tsgn, 'tempsinglegrid', 'ogr')
                        self.fileRemoveTemp(tsn)
                        self.fileRemoveTemp(tgn)
                        if self.abort == False:
                            self.progressUpdateCalc(4)
                            self.workerStatus.emit('Intersecting layers')
                            self.vectorIntersectLayers(sgLyr, item['puLyr'], 'b', 'calcField', tfn, item['geomType'],item['idField'])
                        self.fileRemoveTemp(tsgn)
                        if self.abort == False:
                            self.progressUpdateCalc(5)
                            self.workerStatus.emit('Measuring polygons')
                            results = self.vectorMeasure(tfn, item['geomType'])
                            self.progressUpdateCalc(6)
                # raster source
                elif item['geomType'] == 'raster':
                    self.stepCount = 3
                    self.progressUpdateCalc(1)
                    self.workerStatus.emit('Creating temporary file')
                    self.rasterCreateMatching(trg,item['puLyr'],item['srcLyr'],item['idField'])
                    if self.abort == False:
                        self.progressUpdateCalc(2)
                        self.workerStatus.emit('Estimating overlap')
                        results = self.rasterMeasure(trg,item['srcLyr'].source(),False,item['srcNDValue'],item['pixelSize'])
                        self.progressUpdateCalc(3)
                # write results
                self.fileRemoveTemp(tfn)
                if self.abort == False:
                    # debug
                    # processes above should have created a dictionary structured as follows
                    # {puid : {calcField or pixel value : [count, sum, max, min], cpv2 ... n : [count,sum,...]}, puid2 ... n}
                    # OR
                    # {puid : {0.0 : [count, sum, max, min]}, puid2 ... n}
                    # this check prints a file to ensure that this is what was written
                    if self.checkResults == True:
                        #write results to file to check if processing correctly
                        f = open('qmzRDict.txt','w')
                        f.write(item['geomType']+'\n')
                        f.write(fname + '\n')
                        f.write(str(results))
                        f.close()
                    if item['destType'] == 'file':
                        self.workerStatus.emit('Writing results to file')
                        # delete old files
                        for fName in glob.glob(item['destName'] + '*'):
                            os.remove(fName)
                        if item['singleField'] == True:
                            self.fileSingleOutput(results,item['puLyr'],item['destName'],item['calcType'],item['intersectOp'],item['idField'])
                        else:
                            self.fileMultiOutput(results,item['puLyr'],item['destName'],item['key'],item['calcType'],item['intersectOp'])
                        self.fileWriteQMIFile(item)
                    else:
                        self.workerStatus.emit('Updating PU Layer')
                        if item['singleField'] == True:
                            self.puLayerSingleUpdate(results,item['puLyr'],item['idField'],item['destName'],item['calcType'],item['intersectOp'])
                        else:
                            self.puLayerMultiUpdate(results,item['puLyr'],item['idField'],item['destName'],item['calcType'],item['intersectOp'],item['geomType'])
            if self.abort == False:
                self.workerStatus.emit('Completed')
            else:
                self.workerStatus.emit('Cancelled')
            self.workerFinished.emit(True)
        except Exception, e:
            import traceback
            if messageText == '':
                messageText == 'An error occurred'
            self.workerError.emit(e, traceback.format_exc(),messageText)
            self.workerFinished.emit(False)
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
    
    def progressUpdateCalc(self, stepNumber):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.calcPercentage = stepNumber / float(self.stepCount) * 100
        self.progressCalc.emit(self.calcPercentage)

    #
    # update all process

    def progressUpdateAll(self, calcNumber):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.allPercentage = calcNumber / float(len(self.calcList)) * 100
        self.progressAll.emit(self.allPercentage)


    #
    # Temporary File Management
    #

    #
    # remove temporary files

    def fileRemoveTemp(self,fName):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if os.path.exists(fName):
            QgsVectorFileWriter.deleteShapeFile(fName)
            rFName,ext = os.path.splitext(fName)
            lfn = rFName + '.cpg'
            if os.path.exists(lfn):
                os.remove(lfn)

    #
    # Spatial Processing
    #

    #
    # intersect vectors
    # modified code from ftools Intersection by Victor Olaya

    def vectorIntersectLayers(self, aLayer, bLayer, idLayer, calcFieldName, tfn, geomType, idField):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # create fields and variables to hold information
        aLayer.setSelectedFeatures([])
        bLayer.setSelectedFeatures([])
        fields = QgsFields()
        fields.append(QgsField(idField, QtCore.QVariant.Int))
        fields.append(QgsField('calcField', QtCore.QVariant.Double))
        if geomType == 'point':
            writer = QgsVectorFileWriter(tfn, self.encoding, fields, QGis.WKBPoint, self.crs, 'ESRI Shapefile')
        elif geomType == 'line':
            writer = QgsVectorFileWriter(tfn, self.encoding, fields, QGis.WKBLineString, self.crs, 'ESRI Shapefile')
        else:
            writer = QgsVectorFileWriter(tfn, self.encoding, fields, QGis.WKBPolygon, self.crs, 'ESRI Shapefile')
        # open temporary layer
        aFeat = QgsFeature()
        bFeat = QgsFeature()
        outFeat = QgsFeature()
        aIndex = vector.spatialindex(aLayer)
        nElement = 0
        bFeatures = vector.features(bLayer)
        nFeat = len(bFeatures)
        # look for fields in input layers
        idIdx = -1
        calcIdx = -1
        if idLayer == 'a':
            idIdx = aLayer.dataProvider().fields().indexFromName(idField)
            if calcFieldName <> '':
                calcIdx = bLayer.dataProvider().fields().indexFromName(calcFieldName)
        else:
            idIdx = bLayer.dataProvider().fields().indexFromName(idField)
            if calcFieldName <> '':
                calcIdx = aLayer.dataProvider().fields().indexFromName(calcFieldName)
        lastPercent = 0.0
        self.progressStep.emit(lastPercent)
        idVal = 0
        calcVal = 0.0
        for bFeat in bFeatures:
            nElement += 1
            buildPercent = nElement / float(nFeat) * 100
            if int(buildPercent) > lastPercent and buildPercent <= 99.0:
                self.progressStep.emit(buildPercent)
                lastPercent = buildPercent           
            bGeom = QgsGeometry(bFeat.geometry())
            if idLayer == 'b':
                idVal = bFeat.attributes()[idIdx]
            if idLayer == 'a' and calcIdx <> -1:
                calcVal = bFeat.attributes()[calcIdx]
            intersects = aIndex.intersects(bGeom.boundingBox())
            for i in intersects:
                request = QgsFeatureRequest().setFilterFid(i)
                aFeat = aLayer.getFeatures(request).next()
                tmpGeom = QgsGeometry(aFeat.geometry())
                try:
                    if bGeom.intersects(tmpGeom):
                        if idLayer == 'a':
                            idVal = aFeat.attributes()[idIdx]
                        if idLayer == 'b' and calcIdx <> -1:
                            calcVal = aFeat.attributes()[calcIdx]
                        intGeom = QgsGeometry(bGeom.intersection(tmpGeom))
                        if intGeom.wkbType() == QGis.WKBUnknown:
                            intCom = bGeom.combine(tmpGeom)
                            intSym = bGeom.symDifference(tmpGeom)
                            intGeom = QgsGeometry(intCom.difference(intSym))
                        try:
                            if intGeom.wkbType() in wkbTypeGroups[wkbTypeGroups[intGeom.wkbType()]]:
                                outFeat.setGeometry(intGeom)
                                attrs = [idVal,calcVal]
                                outFeat.setAttributes(attrs)
                                writer.addFeature(outFeat)
                        except:
                            continue
                except:
                    break
                if self.abort == True:
                    break
            if self.abort == True:
                break
        # close writer
        writer = None

    #
    # multi to single
    # this is done to improve vector intersection performance
    # modified from ftools MutlipartToSingleparts by Victor Olaya

    def vectorMultiToSingle(self,srcLyr,calcField,tsn):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # create fields
        fields = QgsFields()
        fields.append(QgsField("id", QtCore.QVariant.Int))
        fields.append(QgsField('calcField', QtCore.QVariant.Double))
        calcIdx = srcLyr.dataProvider().fields().indexFromName(calcField)
        # create writer
        writer = QgsVectorFileWriter(tsn, self.encoding, fields, QGis.WKBPolygon, self.crs, 'ESRI Shapefile')
        # define variables to hold features
        outFeat = QgsFeature()
        inGeom = QgsGeometry()
        # prepare to loop through features
        current = 0
        features = vector.features(srcLyr)
        total = len(features)
        lastPercent = 0.0
        self.progressStep.emit(lastPercent)
        for f in features:
            # get geometry
            inGeom = f.geometry()
            # convert to single
            geometries = self.vectorFeatureMultiToSingle(inGeom)
            total = total + len(geometries) - 1
            outFeat.setAttributes([current,f.attributes()[calcIdx]])
            # add feature for each part
            for g in geometries:
                # index and report progress
                current += 1
                buildPercent = float(current) / float(total) * 100
                if int(buildPercent) > lastPercent and buildPercent <= 99.0:
                    self.progressStep.emit(buildPercent)
                    lastPercent = buildPercent
                    if self.abort:
                        break 
                outFeat.setGeometry(g)
                writer.addFeature(outFeat)
            if self.abort == True:
                break
        # close file
        del writer
        tempLyr = QgsVectorLayer(tsn, 'tempsingle', 'ogr')
        return(tempLyr)

    #
    # convert multi geometries to single geometries
    # modified from ftools MutlipartToSingleparts by Victor Olaya

    def vectorFeatureMultiToSingle(self,geom):
        
        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        multiGeom = QgsGeometry()
        geometries = []
        if geom.type() == QGis.Point:
            if geom.isMultipart():
                multiGeom = geom.asMultiPoint()
                for i in multiGeom:
                    geometries.append(QgsGeometry().fromPoint(i))
            else:
                geometries.append(geom)
        elif geom.type() == QGis.Line:
            if geom.isMultipart():
                multiGeom = geom.asMultiPolyline()
                for i in multiGeom:
                    geometries.append(QgsGeometry().fromPolyline(i))
            else:
                geometries.append(geom)
        elif geom.type() == QGis.Polygon:
            if geom.isMultipart():
                multiGeom = geom.asMultiPolygon()
                for i in multiGeom:
                    geometries.append(QgsGeometry().fromPolygon(i))
            else:
                geometries.append(geom)
        return geometries

    #
    # build a grid file to clip vector into 100 parts to
    # improve vector intersection performance
        
    def gridCreate(self, tgn, srcLyr):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # place squares from top left corner
        bbox = srcLyr.extent()
        xMin = bbox.xMinimum()
        yMax = bbox.yMaximum()
        xMax = bbox.xMaximum()
        yMin = bbox.yMinimum()
        sideLen = min((xMax -xMin) / 10.0, (yMax - yMin) / 10.0)
        fields = QgsFields()
        fields.append(QgsField("id", QtCore.QVariant.Int))
        check = QtCore.QFile(tgn)
        if check.exists():
            if not QgsVectorFileWriter.deleteShapeFile(tgn):
                return
        writer = QgsVectorFileWriter(tgn, self.encoding, fields, QGis.WKBPolygon, self.crs, 'ESRI Shapefile')
        outFeat = QgsFeature()
        outFeat.setFields(fields)
        outGeom = QgsGeometry()
        idVar = 1
        cellCount = self.gridTools.calcSquareCount(sideLen,xMin,xMax,yMin,yMax)
        y = yMax
        lastPercent = 0.0
        self.progressStep.emit(lastPercent)
        while y >= yMin and self.abort == False:
            x = xMin
            while x < xMax and self.abort == False:
                polygon = self.gridTools.createSquare(x, y, sideLen)
                outFeat.setGeometry(outGeom.fromPolygon(polygon))
                outFeat.setAttributes([idVar])
                writer.addFeature(outFeat)
                idVar = idVar + 1
                x = x + sideLen
            y = y - sideLen
            buildPercent = float(idVar) / float(cellCount) * 100
            if int(buildPercent) > lastPercent and buildPercent <= 99.0:
                self.progressStep.emit(buildPercent)
                lastPercent = buildPercent
                if self.abort:
                    break 
        # close writer
        del writer
        tempLyr = QgsVectorLayer(tgn, 'tempsingle', 'ogr')
        return(tempLyr) 

    #
    # create matching rasters

    def rasterCreateMatchingPair(self,trg,trs,calcField,puLyr,srcLyr,idField,pixelSize,calcType):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.progressStep.emit(0.0)
        # this sleep is inserted here to ensure that the interface refreshes
        # before the gdal processes start which can stall the user interface.
        time.sleep(1)
        # get parameters
        pixelSize = pixelSize
        bbox = srcLyr.extent()
        xMin = bbox.xMinimum()
        yMax = bbox.yMaximum()
        xMax = bbox.xMaximum()
        yMin = bbox.yMinimum()
        xRecs = round((xMax - xMin) / pixelSize)
        yRecs = round((yMax - yMin) / pixelSize)
        # increase pixel size to manage cases with very large arrays
        # making pixel size larger than this leaves too many unneeded planning units
        aSize = xRecs * yRecs
        magRef = float(aSize) / 10000000.0
        if magRef > 10:
            pixelSize = pixelSize * 2
            xRecs = round((xMax - xMin) / pixelSize)
            yRecs = round((yMax - yMin) / pixelSize)
        self.progressStep.emit(5.0)
        # set transform array
        #adfGeoTransform[0] /* top left x */
        #adfGeoTransform[1] /* w-e pixel resolution */
        #adfGeoTransform[2] /* 0 */
        #adfGeoTransform[3] /* top left y */
        #adfGeoTransform[4] /* 0 */
        #adfGeoTransform[5] /* n-s pixel resolution (negative value) */
        transformArray = [xMin,pixelSize,0,yMax,0,-pixelSize]
        self.progressStep.emit(10.0)
        # transform grid first
        self.progressStep.emit(15.0)
        self.vectorToRaster(puLyr.source(),trg,xRecs,yRecs,transformArray,idField)
        self.progressStep.emit(55.0)
        # transform input layer second
        self.progressStep.emit(65.0)
        if calcType == 'calculate':
            self.vectorToRaster(srcLyr.source(),trs,xRecs,yRecs,transformArray,calcField)
        else:
            self.vectorToRaster(srcLyr.source(),trs,xRecs,yRecs,transformArray,None)
        self.progressStep.emit(95.0)

    #
    # create matching raster

    def rasterCreateMatching(self,trg,puLyr,srcLyr,idField):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.progressStep.emit(0.0)
        # this sleep is inserted here to ensure that the interface refreshes
        # before the gdal processes start which can stall the user interface.
        time.sleep(1)
        # get parameters
        pixelSize = min(srcLyr.rasterUnitsPerPixelX(),srcLyr.rasterUnitsPerPixelY())
        bbox = srcLyr.extent()
        xMin = bbox.xMinimum()
        yMax = bbox.yMaximum()
        xMax = bbox.xMaximum()
        yMin = bbox.yMinimum()
        xRecs = round((xMax - xMin) / pixelSize)
        yRecs = round((yMax - yMin) / pixelSize)
        # progress notification
        self.progressStep.emit(15.0)
        transformArray = [xMin,pixelSize,0,yMax,0,-pixelSize]
        self.progressStep.emit(25.0)
        # transform grid 
        self.progressStep.emit(35.0)
        self.vectorToRaster(puLyr.source(),trg,xRecs,yRecs,transformArray,idField)
        self.progressStep.emit(95.0)
        
    #
    # convert to raster
    
    def vectorToRaster(self,inFName,outFName,xRecs,yRecs,transformArray,keyField=None):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # Open the data source and read in the extent
        sDs = ogr.Open(inFName)
        sLyr = sDs.GetLayer()
        gtDriver = gdal.GetDriverByName('GTiff')
        tDs = gtDriver.Create(outFName, int(xRecs), int(yRecs), 1, gdal.GDT_Int32)
        tDs.SetGeoTransform(transformArray)
        # set options
        if keyField == None:
            #options = ['ALL_TOUCHED=True']
            options = []
        else:
            #options = ['ATTRIBUTE=%s' % keyField,'ALL_TOUCHED=TRUE']
            options = ['ATTRIBUTE=%s' % keyField]
        # rasterize
        #QgsMessageLog.logMessage('rasterize')
        gdal.RasterizeLayer(tDs, [1], sLyr, None, None, [1], options)
        sLyr = None
        sDs = None
        tDs = None


    #
    # Measuring of Raw Values
    #

    #
    # extract records from pu field
    
    def puRecordsExtract(self,puLyr,idField,calcField):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if puLyr.isValid():
            fields  = puLyr.dataProvider().fields()
            puidIdx = fields.indexFromName(idField)
            calcIdx = fields.indexFromName(calcField)
            total = puLyr.featureCount()
            current = 0
            lastPercent = 0.0
            self.progressStep.emit(lastPercent)
            featIter = puLyr.getFeatures(QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry))
            results = {}
            for feat in featIter:
                attr = feat.attributes()
                if attr[calcIdx] > 0:
                    if attr[puidIdx] in results:
                        # record exists for this puid
                        if attr[calcIdx] in results[attr[puidIdx]]:
                            # record exits for this puid and this unique value of calcfield value
                            results[attr[puidIdx]][attr[calcIdx]][0] += 1
                            results[attr[puidIdx]][attr[calcIdx]][1] += attr[calcIdx]
                            if attr[calcIdx] > results[attr[puidIdx]][attr[calcIdx]][2]:
                                results[attr[puidIdx]][attr[calcIdx]][2] = attr[calcIdx]
                            if attr[calcIdx] < results[attr[puidIdx]][attr[calcIdx]][3]:
                                results[attr[puidIdx]][attr[calcIdx]][3] = attr[calcIdx]
                        else:
                            # create this unique value of calcfield value within existing puid record
                            results[attr[puidIdx]][attr[calcIdx]] = [1,attr[calcIdx],attr[calcIdx],attr[calcIdx]]
                            if not attr[calcIdx] in self.uniqueValues:
                                self.uniqueValues.add(attr[calcIdx])
                    else:
                        # create record for this puid
                        # store array of [count, sum, max, min] for each calcField or unique value
                        results[attr[puidIdx]] = {attr[calcIdx] : [1,attr[calcIdx],attr[calcIdx],attr[calcIdx]]}
                        if not attr[calcIdx] in self.uniqueValues:
                            self.uniqueValues.add(attr[calcIdx])
                current += 1
                buildPercent = float(current) / float(total) * 100
                # limit signals to increase processing speed
                if int(buildPercent) > lastPercent+2 and buildPercent <= 99.0:
                    self.progressStep.emit(buildPercent)
                    lastPercent = buildPercent
                    if self.abort:
                        break 
        # close layer
        tempLayer = None
        # return results
        return(results)

    #
    # measure vector features

    def vectorMeasure(self,tfn,geomType):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # open layer
        tempLayer = QgsVectorLayer(tfn, 'tempint', 'ogr')
        # confirm it is valid
        if tempLayer.isValid():
            fields = tempLayer.dataProvider().fields()
            total = tempLayer.featureCount()
            current = 0
            lastPercent = 0.0
            self.progressStep.emit(lastPercent)
            if geomType == 'point':
                featIter = tempLayer.getFeatures(QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry))
            else:
                featIter = tempLayer.getFeatures()
            results = {}
            # produce multi dimensional dictionary of puids, calcFieldsValues and counts
            # attr[0] == puid
            # attr[1] === calcField
            measure = 1
            for feat in featIter:
                attr = feat.attributes()
                # determine measure (points are 1)
                if geomType == 'area':
                    measure = feat.geometry().area()
                elif geomType == 'line':
                    measure = feat.geometry().length()
                if attr[0] in results:
                    # record exists for this puid
                    if attr[1] in results[attr[0]]:
                        # record exits for this puid and this unique value of calcfield value
                        results[attr[0]][attr[1]][0] += 1
                        results[attr[0]][attr[1]][1] += measure
                        if measure > results[attr[0]][attr[1]][2]:
                            results[attr[0]][attr[1]][2] = measure
                        if measure < results[attr[0]][attr[1]][3]:
                            results[attr[0]][attr[1]][3] = measure
                    else:
                        # create this unique value of calcfield value within existing puid record
                        results[attr[0]][attr[1]] = [1,measure,measure,measure]
                        if not attr[1] in self.uniqueValues:
                            self.uniqueValues.add(attr[1])
                else:
                    # create record for this puid
                    # store array of [count, sum, max, min] for each calcField or unique value
                    results[attr[0]] = {attr[1] : [1,measure,measure,measure]}
                    if not attr[1] in self.uniqueValues:
                        self.uniqueValues.add(attr[1])
                current += 1
                buildPercent = float(current) / float(total) * 100
                # limit signals to increase processing speed
                if int(buildPercent) > lastPercent and buildPercent <= 99.0:
                    self.progressStep.emit(buildPercent)
                    lastPercent = buildPercent
                    if self.abort:
                        break 
        # close layer
        tempLayer = None
        # return results
        return(results)

    #
    # estimate raster overlaps

    def rasterMeasure(self,trg,trs,delSource,srcNDValue,pixelSize):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # create arrays for each raster source
        try:
            # read grid
            gds = gdal.Open(trg)
            gdBand = gds.GetRasterBand(1)
            # read content layer
            cds = gdal.Open(trs)
            cdBand = cds.GetRasterBand(1)
            ndValue = cdBand.GetNoDataValue()
            nRows = gds.RasterYSize
            nCols = gds.RasterXSize
            # get raster attribute table
            results = {}
            lastPercent = 0.0
            self.progressStep.emit(lastPercent)
            size = pixelSize*pixelSize
            for rowIdx in range(nRows):
                gaf = np.array(gdBand.ReadAsArray(0,rowIdx,nCols,1)).flatten()
                caf = np.array(cdBand.ReadAsArray(0,rowIdx,nCols,1)).flatten()
                puidList = np.unique(gaf).tolist()
                if 0 in puidList:
                    puidList.remove(0)
                for puid in puidList:
                    masked = np.ma.MaskedArray(caf, mask=np.logical_or(caf==ndValue,gaf<>puid))
                    pixelList = filter(None,masked.tolist())
                    puDict = dict(Counter(pixelList))
                    if len(puDict) > 0:
                        newDict = {}
                        for key, value in puDict.iteritems():
                            newDict[key] = [value, value * size, value * size, value * size]
                        if puid in results:
                            for key,value in newDict.iteritems():
                                if key in results[puid]:
                                    results[puid][key][0] += value[0]
                                    results[puid][key][1] += value[1]
                                    results[puid][key][2] += value[2]
                                    results[puid][key][3] += value[3]
                                else:
                                    results[puid][key] = value
                                    self.uniqueValues.add(key)
                        else:
                            results[puid] = newDict
                            self.uniqueValues = self.uniqueValues.union(newDict.keys())
                buildPercent = float(rowIdx) / float(nRows) * 100
                # limit signals to increase processing speed
                if int(buildPercent) > lastPercent:
                    self.progressStep.emit(buildPercent)
                    lastPercent = buildPercent
                    if self.abort:
                        break
        except:
            self.workerStatus.emit('Out of memory')
            self.abort = True
        os.remove(trg)
        if delSource == True:
            os.remove(trs)  
        del gaf
        del caf
        return(results)


    #
    # Summarize Raw Measures and Performing Calculations
    #

    #
    # summarize single values for a pu

    def valuesSummarizeSingle(self,puResults,calcType,intersectOp):

        #
        # Note that puResults looks like either
        # this:
        # {calcField or pixel value : [count, sum, max, min], cpv2 ... n : [count,sum,...]}
        # or this:
        # {0.0 : [count, sum, max, min]}
        # puResults[key][0] == count
        # puResults[key][1] == sum
        # puResults[key][2] == max
        # puResults[key][3] == min
        
        #if self.debug == True:
        #    QgsMessageLog.logMessage(self.myself())
        finalValue = None
        cnt = 0
        if calcType == 'measure':
            if intersectOp == 'sum':
                for key in puResults:
                    if finalValue == None:
                        finalValue = puResults[key][1]
                    else:
                        finalValue += puResults[key][1]
            elif intersectOp == 'mean':
                for key in puResults:
                    if finalValue == None:
                        cnt = puResults[key][0]
                        finalValue = puResults[key][1]
                    else:
                        cnt += puResults[key][0]
                        finalValue += puResults[key][1]
                finalValue = float(finalValue) / cnt
            elif intersectOp == 'max':
                for key in puResults:
                    if finalValue == None:
                        finalValue = puResults[key][2]
                    else:
                        finalValue += puResults[key][2]
            elif intersectOp == 'min':
                for key in puResults:
                    if finalValue == None:
                        finalValue = puResults[key][3]
                    else:
                        finalValue += puResults[key][3]
            elif intersectOp == 'count':
                for key in puResults:
                    if finalValue == None:
                        finalValue = puResults[key][0]
                    else:
                        finalValue += puResults[key][0]
            elif intersectOp == 'presence':
                for key in puResults:
                    if finalValue == None:
                        finalValue = 1
        elif calcType == 'value':
            if intersectOp == 'sum':
                for key in puResults:
                    if finalValue == None:
                        finalValue = float(key)
                    else:
                        finalValue += float(key)
            elif intersectOp == 'mean':
                for key in puResults:
                    if finalValue == None:
                        cnt = puResults[key][0]
                        finalValue = float(key)
                    else:
                        cnt += puResults[key][0]
                        finalValue += float(key)
                finalValue = float(finalValue) / cnt
            elif intersectOp == 'max':
                for key in puResults:
                    if finalValue == None:
                        finalValue = float(key)
                    else:
                        if float(key) > finalValue:
                            finalValue = float(key)
            elif intersectOp == 'min':
                for key in puResults:
                    if finalValue == None:
                        finalValue = float(key)
                    else:
                        if float(key) < finalValue:
                            finalValue = float(key)
            elif intersectOp == 'count':
                for key in puResults:
                    if finalValue == None:
                        finalValue = 1
                    else:
                        finalValue += 1
            # 2014-12-29 - TSW
            # this last option can not be set in the user interface
            # because it doesn't make sense at this time. It is just commented
            # out in case at some point in the future a case can be made for its
            # inclusion
            #elif intersectOp == 'presence':
                #for key in puResults:
                    #if finalValue == None:
                        #finalValue = 1
        else:
            # measure x value 
            if intersectOp == 'sum':
                for key in puResults:
                    if finalValue == None:
                        finalValue = puResults[key][1] * float(key)
                    else:
                        finalValue += puResults[key][1] * float(key)
            elif intersectOp == 'mean':
                for key in puResults:
                    if finalValue == None:
                        cnt = puResults[key][0]
                        finalValue = puResults[key][1] * float(key)
                    else:
                        cnt += puResults[key][0]
                        finalValue += puResults[key][1] * float(key)
                finalValue = float(finalValue) / cnt
            elif intersectOp == 'max':
                for key in puResults:
                    if finalValue == None:
                        finalValue = puResults[key][2] * float(key)
                    else:
                        if puResults[key][2] * float(key) > finalValue:
                            finalValue = puResults[key][2] * float(key)
            elif intersectOp == 'min':
                for key in puResults:
                    if finalValue == None:
                        finalValue = puResults[key][3] * float(key)
                    else:
                        if puResults[key][3] * float(key) < finalValue:
                            finalValue = puResults[key][3] * float(key)
            # 2014-12-29 - TSW
            # the last options can not be set in the user interface
            # because they doesn't make sense at this time. They are just commented
            # out in case at some point in the future a case can be made for their
            # inclusion
            #elif intersectOp == 'count':
                #for key in puResults:
                    #if finalValue == None:
                        #finalValue = 1
                    #else:
                        #finalValue += 1
            #elif intersectOp == 'presence':
                #for key in puResults:
                    #if finalValue == None:
                        #finalValue = 1
            
        return(finalValue)


    def valuesSummarizeMulti(self,puResults,calcType,intersectOp):
        
        #
        # Note that puResults looks like either
        # this:
        # {calcField or pixel value : [count, sum, max, min], cpv2 ... n : [count,sum,...]}
        # or this:
        # {0.0 : [count, sum, max, min]}
        # puResults[key][0] == count
        # puResults[key][1] == sum
        # puResults[key][2] == max
        # puResults[key][3] == min

        #if self.debug == True:
        #    QgsMessageLog.logMessage(self.myself())
        finalValues = {}
        cnts = {}
        if calcType == 'value':
            # pixel or field value
            if intersectOp == 'count':
                for key in puResults:
                    if key in finalValues:
                        finalValues[key] += 1
                    else:
                        finalValues[key] = 1
            elif intersectOp == 'presence':
                for key in puResults:
                    if not key in finalValues:
                        finalValues[key] = 1
        else:
            # measure per pixel or field value
            if intersectOp == 'sum':
                for key in puResults:
                    if key in finalValues:
                        finalValues[key] += puResults[key][1]
                    else:
                        finalValues[key] = puResults[key][1]
            elif intersectOp == 'mean':
                for key in puResults:
                    if key in finalValues:
                        finalValues[key] += puResults[key][1] 
                        cnts[key] += puResults[key][0]
                    else:
                        finalValues[key] = puResults[key][1]
                        cnts[key] = puResults[key][0]
                for key in finalValues:
                    finalValues[key] = float(finalValues[key]) / cnts[key]
            elif intersectOp == 'max':
                for key in puResults:
                    if key in finalValues:
                        if puResults[key][2] > finalValues[key]:
                            finalValues[key] = puResults[key][2] 
                    else:
                        finalValues[key] = puResults[key][2]
            elif intersectOp == 'min':
                for key in puResults:
                    if key in finalValues:
                        if puResults[key][2] < finalValues[key]:
                            finalValues[key] = puResults[key][2]
                    else:
                        finalValues[key] = puResults[key][2]
            elif intersectOp == 'count':
                for key in puResults:
                    if key in finalValues:
                        finalValues[key] += puResults[key][0]
                    else:
                        finalValues[key] = puResults[key][0]
                        
        return(finalValues)

    #
    # create attribute map for pu layer

    def valuesCreateAttributeMap(self,puResults,idxDict):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # summarize by key
        results = {}
        if puResults == None:
            # nothing found so set all to zero
            for dKey, dValue in idxDict.iteritems():
                results[dValue] = 0.0
        else:
            for dKey, dValue in idxDict.iteritems():
                if dKey in puResults:
                    results[dValue] = puResults[dKey]
                else:
                    results[dValue] = 0.0
        return(results)


    #
    # Writing Results to Disk
    #

    #
    # single field update pu layer

    def puLayerSingleUpdate(self,results,puLyr,idField,destName,calcType,intersectOp):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # confirm it is valid
        if puLyr.isValid():
            fields = puLyr.dataProvider().fields()
            puidIdx = fields.indexFromName(idField)
            destIdx = fields.indexFromName(destName)
            if destIdx == -1:
                try:
                    res = puLyr.dataProvider().addAttributes([QgsField(destName, QtCore.QVariant.Double, "real", 19, 10)])
                    puLyr.updateFields()
                    fields = puLyr.dataProvider().fields()
                    destIdx = fields.indexFromName(destName)
                except:
                    pass 
                if destIdx == -1:
                    self.abort = True
                    return
            total = puLyr.featureCount()
            current = 1
            lastPercent = 0.0
            self.progressStep.emit(lastPercent)
            featIter = puLyr.getFeatures(QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry))
            updateMap = {}
            for feat in featIter:
                puid = feat.attributes()[puidIdx]
                if puid in results:
                    updateVal = self.valuesSummarizeSingle(results[puid],calcType,intersectOp)
                    updateMap[feat.id()] = {destIdx : updateVal}
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
            puLyr.dataProvider().changeAttributeValues(updateMap)

    #
    # multiple field update pu layer

    def puLayerMultiUpdate(self,results,puLyr,idField,destName,calcType,intersectOp,geomType):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        maxFields = 254
        # confirm it is valid
        if puLyr.isValid():
            fields = puLyr.dataProvider().fields()
            puidIdx = fields.indexFromName(idField)
            fldCount = len(fields) + len(self.uniqueValues)
            if fldCount > maxFields:
                self.abort = True
                raise NameError('Too many values to add fields for each')
                return 
            if self.abort == False:
                idxDict = {}
                for val in self.uniqueValues:
                    fldName = 'f%s-%03d' % (destName,int(val))
                    destIdx = fields.indexFromName(fldName)
                    if destIdx == -1:
                        try:
                            res = puLyr.dataProvider().addAttributes([QgsField(fldName, QtCore.QVariant.Double, "real", 19, 10)])
                            puLyr.updateFields()
                            fields = puLyr.dataProvider().fields()
                            destIdx = fields.indexFromName(fldName)
                            idxDict[val] = destIdx
                        except:
                            pass
                    else:
                        idxDict[val] = destIdx
                total = puLyr.featureCount()
                current = 1
                lastPercent = 0.0
                self.progressStep.emit(lastPercent)
                featIter = puLyr.getFeatures(QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry))
                updateMap = {}
                for feat in featIter:
                    puid = feat.attributes()[puidIdx]
                    if puid in results:
                        summarizedValues = self.valuesSummarizeMulti(results[puid],calcType,intersectOp)
                        updateValues = self.valuesCreateAttributeMap(summarizedValues,idxDict)
                    else:
                        updateValues = self.valuesCreateAttributeMap(None,idxDict)
                    updateMap[feat.id()] = updateValues
                    current += 1
                    buildPercent = float(current) / float(total) * 100
                    # limit signals to increase processing speed
                    if int(buildPercent) > lastPercent and buildPercent <= 99.0:
                        self.progressStep.emit(buildPercent)
                        lastPercent = buildPercent
                        if self.abort:
                            break 
                puLyr.dataProvider().changeAttributeValues(updateMap)

    #
    # single file output

    def fileSingleOutput(self,results,puLyr,destName,calcType,intersectOp,idField):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # confirm it is valid
        if puLyr.isValid():
            fName = destName + '.qmd'
            f = open(fName,'w')
            f.write('puid,amount\n')
            total = len(results)
            current = 1
            lastPercent = 0.0
            self.progressStep.emit(lastPercent)
            for key, value in results.iteritems():
                updateVal = self.valuesSummarizeSingle(value,calcType,intersectOp)
                f.write('%d,%f\n' % (key,updateVal))
                current += 1
                buildPercent = float(current) / float(total) * 100
                # limit signals to increase processing speed
                if int(buildPercent) > lastPercent and buildPercent <= 99.0:
                    self.progressStep.emit(buildPercent)
                    lastPercent = buildPercent
                    if self.abort:
                        break 
            f.close()
        if self.debug == True:
            QgsMessageLog.logMessage('leaving ' + self.myself())

    #
    # multi file output

    def fileMultiOutput(self,results,puLyr,destName,key,calcType,intersectOp):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # confirm it is valid
        if puLyr.isValid():
            outFiles = {}
            #if key > 0:
                #fName = destName + '.qmd'
                #f = open(fName,'w')
                #f.write('this is a blank file to compare output timestamps to source file modify dates for multi-field output calculations')
                #f.close()
            for val in self.uniqueValues:
                fName = '%s-%03d.qmd' % (destName,int(val))
                outFiles[val] = open(fName,'w')
                outFiles[val].write('puid,amount\n')
            total = len(results)
            current = 1
            lastPercent = 0.0
            self.progressStep.emit(lastPercent)
            for rKey, rValue in results.iteritems():
                updateValues = self.valuesSummarizeMulti(rValue,calcType,intersectOp)
                #QgsMessageLog.logMessage(str(updateValues))
                for cKey, cValue in updateValues.iteritems():
                    outFiles[cKey].write('%d,%f\n' % (rKey,cValue))
                current += 1
                buildPercent = float(current) / float(total) * 100
                # limit signals to increase processing speed
                if int(buildPercent) > lastPercent and buildPercent <= 99.0:
                    self.progressStep.emit(buildPercent)
                    lastPercent = buildPercent
                    if self.abort:
                        break 
            for fKey,fValue in outFiles.iteritems():
                fValue.close()

    #
    # write value info file

    def fileWriteQMIFile(self,calcRecord):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
            #QgsMessageLog.logMessage(str(calcRecord))
        fName = calcRecord['destName'] + '.qmi'
        if calcRecord['geomType'] == 'raster':
            srcPath,srcName = os.path.split(calcRecord['srcLyr'].source())
            if calcRecord['singleField'] == True:
                if self.debug == True:
                    QgsMessageLog.logMessage('raster single')
                f = open(fName,'w')
                srcText = srcName
                methodText = "%s using %s" % (calcRecord['calcType'],calcRecord['intersectOp'])
                nameText = calcRecord['name']
                f.write('value,name,source,method,description\n')
                f.write("0,'%s','%s','%s','%s'\n" % (nameText,srcText,methodText,calcRecord['description']))
                f.close()
            else:
                if self.debug == True:
                    QgsMessageLog.logMessage('raster multi')
                f = open(fName,'w')
                srcText = srcName
                methodText = "%s using %s" % (calcRecord['calcType'],calcRecord['intersectOp'])
                f.write('value,name,source,method,description\n')
                # get unique values
                vals = list(self.uniqueValues)
                # get definitions from Raster Attribute Table if possible
                srcFile = os.path.join(srcPath,srcName)
                ratList = {}
                if os.path.exists(srcFile):
                    raster = gdal.Open(srcFile)
                    band = raster.GetRasterBand(1)
                    RAT = band.GetDefaultRAT()
                    if RAT <> None:
                        rCnt = RAT.GetRowCount()
                        cCnt = RAT.GetColumnCount()
                        for x in range(rCnt):
                            key = int(RAT.GetValueAsString(x,0))
                            value = RAT.GetValueAsString(x,2)
                            ratList[key] = value
                    band = None
                    raster = None
                # write results
                for val in vals:
                    if int(val) in ratList:
                        nameText = ratList[int(val)]
                    else:
                        nameText = "%s value of %d" % (calcRecord['name'],int(val))
                    f.write("%d,'%s','%s','%s','%s'\n" % (int(val),nameText,srcText,methodText,calcRecord['description']))
                f.close()
        elif calcRecord['geomType'] == 'pufield':
            srcPath,srcName = os.path.split(calcRecord['puLyr'].source())
            if self.debug == True:
                QgsMessageLog.logMessage('pufield')
            f = open(fName,'w')
            srcText = srcName
            methodText = "%s values using %s" % (calcRecord['calcField'],calcRecord['intersectOp'])
            nameText = calcRecord['name']
            f.write('value,name,source,method,description\n')
            f.write("0,'%s','%s','%s','%s'\n" % (nameText,srcText,methodText,calcRecord['description']))
            f.close()
        else:
            srcPath,srcName = os.path.split(calcRecord['srcLyr'].source())
            if calcRecord['singleField'] == True:
                if self.debug == True:
                    QgsMessageLog.logMessage('vector single')
                f = open(fName,'w')
                srcText = srcName
                if calcRecord['calcType'] in ['calculate','value']:
                    methodText = "%s values with %s using %s" % (calcRecord['calcField'],calcRecord['calcType'],calcRecord['intersectOp'])
                else:
                    methodText = "%s using %s" % (calcRecord['calcType'],calcRecord['intersectOp'])
                nameText = calcRecord['name']
                f.write('value,name,source,method,description\n')
                f.write("0,'%s','%s','%s','%s'\n" % (nameText,srcText,methodText,calcRecord['description']))
                f.close()
            else:
                if self.debug == True:
                    QgsMessageLog.logMessage('vector multi')
                f = open(fName,'w')
                srcText = srcName
                methodText = "%s using %s" % (calcRecord['calcType'],calcRecord['intersectOp'])
                methodText += " with %s" % calcRecord['calcField']
                f.write('value,name,source,method,description\n')
                vals = list(self.uniqueValues)
                for val in vals:
                    nameText = '%s value of %d' % (calcRecord['name'], int(val))
                    f.write("%d,'%s','%s','%s','%s'\n" % (int(val),nameText,srcText,methodText,calcRecord['description']))
                f.close()



    progressAll = QtCore.pyqtSignal(int)
    progressCalc = QtCore.pyqtSignal(int)
    progressStep = QtCore.pyqtSignal(int)
    workerStatus = QtCore.pyqtSignal(str)
    workerError = QtCore.pyqtSignal(Exception, basestring, str)
    workerFinished = QtCore.pyqtSignal(bool)
            
