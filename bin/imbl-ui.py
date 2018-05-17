#!/usr/bin/env python3

import sys
import os

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot, QSettings, QProcess, QEventLoop
from PyQt5.QtWidgets import QFileDialog, QApplication
from PyQt5.uic import loadUi

from subprocess import Popen
from pathlib import Path

sys.path.append("..")
from share import ui_imbl


warnStyle = 'background-color: rgba(255, 0, 0, 128);'


class MainWindow(QtWidgets.QMainWindow):

    configName = str(Path.home()) + "/.imbl-ui"

    def __init__(self):
        super(MainWindow, self).__init__()
        # self.ui = loadUi('../share/imbl-ui.ui', self)
        self.ui = ui_imbl.Ui_MainWindow()
        self.ui.setupUi(self)

        self.loadConfiguration()
        self.on_outPath_textChanged()

        for swdg in self.findChildren((QtWidgets.QCheckBox,
                                       QtWidgets.QAbstractSpinBox,
                                       QtWidgets.QLineEdit)):
            if swdg.objectName() == 'qt_spinbox_lineedit':
                pass
            elif isinstance(swdg, QtWidgets.QLineEdit):
                swdg.textChanged.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QCheckBox):
                swdg.toggled.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QAbstractSpinBox):
                swdg.valueChanged.connect(self.saveConfiguration)

        self.scanRange = 0
        self.doSerial = self.do2D = False
        self.initproc = QProcess(self)
        
        self.addToConsole("Am ready...")

    def addToConsole(self, text, qcolor=None):
        if not text:
            return
        if not qcolor:
            qcolor = self.ui.console.palette().text().color()
        self.ui.console.setTextColor(qcolor)
        self.ui.console.append(str(text).strip('\n'))

    def addOutToConsole(self, text):
        self.addToConsole(text, QtCore.Qt.blue)

    def addErrToConsole(self, text):
        self.addToConsole(text, QtCore.Qt.red)

    @pyqtSlot()
    def saveConfiguration(self, fileName=configName):
        config = QSettings(fileName, QSettings.IniFormat)

        def valToSave(wdg):
            if isinstance(wdg, QtWidgets.QLineEdit):
                return wdg.text()
            elif isinstance(wdg, QtWidgets.QCheckBox):
                return wdg.isChecked()
            elif isinstance(wdg, QtWidgets.QAbstractSpinBox):
                return wdg.value()
        for swdg in self.findChildren((QtWidgets.QCheckBox,
                                       QtWidgets.QAbstractSpinBox,
                                       QtWidgets.QLineEdit)):
            if swdg.objectName() != 'qt_spinbox_lineedit':
                config.setValue(swdg.objectName(), valToSave(swdg))

    @pyqtSlot()
    def loadConfiguration(self, fileName=configName):
        config = QSettings(fileName, QSettings.IniFormat)

        def valToLoad(wdg, val):
            if isinstance(wdg, QtWidgets.QLineEdit):
                wdg.setText(str(val))
            elif isinstance(wdg, QtWidgets.QCheckBox):
                wdg.setChecked(bool(val))
            elif isinstance(wdg, QtWidgets.QAbstractSpinBox):
                wdg.setValue(float(val))
        for swdg in self.findChildren((QtWidgets.QCheckBox,
                                      QtWidgets.QAbstractSpinBox,
                                      QtWidgets.QLineEdit)):
            oName = swdg.objectName()
            if config.contains(oName) and \
               oName != 'qt_spinbox_lineedit':
                valToLoad(swdg, config.value(oName))

    @pyqtSlot()
    def on_inBrowse_clicked(self):
        newdir = QFileDialog.getExistingDirectory(self, "Experiment directory",
                                                  self.ui.inPath.text())
        if newdir:
            self.ui.inPath.setText(newdir)

    @pyqtSlot(str)
    def on_inPath_textChanged(self):

        self.ui.noConfigLabel.hide()
        self.ui.oldConfigLabel.hide()
        self.ui.initiate.setEnabled(False)
        self.ui.inPath.setStyleSheet('')

        ipath = self.ui.inPath.text()
        if not os.path.isdir(ipath):
            self.ui.inPath.setStyleSheet(warnStyle)
            return

        cfgName = ''
        attempt = 0
        while True:
            n_cfgName = ipath + '/acquisition.%i.configuration' % attempt
            if os.path.exists(n_cfgName):
                cfgName = n_cfgName
            else:
                break
            attempt += 1
        if not cfgName:  # one more attempt for little earlier code
            cfgName = os.popen(
                'ls ' + ipath + '/acquisition.*config* | sort -V | tail -n 1'
                ).read().strip("\n")
        if not cfgName:
            self.ui.noConfigLabel.show()
            return

        cfg = QSettings(cfgName, QSettings.IniFormat)
        if not cfg.value('version'):
            self.ui.oldConfigLabel.show()
            return

        scanRange = cfg.value('scan/range', type=int)
        self.ui.scanRange.setText(str(scanRange))
        self.ui.notFnS.setVisible(scanRange >= 360)
        self.ui.projections.setText(cfg.value('scan/steps'))

        doSerial = cfg.value('doserialscans', type=bool)
        self.ui.yIndependent.setVisible(doSerial)
        self.ui.ylabel.setVisible(doSerial)
        self.ui.ys.setVisible(doSerial)
        self.ui.ys.setText(cfg.value('serial/outerseries/nofsteps'))

        do2D = doSerial and cfg.value('serial/2d', type=bool)
        self.ui.zIndependent.setVisible(do2D)
        self.ui.zlabel.setVisible(do2D)
        self.ui.zs.setVisible(do2D)
        self.ui.zs.setText(cfg.value('serial/innearseries/nofsteps'))

        self.ui.initiate.setEnabled(os.path.isdir(self.ui.outPath.text())
                                    and (scanRange >= 360 or doSerial or do2D))

    @pyqtSlot()
    def on_outBrowse_clicked(self):
        newdir = QFileDialog.getExistingDirectory(self, "Processing directory",
                                                  self.ui.outPath.text())
        if newdir:
            self.ui.outPath.setText(newdir)

    @pyqtSlot(str)
    def on_outPath_textChanged(self):

        self.on_inPath_textChanged()  # to update initiate button state

        self.ui.outPath.setStyleSheet('')
        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.setTabEnabled(tabIdx, False)

        opath = self.ui.outPath.text()
        if not os.path.isdir(opath):
            self.ui.outPath.setStyleSheet(warnStyle)
            return

        initiatedFile = opath + '/.initstitch'
        if not os.path.exists(initiatedFile):
            return
        # below vars are from initiatedFile
        scanrange = 0
        pjs = 0
        zs = 0
        ys = 0
        fshift = 0
        width = 0
        hight = 0
        os.exec(open(initiatedFile).read())

        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.setTabEnabled(tabIdx, True)

        self.ui.scanRange.setText(str(scanrange))
        self.ui.notFnS.setVisible(scanrange >= 360)
        self.ui.notFnS.setChecked(fshift > 0)
        self.ui.projections.setText(pjs)

        doSerial = ys > 1
        self.ui.yIndependent.setVisible(doSerial)
        self.ui.ylabel.setVisible(doSerial)
        self.ui.ys.setVisible(doSerial)
        self.ui.ys.setText(ys)

        do2D = doSerial and zs > 1
        self.ui.zIndependent.setVisible(do2D)
        self.ui.zlabel.setVisible(do2D)
        self.ui.zs.setVisible(do2D)
        self.ui.zs.setText(zs)

        self.ui.imageSize.setText('%i (w) x %i (h)' % width % hight)
        self.ui.sCropTop.setMaximum(hight)
        self.ui.sCropBottom.setMaximum(hight)
        self.ui.sCropRight.setMaximum(width)
        self.ui.sCropLeft.setMaximum(width)
        self.ui.iStX.setRange(-width, width)
        self.ui.oStX.setRange(-width, width)
        self.ui.fStX.setRange(-width, width)
        self.ui.iStY.setRange(-hight, hight)
        self.ui.oStY.setRange(-hight, hight)
        self.ui.fStY.setRange(-hight, hight)
        self.ui.fCropTop.setMaximum(hight*max(ys, zs))
        self.ui.fCropBottom.setMaximum(hight*max(ys, zs))
        self.ui.fCropRight.setMaximum(width*max(ys, zs))
        self.ui.fCropLeft.setMaximum(width*max(ys, zs))

    @pyqtSlot()
    def on_initiate_clicked(self):

        if self.initproc.state():
            self.initproc.kill()
            return

        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.setTabEnabled(tabIdx, False)
        self.ui.initInfo.setEnabled(False)
        self.ui.initiate.setStyleSheet(warnStyle)
        self.ui.initiate.setText('Stop')

        command = ("imbl-initiate.sh "
                   + " -o " + self.ui.outPath.text()
                   + " -f " if self.ui.notFnS.isChecked() else ""
                   + " -y " if self.ui.yIndependent.isChecked() else ""
                   + " -z " if self.ui.zIndependent.isChecked() else ""
                   + " -e " if self.ui.noNewFF.isChecked() else ""
                   + self.ui.inPath.text())

        eloop = QEventLoop(self)
        self.initproc.finished.connect(eloop.quit)
        self.initproc.readyReadStandardOutput.connect(eloop.quit)
        self.initproc.readyReadStandardError.connect(eloop.quit)

        self.addToConsole("Executing command:")
        self.addToConsole(command)
        self.initproc.start("/bin/sh", ("-c", command))
        self.initproc.waitForStarted()
        while True:
            self.addOutToConsole(self.initproc.readAllStandardOutput()
                                 .data().decode(sys.getdefaultencoding()))
            self.addErrToConsole(self.initproc.readAllStandardError()
                                 .data().decode(sys.getdefaultencoding()))
            if self.initproc.state():
                eloop.exec_()
            else:
                break
        self.addToConsole("Command stopped with exit status %i"
                          % self.initproc.exitCode())

        self.ui.initInfo.setEnabled(True)
        self.ui.initiate.setStyleSheet('')
        self.ui.initiate.setText('Initiate')

        self.on_outPath_textChanged()


app = QApplication(sys.argv)
my_mainWindow = MainWindow()
my_mainWindow.show()
sys.exit(app.exec_())
