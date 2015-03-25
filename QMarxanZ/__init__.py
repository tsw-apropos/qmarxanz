# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QMarxanZ
                                 A QGIS plugin
 Create Marxan with Zones inputs and import results
                             -------------------
        begin                : 2014-09-18
        copyright            : (C) 2014 by Apropos Information Systems Inc.
        email                : tsw@aproposinfosystems.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load QMarxanZ class from file QMarxanZ.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from qmarxanz import QMarxanZ
    return QMarxanZ(iface)
