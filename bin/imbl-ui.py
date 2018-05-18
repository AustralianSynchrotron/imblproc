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
    amLoading = False

    def __init__(self):
        super(MainWindow, self).__init__()
        # self.ui = loadUi('../share/imbl-ui.ui', self)
        self.ui = ui_imbl.Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.splits.horizontalHeader().setStretchLastSection(False)
        self.ui.splits.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch)
        self.ui.splits.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Fixed)
        self.ui.splits.insertRow(0)
        butt = QtWidgets.QToolButton(self)
        butt.setText('add')
        butt.clicked.connect(self.addToSplit)
        self.ui.splits.setCellWidget(0, 1, butt)

        self.configObjects = (
            self.ui.inPath,
            self.ui.outPath,
            self.ui.notFnS,
            self.ui.yIndependent,
            self.ui.zIndependent,
            self.ui.noNewFF,
            self.ui.denoise,
            self.ui.imageMagick,
            self.ui.rotate,
            self.ui.sCropTop,
            self.ui.sCropBottom,
            self.ui.sCropRight,
            self.ui.sCropLeft,
            self.ui.xBin,
            self.ui.yBin,
            self.ui.sameBin,
            self.ui.iStX,
            self.ui.iStY,
            self.ui.oStX,
            self.ui.oStY,
            self.ui.fStX,
            self.ui.fStY,
            self.ui.fCropTop,
            self.ui.fCropBottom,
            self.ui.fCropRight,
            self.ui.fCropLeft,
            self.ui.testProjection,
            self.ui.testY,
            self.ui.testZ,
            self.ui.noRecFF
        )

        self.loadConfiguration()
        self.on_outPath_textChanged()

        for swdg in self.configObjects:
            if isinstance(swdg, QtWidgets.QLineEdit):
                swdg.textChanged.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QCheckBox):
                swdg.toggled.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QAbstractSpinBox):
                swdg.valueChanged.connect(self.saveConfiguration)

        self.doSerial = False
        self.do2D = False

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
        
        if self.amLoading:
            return
        config = QSettings(fileName, QSettings.IniFormat)

        def valToSave(wdg):
            if isinstance(wdg, QtWidgets.QLineEdit):
                return wdg.text()
            elif isinstance(wdg, QtWidgets.QCheckBox):
                return wdg.isChecked()
            elif isinstance(wdg, QtWidgets.QAbstractSpinBox):
                return wdg.value()
        for swdg in self.configObjects:
            config.setValue(swdg.objectName(), valToSave(swdg))

        config.beginWriteArray('splits')
        for crow in range(0, self.ui.splits.rowCount()-1):
            config.setArrayIndex(crow)
            config.setValue('pos', self.ui.splits.cellWidget(crow, 0).value())
        config.endArray()

    @pyqtSlot()
    def loadConfiguration(self, fileName=configName):
        
        if not os.path.exists(fileName):
            return
        self.amLoading = True
        config = QSettings(fileName, QSettings.IniFormat)

        def valToLoad(wdg, val):
            if isinstance(wdg, QtWidgets.QLineEdit):
                wdg.setText(str(val))
            elif isinstance(wdg, QtWidgets.QCheckBox):
                wdg.setChecked(bool(val))
            elif isinstance(wdg, QtWidgets.QAbstractSpinBox):
                wdg.setValue(float(val))
        for swdg in self.configObjects:
            oName = swdg.objectName()
            if config.contains(oName):
                valToLoad(swdg, config.value(oName))

        self.remFromSplit(self.ui.splits.rowCount())  # clean splits
        splitsize = config.beginReadArray('splits')
        for crow in range(0, splitsize):
            config.setArrayIndex(crow)
            self.addToSplit(config.value('pos', type=int))
        config.endArray()

        self.amLoading = False

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
        self.ui.scanRange.setValue(scanRange)
        self.ui.notFnS.setVisible(scanRange >= 360)
        self.ui.projections.setValue(cfg.value('scan/steps', type=float))

        self.doSerial = cfg.value('doserialscans', type=bool)
        self.ui.yIndependent.setVisible(self.doSerial)
        self.ui.ylabel.setVisible(self.doSerial)
        self.ui.ys.setVisible(self.doSerial)
        self.ui.ys.setValue(cfg.value('serial/outerseries/nofsteps', type=int))

        self.do2D = self.doSerial and cfg.value('serial/2d', type=bool)
        self.ui.zIndependent.setVisible(self.do2D)
        self.ui.zlabel.setVisible(self.do2D)
        self.ui.zs.setVisible(self.do2D)
        self.ui.zs.setValue(cfg.value('serial/innearseries/nofsteps', type=int))

        self.ui.initiate.setEnabled(
            os.path.isdir(self.ui.outPath.text())
            and (scanRange >= 360 or self.doSerial or self.do2D))

    @pyqtSlot()
    def on_outBrowse_clicked(self):
        newdir = QFileDialog.getExistingDirectory(
            self, "Processing directory", self.ui.outPath.text())
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
        initDict = dict()
        exec(open(initiatedFile).read(), initDict)
        scanrange = initDict['scanrange']
        width = initDict['width']
        hight = initDict['hight']
        fshift = initDict['fshift']
        pjs = initDict['pjs']
        ys = initDict['ys']
        zs = initDict['zs']

        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.setTabEnabled(tabIdx, True)

        self.ui.scanRange.setValue(scanrange)
        self.ui.notFnS.setVisible(scanrange >= 360)
        self.ui.notFnS.setChecked(fshift > 0)
        self.ui.projections.setValue(pjs)
        self.on_notFnS_toggled()

        self.doSerial = ys > 1
        self.ui.yIndependent.setVisible(self.doSerial)
        self.ui.ylabel.setVisible(self.doSerial)
        self.ui.ys.setVisible(self.doSerial)
        self.ui.ys.setValue(ys)
        self.on_yIndependent_toggled()

        self.do2D = self.doSerial and zs > 1
        self.ui.zIndependent.setVisible(self.do2D)
        self.ui.zlabel.setVisible(self.do2D)
        self.ui.zs.setVisible(self.do2D)
        self.ui.zs.setValue(zs)
        self.on_zIndependent_toggled()

        self.ui.width.setValue(width)
        self.ui.hight.setValue(hight)
        self.ui.sCropTop.setMaximum(hight)
        self.ui.sCropBottom.setMaximum(hight)
        self.ui.sCropRight.setMaximum(width)
        self.ui.sCropLeft.setMaximum(width)

        self.ui.iStX.setRange(-width, width)
        self.ui.iStY.setRange(-hight, hight)
        self.ui.oStX.setRange(-width, width)
        self.ui.oStY.setRange(-hight, hight)
        self.ui.fStX.setRange(-width, width)
        self.ui.fStY.setRange(-hight, hight)
        self.ui.fCropTop.setMaximum(hight*max(ys, zs))
        self.ui.fCropBottom.setMaximum(hight*max(ys, zs))
        self.ui.fCropRight.setMaximum(width*max(ys, zs))
        self.ui.fCropLeft.setMaximum(width*max(ys, zs))

    @pyqtSlot()
    def on_notFnS_toggled(self):
        visible = self.ui.scanRange.value() >= 360 and \
            self.ui.notFnS.isChecked()
        self.ui.fStLbl.setVisible(visible)
        self.ui.fStWdg.setVisible(visible)

    @pyqtSlot()
    def on_yIndependent_toggled(self):
        visible = self.doSerial and self.ui.yIndependent.isChecked()
        self.ui.oStLbl.setVisible(visible)
        self.ui.oStWdg.setVisible(visible)

    @pyqtSlot()
    def on_zIndependent_toggled(self):
        visible = self.do2D and self.ui.zIndependent.isChecked()
        self.ui.iStLbl.setVisible(visible)
        self.ui.iStWdg.setVisible(visible)

    initproc = QProcess()

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

    @pyqtSlot()
    def addToSplit(self, pos=0):
        nrow = self.ui.splits.rowCount() - 1
        self.ui.splits.insertRow(nrow)
        poss = QtWidgets.QSpinBox(self)
        poss.setMaximum(self.ui.fCropTop.maximum())
        poss.setValue(pos)
        poss.editingFinished.connect(self.saveConfiguration)
        self.ui.splits.setCellWidget(nrow, 0, poss)
        butt = QtWidgets.QToolButton(self)
        butt.setText('delete')
        butt.clicked.connect(self.remFromSplit)
        self.ui.splits.setCellWidget(nrow, 1, butt)
        self.saveConfiguration()

    @pyqtSlot()
    def remFromSplit(self, row=-1):
        if row < 0:  # on rem click
            for crow in range(0, self.ui.splits.rowCount()-1):
                if self.ui.splits.cellWidget(crow, 1) is self.sender():
                    self.remFromSplit(crow)
                    break;
        elif row >= self.ui.splits.rowCount():  # remove all
            while self.ui.splits.rowCount() > 1:
                self.remFromSplit(0)
        else:
            self.ui.splits.cellWidget(row, 0).destroy()
            self.ui.splits.cellWidget(row, 1).destroy()
            self.ui.splits.removeRow(row)
        self.saveConfiguration()


app = QApplication(sys.argv)
my_mainWindow = MainWindow()
my_mainWindow.show()
sys.exit(app.exec_())
