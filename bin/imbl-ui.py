#!/usr/bin/env python3

import sys
import os

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot, QSettings, QProcess, QEventLoop
from PyQt5.QtWidgets import QFileDialog, QApplication
from PyQt5.uic import loadUi

from subprocess import Popen
from pathlib import Path

# sys.path.append("..")
# from share import ui_imbl

execPath = os.path.dirname(os.path.realpath(__file__)) + os.path.sep
warnStyle = 'background-color: rgba(255, 0, 0, 128);'


class MainWindow(QtWidgets.QMainWindow):

    configName = str(Path.home()) + "/.imbl-ui"
    amLoading = False

    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = loadUi('../share/imbl-ui.ui', self)
        # self.ui = ui_imbl.Ui_MainWindow()
        # self.ui.setupUi(self)

        self.ui.splits.horizontalHeader().setStretchLastSection(False)
        self.ui.splits.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch)
        self.ui.splits.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Fixed)
        self.ui.splits.insertRow(0)
        butt = QtWidgets.QToolButton(self)
        butt.setText('add')
        butt.clicked.connect(self.addToSplit)
        self.ui.splits.setCellWidget(0, 0, butt)
        self.ui.splits.setSpan(0, 0, 1, 2)

        self.configObjects = (
            self.ui.inPath,
            self.ui.outPath,  # must come early in loading
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
            self.ui.testSubDir,
            self.ui.noRecFF
        )

        self.loadConfiguration()

        for swdg in self.configObjects:
            if isinstance(swdg, QtWidgets.QLineEdit):
                swdg.textChanged.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QCheckBox):
                swdg.toggled.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QAbstractSpinBox):
                swdg.valueChanged.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QComboBox):
                swdg.currentTextChanged.connect(self.saveConfiguration)

        self.ui.notFnS.clicked.connect(self.needReinitiation)
        self.ui.yIndependent.clicked.connect(self.needReinitiation)
        self.ui.zIndependent.clicked.connect(self.needReinitiation)

        self.doYst = False
        self.doZst = False
        self.doFnS = False

        self.addToConsole("Am ready.")

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
            elif isinstance(wdg, QtWidgets.QComboBox):
                return wdg.currentText()
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
            elif isinstance(wdg, QtWidgets.QComboBox):
                didx = wdg.findText(str(val))
                if not didx < 0:
                    wdg.setCurrentIndex(didx)
        for swdg in self.configObjects:
            oName = swdg.objectName()
            if config.contains(oName):
                valToLoad(swdg, config.value(oName))
            if swdg is self.ui.outPath:  # must come early in loading
                self.on_outPath_textChanged()

        while self.ui.splits.rowCount() > 1:
                self.remFromSplit(0)
        splitsize = config.beginReadArray('splits')
        for crow in range(0, splitsize):
            config.setArrayIndex(crow)
            self.addToSplit(config.value('pos', type=int))
        config.endArray()

        self.amLoading = False

    def execInBg(self, proc):

        self.addToConsole("Executing command:")
        self.addToConsole(proc.program() + " "
                          + ' '.join([ar for ar in proc.arguments()]))
        if proc.workingDirectory() and \
           not os.path.samefile(proc.workingDirectory(), os.getcwd()):
            self.addToConsole("in \"%s\""
                              % os.path.realpath(proc.workingDirectory()))

        eloop = QEventLoop(self)
        proc.finished.connect(eloop.quit)
        proc.readyReadStandardOutput.connect(eloop.quit)
        proc.readyReadStandardError.connect(eloop.quit)

        proc.start()
        proc.waitForStarted(500)
        while True:
            self.addOutToConsole(proc.readAllStandardOutput()
                                 .data().decode(sys.getdefaultencoding()))
            self.addErrToConsole(proc.readAllStandardError()
                                 .data().decode(sys.getdefaultencoding()))
            if proc.state():
                eloop.exec_()
            else:
                break
        self.addToConsole("Stopped with exit status %i" % proc.exitCode())


    def needReinitiation(self):
        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.setTabEnabled(tabIdx, False)

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

        scanrange = cfg.value('scan/range', type=float)
        self.ui.scanRange.setValue(scanrange)
        self.ui.notFnS.setVisible(scanrange >= 360)
        self.ui.projections.setValue(cfg.value('scan/steps', type=int))

        serialScan = cfg.value('doserialscans', type=bool)
        self.ui.yIndependent.setVisible(serialScan)
        self.ui.ylabel.setVisible(serialScan)
        self.ui.ys.setVisible(serialScan)
        self.ui.ys.setValue(cfg.value('serial/outerseries/nofsteps', type=int))

        twodScan = serialScan and cfg.value('serial/2d', type=bool)
        self.ui.zIndependent.setVisible(twodScan)
        self.ui.zlabel.setVisible(twodScan)
        self.ui.zs.setVisible(twodScan)
        self.ui.zs.setValue(cfg.value('serial/innearseries/nofsteps', type=int))

        self.ui.initiate.setEnabled(
            os.path.isdir(self.ui.outPath.text())
            and (scanrange >= 360 or serialScan or twodScan))

    @pyqtSlot()
    def on_outBrowse_clicked(self):
        newdir = QFileDialog.getExistingDirectory(
            self, "Processing directory", self.ui.outPath.text())
        if newdir:
            self.ui.outPath.setText(newdir)

    @pyqtSlot(str)
    def on_outPath_textChanged(self):

        self.on_inPath_textChanged()  # to update initiate button state
        self.needReinitiation()

        opath = self.ui.outPath.text()
        if not os.path.isdir(opath):
            self.ui.outPath.setStyleSheet(warnStyle)
            return
        self.ui.outPath.setStyleSheet('')

        initiatedFile = opath + '/.initstitch'
        if not os.path.exists(initiatedFile):
            return
        initDict = dict()
        exec(open(initiatedFile).read(), initDict)
        try:
            filemask = initDict['filemask']
            ipath = initDict['ipath']
            scanrange = initDict['scanrange']
            width = initDict['width']
            hight = initDict['hight']
            fshift = initDict['fshift']
            pjs = initDict['pjs']
            ys = initDict['ys']
            zs = initDict['zs']
            ystitch = initDict['ystitch']
            zstitch = initDict['zstitch']
        except KeyError:
            return

        self.ui.inPath.setText(ipath)

        self.doFnS = scanrange >= 360 and fshift > 0
        self.ui.scanRange.setValue(scanrange)
        self.ui.notFnS.setChecked(not self.doFnS)
        self.ui.fStLbl.setVisible(self.doFnS)
        self.ui.fStWdg.setVisible(self.doFnS)
        self.ui.projections.setValue(pjs)

        self.doYst = ys > 1 and ystitch > 1
        self.ui.yIndependent.setChecked(not self.doYst)
        self.ui.ys.setValue(ys)
        self.ui.oStLbl.setVisible(self.doYst)
        self.ui.oStWdg.setVisible(self.doYst)

        self.doZst = zs > 1 and zstitch > 1
        self.ui.zIndependent.setChecked(not self.doZst)
        self.ui.zs.setValue(zs)
        self.ui.iStLbl.setVisible(self.doZst)
        self.ui.iStWdg.setVisible(self.doZst)

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

        self.ui.testSubDir.clear()
        sds = 'subdirs' in initDict
        self.ui.testSubDir.addItems(filemask.split() if sds else (".",))
        self.ui.testSubDir.setVisible(sds)
        self.ui.testSubDirLabel.setVisible(sds)
        self.ui.testProjection.setMaximum(pjs)

        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.setTabEnabled(tabIdx, True)

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

        command = execPath + "imbl-init.sh "
        if self.ui.notFnS.isChecked():
            command += " -f "
        if self.ui.yIndependent.isChecked():
            command += " -y "
        if self.ui.zIndependent.isChecked():
            command += " -z "
        if self.ui.noNewFF.isChecked():
            command += " -e "
        command += " -o \"%s\" " % self.ui.outPath.text()
        command += self.ui.inPath.text()

        self.initproc.setProgram("/bin/sh")
        self.initproc.setArguments(("-c", command))
        self.execInBg(self.initproc)

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
                    break
        elif row < self.ui.splits.rowCount()-1:
            self.ui.splits.cellWidget(row, 0).destroy()
            self.ui.splits.cellWidget(row, 1).destroy()
            self.ui.splits.removeRow(row)
        self.saveConfiguration()

    def stitchparams(self):
        params = str()
        if self.doYst or self.doZst:
            params += "-g %i,%i " % (
                self.ui.oStX.value(), self.ui.oStX.value())
        if self.doYst and self.doZst:
            params += "-G %i,%i " % (
                self.ui.iStX.value(), self.ui.iStX.value())
        if self.doFnS:
            params += "-f %i,%i " % (
                self.ui.fStX.value(), self.ui.fStX.value())
        if 1 != self.ui.xBin.value() * self.ui.yBin.value():
            params += "-b %i,%i " % (
                self.ui.xBin.value(), self.ui.yBin.value())
        if self.ui.denoise.value():
            params += "-n %i " % self.ui.denoise.value()
        if self.ui.imageMagick.text():
            params += "-i \"%s\" " % self.ui.imageMagick.text()
        if 0.0 != self.ui.rotate.value():
            params += "-r %d " % self.ui.rotate.value()
        if self.ui.splits.rowCount() > 1:
            splits = []
            for crow in range(0, self.ui.splits.rowCount()-1):
                splits.append(self.ui.splits.cellWidget(crow, 0).value())
            splits.sort()
            splits = set(splits)
            params += "-s %s " % ','.join([str(splt) for splt in splits])
        crops = (self.ui.sCropTop.value(), self.ui.sCropLeft.value(),
                 self.ui.sCropBottom.value(), self.ui.sCropRight.value())
        if sum(crops):
            params += " -c %i,%i,%i,%i " % crops
        crops = (self.ui.fCropTop.value(), self.ui.fCropLeft.value(),
                 self.ui.fCropBottom.value(), self.ui.fCropRight.value())
        if sum(crops):
            params += " -C %i,%i,%i,%i " % crops
        return params

    stitchproc = QProcess()

    @pyqtSlot()
    def on_test_clicked(self):

        if self.stitchproc.state():
            self.stitchproc.kill()
            return

        disableWdgs = (*self.configObjects,
                       self.ui.splits, self.ui.initiate, self.ui.proc)
        for wdg in disableWdgs:
            wdg.setEnabled(False)
        self.ui.test.setStyleSheet(warnStyle)
        testButText = self.ui.test.text()
        self.ui.test.setText('Stop')

        command = (execPath + "imbl-proc.sh "
                   + " -t "
                   + self.stitchparams()
                   + " %i" % self.ui.testProjection.value())

        self.stitchproc.setProgram("/bin/sh")
        self.stitchproc.setArguments(("-c", command))
        self.stitchproc.setWorkingDirectory(
            self.ui.outPath.text() + "/" + self.ui.testSubDir.currentText())
        self.execInBg(self.stitchproc)

        for wdg in disableWdgs:
            wdg.setEnabled(True)
        self.ui.test.setStyleSheet("")
        self.ui.test.setText(testButText)
        self.on_inPath_textChanged()  # to correct state of self.ui.initiate

    @pyqtSlot()
    def on_proc_clicked(self):

        if self.stitchproc.state():
            self.stitchproc.kill()
            return

        disableWdgs = (*self.configObjects,
                       self.ui.splits, self.ui.initiate, self.ui.test)
        for wdg in disableWdgs:
            wdg.setEnabled(False)
        self.ui.proc.setStyleSheet(warnStyle)
        procButText = self.ui.proc.text()
        self.ui.proc.setText('Stop')

        command = (execPath + "imbl-proc.sh "
                   + self.stitchparams()
                   + (" -d " if self.ui.noRecFF.isChecked() else "")
                   + " all")

        self.stitchproc.setProgram("/bin/sh")
        self.stitchproc.setArguments(("-c", command))
        self.stitchproc.setWorkingDirectory(self.ui.outPath.text())
        self.execInBg(self.stitchproc)

        for wdg in disableWdgs:
            wdg.setEnabled(True)
        self.ui.proc.setStyleSheet("")
        self.ui.proc.setText(procButText)
        self.on_inPath_textChanged()  # to correct state of self.ui.initiate


app = QApplication(sys.argv)
my_mainWindow = MainWindow()
my_mainWindow.show()
sys.exit(app.exec_())
