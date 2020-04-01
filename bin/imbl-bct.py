#!/usr/bin/env python3

import sys
import os
import parse
import re

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot, QSettings, QProcess, QEventLoop, QTimer
from PyQt5.QtWidgets import QFileDialog, QApplication
from PyQt5.uic import loadUi

from subprocess import Popen
from pathlib import Path

execPath = os.path.dirname(os.path.realpath(__file__)) + os.path.sep
dataPath = "/data/imbl"


class MainWindow(QtWidgets.QMainWindow):

    configName = ".imbl-bct"
    etcConfigName = os.path.join(Path.home(), configName)
    amLoading = False

    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = loadUi(execPath + '../share/imbl-bct.ui', self)
        for errLabel in self.ui.findChildren(QtWidgets.QLabel, QtCore.QRegExp("^err\\w+")):
            errLabel.hide()

        self.ui.expSelect.addItem("Loading...")
        self.update()
        QtCore.QCoreApplication.processEvents()
        experiments = [name for name in sorted(os.listdir(dataPath))
                                if os.path.isdir(os.path.join(dataPath, name))]
        self.ui.expSelect.clear()
        self.ui.expSelect.addItems(experiments)

        self.configObjects = (
            self.ui.expPath,
            self.ui.expSelect,
            self.ui.inPath,
            self.ui.inSelect,
            self.ui.outPath, 
            self.ui.outAuto,
            self.ui.energy,
            self.ui.distance,
            self.ui.dose
        )
        for swdg in self.configObjects:
            if isinstance(swdg, QtWidgets.QLineEdit):
                swdg.textChanged.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QCheckBox):
                swdg.toggled.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QAbstractSpinBox):
                swdg.valueChanged.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QComboBox):
                swdg.currentTextChanged.connect(self.saveConfiguration)
        #QtCore.QTimer.singleShot(100, self.loadConfiguration)
        self.loadConfiguration()        

        self.ui.expSelect.activated.connect(lambda: \
            self.ui.expPath.setText(os.path.join(dataPath, self.ui.expSelect.currentText())) )
        self.ui.expPath.textChanged.connect(self.onNewExperiment)
        self.ui.inSelect.activated.connect(lambda: \
            self.ui.inPath.setText(os.path.join(self.ui.expPath.text(), "input", self.ui.inSelect.currentText())))
        def outAutoSet():
            if self.ui.outAuto.isChecked():
                self.ui.outPath.setText(re.sub(r"/input/", "/output/", self.ui.inPath.text()))
        self.ui.inPath.textChanged.connect(lambda: (self.onNewSample(), outAutoSet()))
        self.ui.outAuto.toggled.connect(outAutoSet)
        #self.ui.GoStop.clicked.connect(self.onNewSample)



    @pyqtSlot()
    def saveNewConfiguration(self):
        self.saveConfiguration("")

    @pyqtSlot()
    def saveConfiguration(self, fileName=etcConfigName):

        if self.amLoading:
            return

        if not fileName:
            newfile, _filter = QFileDialog.getSaveFileName(
                self, "IMBL-BCT processing configuration",
                directory=self.ui.outPath.text())
            if newfile:
                fileName = newfile
        if not fileName:
            return

        config = QSettings(fileName, QSettings.IniFormat)

        def valToSave(wdg):
            if isinstance(wdg, QtWidgets.QLineEdit):
                return wdg.text()
            elif isinstance(wdg, QtWidgets.QCheckBox):
                return wdg.isChecked()
            elif isinstance(wdg, QtWidgets.QAbstractSpinBox):
                return wdg.value()
            elif isinstance(wdg, QtWidgets.QComboBox):
                return wdg.currentText()
        for swdg in self.configObjects:
            config.setValue(swdg.objectName(), valToSave(swdg))

    @pyqtSlot()
    def loadNewConfiguration(self):
        self.loadConfiguration("")

    @pyqtSlot()
    def loadConfiguration(self, fileName=etcConfigName):

        if not fileName:
            newfile, _filter = QFileDialog.getOpenFileName(
                self, "IMBL-BCT processing configuration",
                directory=self.ui.outPath.text())
            if newfile:
                fileName = newfile
        if not os.path.exists(fileName):
            return

        self.amLoading = True
        config = QSettings(fileName, QSettings.IniFormat)

        def valToLoad(wdg, nm):
            if isinstance(wdg, QtWidgets.QLineEdit):
                wdg.setText(config.value(nm, type=str))
            elif isinstance(wdg, QtWidgets.QCheckBox):
                wdg.setChecked(config.value(nm, type=bool))
            elif isinstance(wdg, QtWidgets.QAbstractSpinBox):
                wdg.setValue(config.value(nm, type=float))
            elif isinstance(wdg, QtWidgets.QComboBox):
                txt = config.value(nm, type=str)
                didx = wdg.findText(txt)
                if not didx < 0:
                    wdg.setCurrentIndex(didx)
        for swdg in self.configObjects:
            oName = swdg.objectName()
            if config.contains(oName):
                valToLoad(swdg, oName)
                if swdg is self.ui.expPath:
                    self.onNewExperiment()

        self.amLoading = False

    @pyqtSlot()
    def onNewExperiment(self):
        ePath = os.path.join(self.ui.expPath.text(), "input")
        self.ui.inSelect.blockSignals(True)
        self.ui.inSelect.addItem("Loading...")
        self.update()
        QtCore.QCoreApplication.processEvents()
        samples = [name for name in sorted(os.listdir(ePath))
                            if os.path.isdir(os.path.join(ePath, name))]
        self.ui.inSelect.clear()
        self.ui.inSelect.addItems(samples)
        self.ui.inSelect.blockSignals(False)


    @pyqtSlot()
    def onNewSample(self):

        self.ui.GoStop.setEnabled(False)
        for errLabel in self.ui.findChildren(QtWidgets.QLabel, QtCore.QRegExp("^err\\w+")):
            errLabel.hide()

        ipath = self.ui.inPath.text()
        if not os.path.isdir(ipath) :
            self.ui.errNoPath.show()
            return
        parsed = parse.parse("{}_{:g}keV_{:g}m_{:g}mGy", os.path.basename(ipath)).fixed
        if len(parsed) == 4 :
            self.ui.sample.setText(parsed[0])
            self.ui.energy.setValue(parsed[1])
            self.ui.distance.setValue(parsed[2])
            self.ui.dose.setValue(parsed[3])
        else:
            self.ui.errFolderName.show()

        cfgName = ''
        attempt = 0
        while True:
            n_cfgName = os.path.join(ipath, 'acquisition.%i.configuration' % attempt)
            if os.path.exists(n_cfgName):
                cfgName = n_cfgName
            else:
                break
            attempt += 1
        if not cfgName:  # one more attempt for little earlier code
            cfgName = os.popen('ls ' + ipath + os.sep + 'acquisition.*conf*' +
                               ' | sort -V | tail -n 1').read().strip("\n")
        if not cfgName:
            self.ui.errNoConfig.show()
            return
        cfg = QSettings(cfgName, QSettings.IniFormat)
        def valFromConfig(key, tp=None):
            if not cfg.contains(key):
                raise Exception
            return cfg.value(key, type=tp)
        try:
            valFromConfig('version', str)
            serialScan = valFromConfig('doserialscans', bool)
            twodScans = serialScan and valFromConfig('serial/2d', bool)
            iSteps = valFromConfig('serial/innearseries/nofsteps', int)
            oSteps = valFromConfig('serial/outerseries/nofsteps', int)
            self.ui.tilesW.setValue( 1 if not serialScan else oSteps if not twodScans else iSteps )
            self.ui.tilesH.setValue( 1 if not serialScan or not twodScans else oSteps )
            arc = valFromConfig('scan/range', float)
            self.ui.arc.setText(str(arc)+'deg')
            self.ui.arcR.setText(str(arc)+'deg')
            projections = valFromConfig('scan/steps', int)
            self.ui.projections.setValue(projections)
            self.ui.projectionsR.setValue(projections)
            self.ui.step.setText(str(arc/projections)+'deg')
            self.ui.stepR.setText(str(arc/projections)+'deg')
        except:
            self.ui.errBadConfig.show()
            return

        logName = re.sub(r"\.config.*", ".log", cfgName)
        if os.path.exists(logName):
            logInfo = os.popen('cat "' + logName + '" | imbl-log.py -i' +
                               ' | grep \'# Common\' | cut -d\' \' -f 4- ' ).read().strip("\n").split()
            if len(logInfo) == 3:
                self.ui.arcR.setText(logInfo[0]+'deg')
                self.ui.projectionsR.setValue(int(logInfo[1]))
                self.ui.stepR.setText(logInfo[2]+'deg')
            else:
                self.ui.errBadLog.show()            
        else :
            self.ui.errNoLog.show()

        self.ui.GoStop.setEnabled(True)

        





app = QApplication(sys.argv)
my_mainWindow = MainWindow()
my_mainWindow.show()
sys.exit(app.exec_())
