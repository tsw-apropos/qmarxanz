"""
# -*- coding: utf-8 -*-
#
# ========================================================
# 
# Purpose: Create a square or hexagon grid worker
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
import ogr, gdal, inspect
import numpy as np

#
# function to grid layer
#

class gridCreator(QtCore.QObject):
    
    def __init__(self, outFName, bbox, puShape, sideLength, puCount, clipLayer,
        useRaster, crs, encoding, *args, **kwargs):
        QtCore.QObject.__init__(self, *args, **kwargs)
        self.creationPercentage = 0
        self.stepPercentage = 0
        self.abort = False
        self.outFName = outFName
        self.bbox = bbox
        self.puShape = puShape
        self.sideLength = sideLength
        self.puCount = puCount
        self.clipLayer = clipLayer
        self.useRaster = useRaster
        self.crs = crs
        self.encoding = encoding
        self.killed = False
        self.tempPrefix = 'qmz%d_' % os.getpid()
        self.gridTools = qmzGrid()
        #
        self.debug = False
        if self.debug == True:
            self.myself = lambda: inspect.stack()[1][3]
            QgsMessageLog.logMessage(self.myself())


    def run(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        try:
            self.status.emit('Started')
            # determine number of steps
            if self.clipLayer == None:
                self.stepCount = 1
            else:
                if self.useRaster == True:
                    self.stepCount = 5
                else:
                    self.stepCount = 8
            step = 0
            # step 1
            if self.puShape == 'square':
                self.status.emit('Building Squares')
                step += 1
                self.updateCreationProgress(step)
                self.buildSquares(True)
            else:
                self.status.emit('Building Hexagons')
                step += 1
                self.updateCreationProgress(step)
                self.buildHexagons()
            if self.clipLayer <> None:
                # determine if clip layer is vector
                if self.clipLayer.type() == 1:
                    clipFormat = 'raster'
                else:
                    clipFormat = 'vector'
                if clipFormat == 'vector':
                    if self.useRaster == True:
                        # step 2
                        self.status.emit('Creating temporary files')
                        step += 1
                        self.updateCreationProgress(step)
                        self.createMatchingRasters()
                        # setp 3
                        self.status.emit('Identifying overlaps')
                        step += 1
                        self.updateCreationProgress(step)
                        matchList = self.rasterFindMatchingPUs()
                    else:
                        # step 2
                        path,fname = os.path.split(self.outFName)
                        tsn = os.path.join(path, self.tempPrefix + 'single.shp')
                        tgn = os.path.join(path, self.tempPrefix + 'grid.shp')
                        tin = os.path.join(path, self.tempPrefix + 'int.shp')
                        tsgn = os.path.join(path, self.tempPrefix + 'singlegrid.shp')
                        self.status.emit('Converting multi features to single')
                        step += 1
                        self.updateCreationProgress(step)
                        self.multiToSingle(self.clipLayer)
                        # step 3
                        self.status.emit('Creating temporary grid')
                        step += 1
                        self.updateCreationProgress(step)
                        self.buildSquares(False)
                        # step 4
                        self.status.emit('Intersecting single with temporary grid')
                        step += 1
                        self.updateCreationProgress(step)
                        grdLyr = QgsVectorLayer(tgn, 'tempgrid', 'ogr')
                        sngLyr = QgsVectorLayer(tsn, 'tempsingle', 'ogr')
                        self.intersectLayers(sngLyr,grdLyr,tsgn)
                        grdLyr = None
                        self.removeTempFile(tgn)
                        sngLyr = None
                        self.removeTempFile(tsn)
                        # step 5
                        self.status.emit('Intersecting layers')
                        step += 1
                        self.updateCreationProgress(step)
                        puLyr = QgsVectorLayer(self.outFName, 'pu', 'ogr')
                        tsgLyr = QgsVectorLayer(tsgn, 'tempsinglegrid', 'ogr')
                        self.intersectLayers(tsgLyr,puLyr,tin)
                        puLyr = None
                        tsgLyr = None
                        self.removeTempFile(tsgn)
                        # step 6
                        self.status.emit('Identifying overlaps')
                        step += 1
                        self.updateCreationProgress(step)
                        intLyr = QgsVectorLayer(tin, 'tempint', 'ogr')
                        matchList = self.vectorFindMatchingPUs(intLyr)
                        intLyr = None
                        self.removeTempFile(tin)
                else:
                    # step 2
                    self.status.emit('Creating temporary files')
                    step += 1
                    self.updateCreationProgress(step)
                    self.createMatchingRaster()
                    # setp 3
                    self.status.emit('Identifying overlaps')
                    step += 1
                    self.updateCreationProgress(step)
                    matchList = self.rasterFindMatchingPUs(self.clipLayer.source())
                # step 4 or 7
                self.status.emit('Deleting non-overlapping PUs')
                step += 1
                self.updateCreationProgress(step)
                self.deleteCells(matchList)
                # step 5 or 8
                self.status.emit('Renumbering puid field')
                step += 1
                self.updateCreationProgress(step)
                self.reNumberPUs()
            if self.abort == False:
                self.status.emit('Completed')
            else:
                self.status.emit('Cancelled')
            self.finished.emit(True)
        except Exception, e:
            import traceback
            self.error.emit(e, traceback.format_exc())
            self.finished.emit(False)

    #
    # kill worker

    def kill(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.abort = True

    #
    # remove temporary files

    def removeTempFile(self,fName):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        if os.path.exists(fName):
            QgsVectorFileWriter.deleteShapeFile(fName)
            rFName,ext = os.path.splitext(fName)
            lfn = rFName + '.cpg'
            if os.path.exists(lfn):
                os.remove(lfn)

    #
    # update creation progress
    
    def updateCreationProgress(self, stepNumber):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.creationPercentage = stepNumber / float(self.stepCount) * 100
        self.creationProgress.emit(self.creationPercentage)

    #
    # build squares

    def buildSquares(self, useSideLength):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # place squares from top left corner
        xMin = self.bbox[0]
        yMax = self.bbox[1]
        xMax = self.bbox[2]
        yMin = self.bbox[3]
        if useSideLength:
            sideLen = self.sideLength
            fName = self.outFName
        else:
            sideLen = min((xMax -xMin) / 10.0, (yMax - yMin) / 10.0)
            path,fname = os.path.split(self.outFName)            
            fName = os.path.join(path, self.tempPrefix + 'grid.shp')
        fields = QgsFields()
        fields.append(QgsField("puid", QtCore.QVariant.Int))
        fields.append(QgsField("pu_status", QtCore.QVariant.Double, "real", 19, 10))
        fields.append(QgsField("bnd_cost", QtCore.QVariant.Double, "real", 19, 10))
        fields.append(QgsField("area", QtCore.QVariant.Double, "real", 19, 10))
        fields.append(QgsField("perimeter", QtCore.QVariant.Double, "real", 19, 10))
        fields.append(QgsField("sidelength", QtCore.QVariant.Double, "real", 19, 10))
        check = QtCore.QFile(fName)
        if check.exists():
            if not QgsVectorFileWriter.deleteShapeFile(fName):
                return
        writer = QgsVectorFileWriter(fName, self.encoding, fields, QGis.WKBPolygon, self.crs, 'ESRI Shapefile')
        outFeat = QgsFeature()
        outFeat.setFields(fields)
        outGeom = QgsGeometry()
        idVar = 1
        puArea = float(sideLen)**2
        puPerimeter = float(sideLen)*4
        cellCount = self.gridTools.calcSquareCount(sideLen,xMin,xMax,yMin,yMax)
        #QgsMessageLog.logMessage('ready to build %d squares' % cellCount)
        y = yMax
        #QgsMessageLog.logMessage('starting build')
        while y >= yMin and self.abort == False:
            x = xMin
            while x < xMax and self.abort == False:
                polygon = self.gridTools.createSquare(x, y, sideLen)
                outFeat.setGeometry(outGeom.fromPolygon(polygon))
                outFeat.setAttributes([idVar,0.0,1.0,puArea,puPerimeter,sideLen])
                writer.addFeature(outFeat)
                idVar = idVar + 1
                x = x + sideLen
            y = y - sideLen
            buildPercent = idVar / float(cellCount) * 100
            self.stepProgress.emit(buildPercent)
        # close writer
        del writer    

    #
    # build hexagons

    def buildHexagons(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        fields = QgsFields()
        fields.append(QgsField("puid", QtCore.QVariant.Int))
        fields.append(QgsField("pu_status", QtCore.QVariant.Double, "real", 19, 10))
        fields.append(QgsField("bnd_cost", QtCore.QVariant.Double, "real", 19, 10))
        fields.append(QgsField("area", QtCore.QVariant.Double, "real", 19, 10))
        fields.append(QgsField("perimeter", QtCore.QVariant.Double, "real", 19, 10))
        fields.append(QgsField("sidelength", QtCore.QVariant.Double, "real", 19, 10))
        check = QtCore.QFile(self.outFName)
        if check.exists():
            if not QgsVectorFileWriter.deleteShapeFile(self.outFName):
                return
        writer = QgsVectorFileWriter(self.outFName, self.encoding, fields, QGis.WKBPolygon, self.crs, 'ESRI Shapefile')
        outFeat = QgsFeature()
        outFeat.setFields(fields)
        outGeom = QgsGeometry()
        idVar = 1
        # place hexagons from just above top left corner
        puArea = self.gridTools.calcHexagonArea(self.sideLength)
        puPerimeter = float(self.sideLength)*6        
        xMin = self.bbox[0]
        yMax = self.bbox[1]
        xMax = self.bbox[2]
        yMin = self.bbox[3]
        cellCount = self.gridTools.calcHexagonCount(self.sideLength,xMin,xMax,yMin,yMax)
        hyp,side_a,side_b = self.gridTools.hexagonTrig(self.sideLength)
        #QgsMessageLog.logMessage('ready to build %d squares' % cellCount)
        y = yMax + side_b
        rowType = 'a'
        buildPercent = 0.0
        while y >= yMin and self.abort == False:
            if rowType == 'a':
                x = xMin
                rowType = 'b'
            else:
                rowType = 'a'
                x = xMin + self.sideLength + side_a
            while x < xMax and self.abort == False:
                polygon = self.gridTools.createHexagon(x, y, self.sideLength)
                outFeat.setGeometry(outGeom.fromPolygon(polygon))
                outFeat.setAttributes([idVar,0.0,1.0,puArea,puPerimeter,self.sideLength])
                writer.addFeature(outFeat)
                idVar = idVar + 1
                x = x + (2 * self.sideLength) + (2 * side_a)
            y = y - side_b
            buildPercent = idVar / float(cellCount) * 100
            self.stepProgress.emit(buildPercent)
        # close writer
        del writer    

    #
    # buffer source
    # Modified code from Buffer.py in ftools by Victor Olaya

    def bufferLayer(self,sourceLayer):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # create needed variables
        outFeat = QgsFeature()
        inFeat = QgsFeature()
        inGeom = QgsGeometry()
        outGeom = QgsGeometry()
        # set buffer parameters
        buffDist = self.sideLength * 0.01
        segCount = 5
        # get feature list
        features = vector.features(sourceLayer)
        # create temp filename
        path,fname = os.path.split(self.outFName)
        tfn = os.path.join(path, self.tempPrefix + 'buff.shp')
        # create fields
        fields = QgsFields()
        fields.append(QgsField("id", QtCore.QVariant.Int))
        # create writer
        writer = QgsVectorFileWriter(tfn, self.encoding, fields, QGis.WKBPolygon, self.crs, 'ESRI Shapefile')
        # loop through features
        current = 0
        self.stepProgress.emit(1)
        total = len(features)
        for feat in features:
            current += 1
            buildPercent = current / total * 100
            self.stepProgress.emit(buildPercent)
            inGeom = QgsGeometry(feat.geometry())
            outGeom = inGeom.buffer(float(buffDist), segCount)
            outFeat.setGeometry(outGeom)
            outFeat.setAttributes([1])
            writer.addFeature(outFeat)
            if self.abort == True:
                break
        # close writer
        del writer

    #
    # multi to single
    # modified from ftools MutlipartToSingleparts by Victor Olaya

    def multiToSingle(self,sourceLayer):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # create temp filename
        path,fname = os.path.split(self.outFName)
        tfn = os.path.join(path, self.tempPrefix + 'single.shp')
        # create fields
        fields = QgsFields()
        fields.append(QgsField("id", QtCore.QVariant.Int))
        # create writer
        writer = QgsVectorFileWriter(tfn, self.encoding, fields, QGis.WKBPolygon, self.crs, 'ESRI Shapefile')
        # define variables to hold features
        outFeat = QgsFeature()
        inGeom = QgsGeometry()
        # prepare to loop through features
        current = 0
        features = vector.features(sourceLayer)
        total = len(features)
        for f in features:
            # get geometry
            inGeom = f.geometry()
            # convert to single
            geometries = self.convertToSingle(inGeom)
            total = total + len(geometries) - 1
            outFeat.setAttributes([1])
            # add feature for each part
            for g in geometries:
                # index and report progress
                current += 1
                buildPercent = current / total * 100
                self.stepProgress.emit(buildPercent)
                outFeat.setGeometry(g)
                writer.addFeature(outFeat)
            if self.abort == True:
                break
        # close file
        del writer

    #
    # convert multi geometries to single geometries
    # modified from ftools MutlipartToSingleparts by Victor Olaya

    def convertToSingle(self,geom):

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
    # intersect layers
    # modified code Intersection.py in ftools by Victor Olaya

    def intersectLayers(self,aLayer,bLayer,tfn):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # create fields and variables to hold information
        fields = QgsFields()
        fields.append(QgsField("puid", QtCore.QVariant.Int))
        writer = QgsVectorFileWriter(tfn, self.encoding, fields, QGis.WKBPolygon, self.crs, 'ESRI Shapefile')
        aFeat = QgsFeature()
        bFeat = QgsFeature()
        outFeat = QgsFeature()
        index = vector.spatialindex(aLayer)
        nElement = 0
        bFeatures = vector.features(bLayer)
        nFeat = len(bFeatures)
        idIdx = bLayer.dataProvider().fields().indexFromName('puid')
        for bFeat in bFeatures:
            nElement += 1
            buildPercent = nElement / float(nFeat) * 100
            self.stepProgress.emit(buildPercent)            
            bGeom = QgsGeometry(bFeat.geometry())
            idVal = bFeat.attributes()[idIdx]
            intersects = index.intersects(bGeom.boundingBox())
            for i in intersects:
                request = QgsFeatureRequest().setFilterFid(i)
                aFeat = aLayer.getFeatures(request).next()
                tmpGeom = QgsGeometry(aFeat.geometry())
                try:
                    if bGeom.intersects(tmpGeom):
                        intGeom = QgsGeometry(bGeom.intersection(tmpGeom))
                        if intGeom.wkbType() == QGis.WKBUnknown:
                            intCom = bGeom.combine(tmpGeom)
                            intSym = bGeom.symDifference(tmpGeom)
                            intGeom = QgsGeometry(intCom.difference(intSym))
                        try:
                            if intGeom.wkbType() in (QGis.WKBPolygon,QGis.WKBMultiPolygon):
                                outFeat.setGeometry(intGeom)
                                outFeat.setAttributes([idVal])
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
        del writer

    #
    # renumber PUs

    def reNumberPUs(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # open layer
        gridLayer = QgsVectorLayer(self.outFName, 'grid', 'ogr')
        # confirm it is valid
        if gridLayer.isValid():
            fields = gridLayer.dataProvider().fields()
            idx = fields.indexFromName('puid')
            total = gridLayer.featureCount()
            idVar = 1
            lastPercent = 0.0
            self.stepProgress.emit(lastPercent)
            featIter = gridLayer.getFeatures(QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry))
            updateMap = {}
            for feat in featIter:
                updateMap[feat.id()] = {idx : idVar}
                idVar += 1
                buildPercent = float(idVar) / float(total) * 100
                # limit signals to increase processing speed
                if int(buildPercent) > lastPercent:
                    self.stepProgress.emit(buildPercent)
                    lastPercent = buildPercent
                    if self.abort:
                        break 
            gridLayer.dataProvider().changeAttributeValues(updateMap)
        # close layer
        gridLayer = None

    #
    # delete cells

    def deleteCells(self,matchList):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # open layer
        gridLayer = QgsVectorLayer(self.outFName, 'grid', 'ogr')
        # confirm valid
        if gridLayer.isValid():
            total = gridLayer.featureCount()
            # create deletion list
            deleteList = []
            featIter = gridLayer.getFeatures(QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry))
            current = 0
            lastPercent = 0.0
            self.stepProgress.emit(lastPercent)
            for feat in featIter:
                if not feat.attributes()[0] in matchList:
                    deleteList.append(feat.id())
                current += 1
                buildPercent = float(current) / float(total) * 100
                # limit signals to increase processing speed
                if int(buildPercent) > lastPercent:
                    self.stepProgress.emit(buildPercent)
                    lastPercent = buildPercent
                    if self.abort:
                        break 
            # if deletion list not empty, delete records
            if len(deleteList) > 0:
                gridLayer.startEditing()
                gridLayer.dataProvider().deleteFeatures(deleteList)
                gridLayer.commitChanges()
        else:
            self.status.emit('Could not delete non-overlapping PUs')
            self.abort = True
        # close layer
        gridLayer = None
            
    #
    # find PUs that overlap with clip layer via vector
    
    def vectorFindMatchingPUs(self,tempLayer):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # confirm it is valid
        if tempLayer.isValid():
            fields = tempLayer.dataProvider().fields()
            total = tempLayer.featureCount()
            current = 0
            lastPercent = 0.0
            self.stepProgress.emit(lastPercent)
            featIter = tempLayer.getFeatures(QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry))
            results = set([])
            for feat in featIter:
                attr = feat.attributes()
                if not attr[0] in results:
                    results.add(attr[0])
                current += 1
                buildPercent = float(current) / float(total) * 100
                # limit signals to increase processing speed
                if int(buildPercent) > lastPercent and buildPercent <= 99.0:
                    self.stepProgress.emit(buildPercent)
                    lastPercent = buildPercent
                    if self.abort:
                        break 
        # return results
        return(results)

    #
    # find PUs that overlap with clip layer via use of raster

    def rasterFindMatchingPUs(self,clipFileName=None):

        def insquare(gid,gval,ndValue):
            if gid <> 0 and gval <> 0 and gval <> ndValue:
                return(gid)
            else:
                return(0)

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        # create arrays for each raster source
        path,fname = os.path.split(self.outFName)
        # need to insert some sort of robust memory test here to prevent
        # system crashes when not enough memory
        try:
            # read grid
            gfn = os.path.join(path,self.tempPrefix+'grid.tif')
            gds = gdal.Open(gfn)
            gdBand = gds.GetRasterBand(1)
            # read clip layer
            if clipFileName == None:
                cfn = os.path.join(path,self.tempPrefix+'clip.tif')
            else:
                cfn = clipFileName
            cds = gdal.Open(cfn)
            cdBand = cds.GetRasterBand(1)
            ndValue = cdBand.GetNoDataValue()
            nRows = gds.RasterYSize
            nCols = gds.RasterXSize
            results = set([])
            vmap = np.vectorize(insquare)
            lastPercent = 0.0
            self.stepProgress.emit(lastPercent)
            for rowIdx in range(nRows):
                rowResults = set([])
                gaf = np.array(gdBand.ReadAsArray(0,rowIdx,nCols,1)).flatten()
                caf = np.array(cdBand.ReadAsArray(0,rowIdx,nCols,1)).flatten()
                rowResults = set(vmap(gaf,caf,ndValue))
                results = results.union(rowResults)
                buildPercent = float(rowIdx) / float(nRows) * 100
                # limit signals to increase processing speed
                if int(buildPercent) > lastPercent:
                    self.stepProgress.emit(buildPercent)
                    lastPercent = buildPercent
                    if self.abort:
                        break
            results.remove(0)
        except:
            self.status.emit('Out of memory')
            self.abort = True
        os.remove(gfn)
        if clipFileName == None:
            os.remove(cfn)
        del gaf
        del caf

        return(results)

    #
    # create matching raster

    def createMatchingRaster(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.stepProgress.emit(0.0)
        # this sleep is inserted here to ensure that the interface refreshes
        # before the gdal processes start which can stall the user interface.
        time.sleep(1)
        # get parameters
        pixelSize = min(self.clipLayer.rasterUnitsPerPixelX(),self.clipLayer.rasterUnitsPerPixelY())
        bbox = self.clipLayer.extent()
        xMin = bbox.xMinimum()
        yMax = bbox.yMaximum()
        xMax = bbox.xMaximum()
        yMin = bbox.yMinimum()
        xRecs = round((xMax - xMin) / pixelSize)
        yRecs = round((yMax - yMin) / pixelSize)
        # progress notification
        self.stepProgress.emit(15.0)
        transformArray = [xMin,pixelSize,0,yMax,0,-pixelSize]
        self.stepProgress.emit(25.0)
        # transform grid 
        self.stepProgress.emit(35.0)
        # transform grid first
        path,fname = os.path.split(self.outFName)
        grFName = os.path.join(path,self.tempPrefix+'grid.tif')
        self.convertToRaster(self.outFName,grFName,xRecs,yRecs,transformArray,'puid')
        self.stepProgress.emit(95.0)

    #
    # create matching rasters

    def createMatchingRasters(self):

        if self.debug == True:
            QgsMessageLog.logMessage(self.myself())
        self.stepProgress.emit(0.0)
        # this sleep is inserted here to ensure that the interface refreshes
        # before the gdal processes start which can stall the user interface.
        time.sleep(1)
        # get parameters
        pixelSize = self.sideLength * 0.1
        xMin = self.bbox[0]
        yMax = self.bbox[1]
        xMax = self.bbox[2]
        yMin = self.bbox[3]
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
        self.stepProgress.emit(5.0)
        # set transform array
        #adfGeoTransform[0] /* top left x */
        #adfGeoTransform[1] /* w-e pixel resolution */
        #adfGeoTransform[2] /* 0 */
        #adfGeoTransform[3] /* top left y */
        #adfGeoTransform[4] /* 0 */
        #adfGeoTransform[5] /* n-s pixel resolution (negative value) */
        transformArray = [xMin,pixelSize,0,yMax,0,-pixelSize]
        self.stepProgress.emit(10.0)
        # transform grid first
        path,fname = os.path.split(self.outFName)
        grFName = os.path.join(path,self.tempPrefix+'grid.tif')
        self.stepProgress.emit(15.0)
        self.convertToRaster(self.outFName,grFName,xRecs,yRecs,transformArray,'puid')
        self.stepProgress.emit(55.0)
        # transform input layer second
        crFName = os.path.join(path,self.tempPrefix+'clip.tif')
        self.stepProgress.emit(60.0)
        clFname = self.clipLayer.dataProvider().dataSourceUri().split('|')[0]
        self.stepProgress.emit(65.0)
        self.convertToRaster(clFname,crFName,xRecs,yRecs,transformArray,None)
        self.stepProgress.emit(95.0)

    #
    # convert to grid
    
    def convertToRaster(self,inFName,outFName,xRecs,yRecs,transformArray,keyField=None):

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
        gdal.RasterizeLayer(tDs, [1], sLyr, None, None, [1], options)
        sLyr = None
        sDs = None
        tDs = None


    stepProgress = QtCore.pyqtSignal(int)
    creationProgress = QtCore.pyqtSignal(int)
    status = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(Exception, basestring)
    finished = QtCore.pyqtSignal(bool)
            
