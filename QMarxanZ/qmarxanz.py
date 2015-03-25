# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QMarxanZ
                                 A QGIS plugin
 Create Marxan and Marxan with Zones inputs and import results
                              -------------------
        begin                : 2014-09-18
        git sha              : $Format:%H$
        copyright            : (C) 2014 by Apropos Information Systems Inc.
        email                : tsw@aproposinfosystems.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4 import QtCore, QtGui
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from qmz_settings_gis import qmzSettings
from qmz_define import qmzDefine
from qmz_run import qmzRun
from qmz_makegrid import qmzMakeGrid
from qmz_calc import qmzCalcContent
import os.path


class QMarxanZ:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QtCore.QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'QMarxanZ_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

                
    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

       # Add toolbar 
        self.toolBar = self.iface.addToolBar("QMarxanZ")
        self.toolBar.setObjectName("QMarxanZ")

        # Settings and GIS Action
        self.settingsAction = QtGui.QAction(
            QtGui.QIcon(":/plugins/QMarxanZ/icons/qmz_settings.png"),
            u"Settings and GIS", self.iface.mainWindow())
        # connect the action to the run method
        self.settingsAction.triggered.connect(self.settings)
        self.toolBar.addAction(self.settingsAction)
        
        # Project Definition Action
        self.defineAction = QtGui.QAction(
            QtGui.QIcon(":/plugins/QMarxanZ/icons/qmz_define.png"),
            u"Define Problem", self.iface.mainWindow())
        # connect the action to the run method
        self.defineAction.triggered.connect(self.define)
        self.toolBar.addAction(self.defineAction)

        # Run Action
        self.runAction = QtGui.QAction(
            QtGui.QIcon(":/plugins/QMarxanZ/icons/qmz_run.png"),
            u"Configure and Run", self.iface.mainWindow())
        # connect the action to the run method
        self.runAction.triggered.connect(self.run)
        self.toolBar.addAction(self.runAction)

        # Make Grid Action
        self.makeGridAction = QtGui.QAction(
            QtGui.QIcon(":/plugins/QMarxanZ/icons/qmz_mkgrid.png"),
            u"Make Planning Grid", self.iface.mainWindow())
        # connection action to run method
        self.makeGridAction.triggered.connect(self.makeGrid)
        self.toolBar.addAction(self.makeGridAction)

        # GIS Calculator Action
        self.calculatorAction = QtGui.QAction(
            QtGui.QIcon(":/plugins/QMarxanZ/icons/qmz_calc.png"),
            u"Calculate Planning Unit Content", self.iface.mainWindow())
        # connection action to run method
        self.calculatorAction.triggered.connect(self.gisCalculate)
        self.toolBar.addAction(self.calculatorAction)

        # add to menu
        self.iface.addPluginToMenu(u"&QMarxanZ", self.settingsAction)
        self.iface.addPluginToMenu(u"&QMarxanZ", self.defineAction)
        self.iface.addPluginToMenu(u"&QMarxanZ", self.runAction)
        self.iface.addPluginToMenu(u"&QMarxanZ", self.makeGridAction)
        self.iface.addPluginToMenu(u"&QMarxanZ", self.calculatorAction)


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(u"&QMarxanZ", self.settingsAction)
        self.iface.removePluginMenu(u"&QMarxanZ", self.defineAction)
        self.iface.removePluginMenu(u"&QMarxanZ", self.runAction)
        self.iface.removePluginMenu(u"&QMarxanZ", self.makeGridAction)
        self.iface.removePluginMenu(u"&QMarxanZ", self.calculatorAction)

        # remove tool bar
        self.toolBar.hide()
        self.toolBar = None

    # open settings dialog
    def settings(self):

        # Create the dialog (after translation) and keep reference
        self.dlg = qmzSettings(self.iface)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

    # open project definition dialog
    def define(self):

        # Create the dialog (after translation) and keep reference
        self.dlg = qmzDefine(self.iface)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

    # open configure and run dialog
    def run(self):

        # Create the dialog (after translation) and keep reference
        self.dlg = qmzRun(self.iface)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

    # open make grid dialog
    def makeGrid(self):

        # Create the dialog (after translation) and keep reference
        self.dlg = qmzMakeGrid(self.iface)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

    # open calculator dialog
    def gisCalculate(self):

        # Create the dialog (after translation) and keep reference
        self.dlg = qmzCalcContent(self.iface)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

