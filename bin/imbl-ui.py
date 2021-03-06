#!/usr/bin/env python3

import sys
import os
import re

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot, QSettings, QProcess, QEventLoop, QTimer
from PyQt5.QtWidgets import QFileDialog, QApplication
from PyQt5.uic import loadUi

from subprocess import Popen
from pathlib import Path
# sys.path.append("..")
# from share import ui_imbl

execPath = os.path.dirname(os.path.realpath(__file__)) + os.path.sep
warnStyle = 'background-color: rgba(255, 0, 0, 128);'


class MainWindow(QtWidgets.QMainWindow):

    configName = ".imbl-ui"
    etcConfigName = os.path.join(Path.home(), configName)
    amLoading = False

    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = loadUi(execPath + '../share/imblproc/imbl-ui.ui', self)
        # self.ui = ui_imbl.Ui_MainWindow()
        # self.ui.setupUi(self)
        self.on_individualIO_toggled()
        self.on_xtractIn_textChanged()

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
        self.ui.splitSize.editingFinished.connect(self.ui.recalculateSplit)
        self.ui.irregularSplit.toggled.connect(self.ui.recalculateSplit)

        saveBtn = QtWidgets.QPushButton("Save", self)
        saveBtn.setFlat(True)
        saveBtn.clicked.connect(self.saveNewConfiguration)
        self.ui.statusBar().addPermanentWidget(saveBtn)

        loadBtn = QtWidgets.QPushButton("Load", self)
        loadBtn.setFlat(True)
        loadBtn.clicked.connect(self.loadNewConfiguration)
        self.ui.statusBar().addPermanentWidget(loadBtn)

        self.doYst = False
        self.doZst = False
        self.doFnS = False

        self.configObjects = (
            self.ui.individualIO,
            self.ui.expPath,
            self.ui.expSample,
            self.ui.inPath,
            self.ui.outPath,  # must come early in loading
            self.ui.ignoreLog,
            self.ui.step,
            self.ui.notFnS,
            self.ui.yIndependent,
            self.ui.zIndependent,
            self.ui.noNewFF,
            self.ui.procAfterInit,
            self.ui.denoise,
            self.ui.imageMagick,
            self.ui.rotate,
            self.ui.sCropTop,
            self.ui.sCropBottom,
            self.ui.sCropRight,
            self.ui.sCropLeft,
            self.ui.xBin,
            self.ui.sameBin,  # must come between those two
            self.ui.yBin,
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
            self.ui.splitSize,
            self.ui.irregularSplit,
            self.ui.testSubDir,
            self.ui.noRecFF,
            self.ui.xtractAfter,
            self.ui.xtractIn,
            self.ui.minProj,
            self.ui.maxProj,
            self.ui.deleteClean
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

        self.ui.notFnS.clicked.connect(self.needReinitiation)
        self.ui.ignoreLog.clicked.connect(self.needReinitiation)
        self.ui.yIndependent.clicked.connect(self.needReinitiation)
        self.ui.zIndependent.clicked.connect(self.needReinitiation)
        self.ui.xtractAfter.toggled.connect(self.on_xtractIn_textChanged)
        self.ui.expUpdate.clicked.connect(self.on_expPath_textChanged)
        self.ui.ignoreLog.toggled.connect(self.on_inPath_textChanged)

        QtCore.QTimer.singleShot(100, self.loadConfiguration)

    def addToConsole(self, text, qcolor=None):
        if not text:
            return
        if not qcolor:
            qcolor = self.ui.console.palette().text().color()
        self.ui.console.setTextColor(qcolor)
        self.ui.console.append(str(text).strip('\n'))
        #self.ui.console.setText(text)

    def addOutToConsole(self, text):
        self.addToConsole(text, QtCore.Qt.blue)

    def addErrToConsole(self, text):
        self.addToConsole(text, QtCore.Qt.red)

    @pyqtSlot()
    def saveNewConfiguration(self):
        self.saveConfiguration("")

    @pyqtSlot()
    def saveConfiguration(self, fileName=etcConfigName):

        if self.amLoading:
            return

        if not fileName:
            newfile, _filter = QFileDialog.getSaveFileName(
                self, "IMBL processing configuration",
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

        config.beginWriteArray('splits')
        for crow in range(0, self.ui.splits.rowCount()-1):
            config.setArrayIndex(crow)
            config.setValue('pos', self.ui.splits.cellWidget(crow, 0).value())
        config.endArray()

    @pyqtSlot()
    def loadNewConfiguration(self):
        self.loadConfiguration("")

    @pyqtSlot()
    def loadConfiguration(self, fileName=etcConfigName):

        if not fileName:
            newfile, _filter = QFileDialog.getOpenFileName(
                self, "IMBL processing configuration",
                directory=self.ui.outPath.text())
            if newfile:
                fileName = newfile
        if not os.path.exists(fileName):
            return

        self.amLoading = True
        config = QSettings(fileName, QSettings.IniFormat)

        def valToLoad(wdg, nm):
            if isinstance(wdg, QtWidgets.QLineEdit):
                wdg.setText(config.value(oName, type=str))
            elif isinstance(wdg, QtWidgets.QCheckBox):
                wdg.setChecked(config.value(oName, type=bool))
            elif isinstance(wdg, QtWidgets.QAbstractSpinBox):
                wdg.setValue(config.value(oName, type=float))
            elif isinstance(wdg, QtWidgets.QComboBox):
                txt = config.value(oName, type=str)
                didx = wdg.findText(txt)
                if not didx < 0:
                    wdg.setCurrentIndex(didx)
        for swdg in self.configObjects:
            oName = swdg.objectName()
            if config.contains(oName):
                valToLoad(swdg, oName)
            if swdg is self.ui.outPath:
                self.on_outPath_textChanged()
            if swdg is self.ui.sameBin:
                self.on_sameBin_clicked()

        while self.ui.splits.rowCount() > 1:
                self.remFromSplit(0)
        splitsize = config.beginReadArray('splits')
        for crow in range(0, splitsize):
            config.setArrayIndex(crow)
            self.addToSplit(config.value('pos', type=int))
        config.endArray()
        self.recalculateSplit()

        self.amLoading = False

    def execInBg(self, proc):

        self.addToConsole("Executing command:")
        self.addToConsole(proc.program() + " "
                          + ' '.join([ar for ar in proc.arguments()]),
                          QtCore.Qt.green)
        if proc.workingDirectory() and \
           not os.path.samefile(proc.workingDirectory(), os.getcwd()):
            self.addToConsole("in ")
            self.addToConsole(os.path.realpath(proc.workingDirectory()), QtCore.Qt.green)
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

    @pyqtSlot()
    def needReinitiation(self):
        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.setTabEnabled(tabIdx, False)

    def update_initiate_state(self):
        self.ui.initiate.setEnabled(os.path.isdir(self.ui.inPath.text()) and
                                    (os.path.isdir(self.ui.outPath.text()) or
                                     not self.ui.individualIO.isChecked()))

    @pyqtSlot()
    @pyqtSlot(bool)
    def on_individualIO_toggled(self):
        ind = self.ui.individualIO.isChecked()
        self.ui.expPath.setVisible(not ind)
        self.ui.expLbl.setVisible(not ind)
        self.ui.expWdg.setVisible(not ind)
        self.ui.sampleWdg.setVisible(not ind)
        self.ui.expSampleLbl.setVisible(not ind)
        self.ui.inPath.setReadOnly(not ind)
        self.ui.inBrowse.setVisible(ind)
        self.ui.outPath.setReadOnly(not ind)
        self.ui.outBrowse.setVisible(ind)
        self.on_expPath_textChanged()
        self.on_outPath_textChanged()

    @pyqtSlot()
    def on_expBrowse_clicked(self):
        newdir = QFileDialog.getExistingDirectory(
            self, "Experiment directory", self.ui.expPath.text())
        if newdir:
            self.ui.expPath.setText(newdir)

    @pyqtSlot(bool)
    @pyqtSlot(str)
    def on_expPath_textChanged(self):

        if self.ui.individualIO.isChecked():
            return

        ciName = self.ui.inPath.text()
        self.ui.expPath.setStyleSheet('')
        self.ui.expSample.setEnabled(False)
        self.ui.expSample.setStyleSheet(warnStyle)
        self.ui.expSample.clear()

        epath = self.ui.expPath.text()
        if not os.path.isdir(epath):
            self.ui.expSample.addItem("Experiment does not exist")
            return
        eipath = os.path.join(epath, 'input')
        if not os.path.exists(eipath):
            self.ui.expSample.addItem("No input subdirectory")
            return

        self.ui.expSample.addItem("Loading...")
        self.update()
        QtCore.QCoreApplication.processEvents()
        samples = [name for name in sorted(os.listdir(eipath))
                   if os.path.isdir(os.path.join(eipath, name))]
        self.ui.expSample.clear()
        self.ui.expSample.setStyleSheet('')
        self.ui.expSample.addItems(samples)
        if ciName[:len(eipath)] == eipath:
            sample = ciName[len(eipath):].lstrip(os.path.sep)
            sidx = self.ui.expSample.findText(sample)
            if not sidx < 0:
                self.ui.expSample.setCurrentIndex(sidx)
        self.ui.expSample.setEnabled(True)

    @pyqtSlot(str)
    def on_expSample_currentTextChanged(self):
        if self.ui.individualIO.isChecked() or self.ui.expSample.styleSheet():
            return
        epath = self.ui.expPath.text()
        sample = self.ui.expSample.currentText()
        self.ui.inPath.setText(os.path.join(epath, 'input', sample))
        self.ui.outPath.setText(os.path.join(epath, 'output', sample))

    @pyqtSlot()
    def on_inBrowse_clicked(self):
        newdir = QFileDialog.getExistingDirectory(
            self, "Sample directory", os.path.dirname(self.ui.inPath.text()))
        if newdir:
            self.ui.inPath.setText(newdir)

    @pyqtSlot(str)
    @pyqtSlot(bool)
    def on_inPath_textChanged(self):

        QtCore.QCoreApplication.processEvents()  # to update ui.inPath
        self.needReinitiation()
        self.ui.noConfigLabel.hide()
        self.ui.oldConfigLabel.hide()
        self.ui.initiate.setEnabled(False)
        self.ui.inPath.setStyleSheet('')
        self.ui.ignoreLog.hide()

        ipath = self.ui.inPath.text()
        if not os.path.isdir(ipath):
            self.ui.inPath.setStyleSheet(warnStyle)
            return

        cfgName = ''
        attempt = 0
        while True:
            n_cfgName = os.path.join(ipath,
                                     'acquisition.%i.configuration' % attempt)
            if os.path.exists(n_cfgName):
                cfgName = n_cfgName
            else:
                break
            attempt += 1
        if not cfgName:  # one more attempt for little earlier code
            cfgName = os.popen('ls ' + ipath + os.sep + 'acquisition.*conf*' +
                               ' | sort -V | tail -n 1').read().strip("\n")
        if not cfgName:
            self.ui.noConfigLabel.show()
            return

        cfg = QSettings(cfgName, QSettings.IniFormat)
        if not cfg.value('version'):
            self.ui.oldConfigLabel.show()
            return

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

        fromlog = False
        logName = re.sub(r"\.config.*", ".log", cfgName)
        self.ui.ignoreLog.setVisible(os.path.exists(logName))
        logInfo = []
        if os.path.exists(logName) and not self.ui.ignoreLog.isChecked() :
            logInfo = os.popen('cat "' + logName + '"'
                                + ' | ' + execPath + 'imbl-log.py -i'
                                + ' | grep \'# Common\' '
                                + ' | cut -d\' \' -f 4- ' ) \
                            .read().strip("\n").split()
            if len(logInfo) == 3 :
                fromlog = True

        scanrange = float(logInfo[0]) if fromlog else cfg.value('scan/range', type=float)
        self.ui.scanRange.setText(str(scanrange))
        self.ui.notFnS.setVisible(scanrange >= 360)
        projections = int(logInfo[1]) if fromlog else cfg.value('scan/steps', type=int)
        self.ui.projections.setText(str(projections))
        step = float(logInfo[2]) if fromlog else scanrange / projections
        self.ui.step.setText(str(step))

        self.update_initiate_state()


    @pyqtSlot()
    def on_outBrowse_clicked(self):
        newdir = QFileDialog.getExistingDirectory(
            self, "Output directory", os.path.dirname(self.ui.outPath.text()))
        if newdir:
            self.ui.outPath.setText(newdir)


    @pyqtSlot()
    @pyqtSlot(str)
    def on_outPath_textChanged(self):

        self.update_initiate_state()
        self.needReinitiation()

        opath = self.ui.outPath.text()
        if not os.path.isdir(opath):
            self.ui.outPath.setStyleSheet(
                warnStyle if self.ui.individualIO.isChecked() else "")
            return
        self.ui.outPath.setStyleSheet('')

        initiatedFile = os.path.join(opath, '.initstitch')
        if not os.path.exists(initiatedFile):
            return
        initDict = dict()
        try:
            exec(open(initiatedFile).read(), initDict)
        except :
            self.addErrToConsole("Corrupt init file \"%s\"" % initiatedFile)
            return
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
            step = initDict['step'] if 'step' in initDict else self.ui.step.text()
        except KeyError:
            return

        self.ui.inPath.setText(ipath)

        self.doFnS = scanrange >= 360 and fshift > 0
        self.ui.scanRange.setText(str(scanrange))
        self.ui.step.setText(str(step))
        self.ui.notFnS.setChecked(not self.doFnS)
        self.ui.fStLbl.setVisible(self.doFnS)
        self.ui.fStWdg.setVisible(self.doFnS)
        self.ui.projections.setText(str(pjs))

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

        self.ui.iStX.setRange(-2*width, 2*width)
        self.ui.iStY.setRange(-2*hight, 2*hight)
        self.ui.oStX.setRange(-2*width, 2*width)
        self.ui.oStY.setRange(-2*hight, 2*hight)
        self.ui.fStX.setRange(-2*width, 2*width)
        self.ui.fStY.setRange(-2*hight, 2*hight)
        msz = max(1,ys, zs)
        self.ui.splitSize.setMaximum(hight*msz)
        self.ui.fCropTop.setMaximum(hight*msz)
        self.ui.fCropBottom.setMaximum(hight*msz)
        self.ui.fCropRight.setMaximum(width*msz)
        self.ui.fCropLeft.setMaximum(width*msz)
        self.ui.recalculateSplit()

        self.ui.testSubDir.clear()
        sds = 'subdirs' in initDict
        self.ui.testSubDir.addItems(filemask.split() if sds else (".",))
        self.ui.testSubDir.setVisible(sds)
        self.ui.testSubDirLabel.setVisible(sds)
        self.ui.procThis.setVisible(sds)
        self.ui.testProjection.setMaximum(pjs)
        self.ui.minProj.setMaximum(pjs)
        self.ui.maxProj.setMaximum(pjs)

        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.setTabEnabled(tabIdx, True)


    initproc = QProcess()


    @pyqtSlot()
    def on_initiate_clicked(self):

        if self.initproc.state():
            self.initproc.kill()
            return

        self.needReinitiation()
        self.ui.initInfo.setEnabled(False)
        self.ui.initiate.setStyleSheet(warnStyle)
        self.ui.initiate.setText('Stop')

        opath = self.ui.outPath.text()
        if not self.ui.individualIO.isChecked() and \
           not os.path.isdir(opath):
            os.makedirs(opath, exist_ok=True)

        command = execPath + "imbl-init.sh "
        if self.ui.notFnS.isChecked():
            command += " -f "
        if self.ui.yIndependent.isChecked():
            command += " -y "
        if self.ui.zIndependent.isChecked():
            command += " -z "
        if self.ui.noNewFF.isChecked():
            command += " -e "
        if not self.ui.ignoreLog.isChecked() and self.ui.ignoreLog.isVisible() :
            command += " -l "        
        command += " -o \"%s\" " % opath
        command += self.ui.inPath.text()

        self.initproc.setProgram("/bin/sh")
        self.initproc.setArguments(("-c", command))
        self.execInBg(self.initproc)

        self.ui.initInfo.setEnabled(True)
        self.ui.initiate.setStyleSheet('')
        self.ui.initiate.setText('Initiate')

        self.on_outPath_textChanged()

        if self.ui.procAfterInit.isChecked():
            self.on_procAll_clicked()


    @pyqtSlot()
    def on_sameBin_clicked(self):
        if (self.ui.sameBin.isChecked()):
            self.ui.yBin.setValue(self.ui.xBin.value())
            self.ui.xBin.valueChanged.connect(self.ui.yBin.setValue)
        else:
            try:
                self.ui.xBin.valueChanged.disconnect(self.ui.yBin.setValue)
            except TypeError:
                pass
        self.ui.yBin.setEnabled(not self.ui.sameBin.isChecked())


    @pyqtSlot()
    def addToSplit(self, pos=0):
        nrow = self.ui.splits.rowCount() - 1
        self.ui.splits.insertRow(nrow)
        poss = QtWidgets.QSpinBox(self)
        poss.setMaximum(self.ui.splitSize.maximum())
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


    @pyqtSlot()
    def recalculateSplit(self):
        self.ui.splitSize.setEnabled(not self.ui.irregularSplit.isChecked())
        self.ui.splits.setEnabled(self.ui.irregularSplit.isChecked())
        if self.ui.irregularSplit.isChecked() :
            return
        pixels = self.ui.splitSize.value()
        points = 0  if  pixels == 0  else  self.ui.splitSize.maximum() // pixels        
        for cpnt in range(points) :
            cpos = (cpnt + 1 ) * pixels
            pointWdg = self.ui.splits.cellWidget(cpnt,0)
            if isinstance(pointWdg, QtWidgets.QSpinBox) :
                pointWdg.setValue(cpos)
            else :
                self.addToSplit(cpos)
        while self.ui.splits.rowCount() - 1 != points :
            self.remFromSplit(self.ui.splits.rowCount()-2)


    stitchproc = QProcess()

    def common_test_proc(self, ars, wdir, actButton):

        if self.stitchproc.state():
            self.stitchproc.kill()
            return

        prms = str()
        if self.doYst or self.doZst:
            if self.doZst:
                prms += "-g %f,%f " % (
                  self.ui.iStX.value(), self.ui.iStY.value())
            else:
                prms += "-g %f,%f " % (
                  self.ui.oStX.value(), self.ui.oStY.value())
        if self.doYst and self.doZst:
            prms += "-G %f,%f " % (
                self.ui.oStX.value(), self.ui.oStY.value())
        if self.doFnS:
            prms += "-f %f,%f " % (
                self.ui.fStX.value(), self.ui.fStY.value())
        if 1 != self.ui.xBin.value() * self.ui.yBin.value():
            prms += "-b %i,%i " % (
                self.ui.xBin.value(), self.ui.yBin.value())
        if self.ui.denoise.value():
            prms += "-n %i " % self.ui.denoise.value()
        if self.ui.imageMagick.text():
            prms += "-i \"%s\" " % self.ui.imageMagick.text()
        if 0.0 != self.ui.rotate.value():
            prms += "-r %f " % self.ui.rotate.value()
        if self.ui.splits.rowCount() > 1:
            splits = []
            for crow in range(0, self.ui.splits.rowCount()-1):
                splits.append(self.ui.splits.cellWidget(crow, 0).value())
            splits.sort()
            splits = set(splits)
            prms += "-s %s " % ','.join([str(splt) for splt in splits])
        crops = (self.ui.sCropTop.value(), self.ui.sCropLeft.value(),
                 self.ui.sCropBottom.value(), self.ui.sCropRight.value())
        if sum(crops):
            prms += " -c %i,%i,%i,%i " % crops
        crops = (self.ui.fCropTop.value(), self.ui.fCropLeft.value(),
                 self.ui.fCropBottom.value(), self.ui.fCropRight.value())
        if sum(crops):
            prms += " -C %i,%i,%i,%i " % crops
        prms += "-v"
        prms += ars

        disableWdgs = (*self.configObjects,
                       self.ui.procAll, self.ui.procThis, self.ui.test,
                       self.ui.splits, self.ui.initiate)
        for wdg in disableWdgs:
            if wdg is not actButton:
                wdg.setEnabled(False)
        actText = actButton.text()
        actButton.setText('Stop')
        actButton.setStyleSheet(warnStyle)

        self.stitchproc.setProgram("/bin/sh")
        self.stitchproc.setArguments(("-c", execPath + "imbl-proc.sh " + prms))
        self.stitchproc.setWorkingDirectory(wdir)
        self.execInBg(self.stitchproc)

        for wdg in disableWdgs:
            wdg.setEnabled(True)
        actButton.setText(actText)
        actButton.setStyleSheet("")
        self.on_sameBin_clicked()  # to correct state of the yBin
        self.on_xtractIn_textChanged()  # to correct state of process all
        self.update_initiate_state()

    @pyqtSlot()
    def on_test_clicked(self):
        ars = (" -t %i" % self.ui.testProjection.value())
        wdir = os.path.join(self.ui.outPath.text(),
                            self.ui.testSubDir.currentText())
        self.common_test_proc(ars, wdir, self.ui.test)

    def procParams(self):
        ars = " -d " if self.ui.noRecFF.isChecked() else ""
        ars += (" -x \"%s\" " % self.ui.xtractIn.text()
                if self.ui.xtractAfter.isChecked() else "")
        ars += " -w " if self.ui.deleteClean.isChecked() else ""
        minProj = self.ui.minProj.value()
        maxProj = self.ui.maxProj.value()
        if maxProj == self.ui.maxProj.minimum():
            maxProj = int(self.ui.projections.text())
        ars += " -m %i -M %i " % (minProj, maxProj)
        ars += " all"
        return ars

    @pyqtSlot()
    def on_procAll_clicked(self):
        wdir = self.ui.outPath.text()
        self.saveConfiguration(os.path.join(wdir, self.configName))
        self.common_test_proc(self.procParams(), wdir, self.ui.procAll)

    @pyqtSlot()
    def on_procThis_clicked(self):
        wdir = os.path.join(self.ui.outPath.text(),
                            self.ui.testSubDir.currentText())
        self.saveConfiguration(os.path.join(wdir, self.configName))
        self.common_test_proc(self.procParams(), wdir, self.ui.procThis)

    @pyqtSlot()
    def on_xtractBrowse_clicked(self):
        newfile, _filter = QFileDialog.getOpenFileName(self,
            "Xtract parameters file", os.path.dirname(self.ui.xtractIn.text()))
        if newfile:
            self.ui.xtractIn.setText(newfile)

    xtrproc = QProcess()

    @pyqtSlot()
    def on_xtractExecute_clicked(self):
        if self.xtrproc.state():
            self.xtrproc.kill()
            return

        xtrText = self.ui.xtractExecute.text()
        self.ui.xtractExecute.setText('Stop')
        self.ui.xtractExecute.setStyleSheet(warnStyle)

        self.xtrproc.setProgram("/bin/sh")
        self.xtrproc.setArguments(("-c",
                                   execPath + "imbl-xtract-wrapper.sh " +
                                   self.ui.xtractIn.text() + " clean rec32fp"))
        wdir = os.path.join(self.ui.outPath.text(),
                            self.ui.testSubDir.currentText())
        self.xtrproc.setWorkingDirectory(wdir)
        self.execInBg(self.xtrproc)

        self.ui.xtractExecute.setText(xtrText)
        self.ui.xtractExecute.setStyleSheet("")

    @pyqtSlot()
    @pyqtSlot(str)
    def on_xtractIn_textChanged(self):
        doXtract = self.ui.xtractAfter.isChecked()
        xparfOK = os.path.exists(self.ui.xtractIn.text()) or not doXtract
        self.ui.xtractWdg.setVisible(doXtract)
        self.ui.xtractInabel.setVisible(doXtract)
        self.ui.xtractIn.setStyleSheet("" if xparfOK else warnStyle)
        self.ui.procThis.setEnabled(xparfOK)
        self.ui.procAll.setEnabled(xparfOK)

    def onMinMaxProjectionChanged(self):
        minProj = self.ui.minProj.value()
        maxProj = self.ui.maxProj.value()
        if maxProj == self.ui.maxProj.minimum():
            maxProj = int(self.ui.projections.text())
        nstl = "" if minProj <= maxProj else warnStyle
        self.ui.minProj.setStyleSheet(nstl)
        self.ui.maxProj.setStyleSheet(nstl)

    @pyqtSlot(int)
    def on_minProj_valueChanged(self):
        self.onMinMaxProjectionChanged()

    @pyqtSlot(int)
    def on_maxProj_valueChanged(self):
        self.onMinMaxProjectionChanged()


app = QApplication(sys.argv)
my_mainWindow = MainWindow()
my_mainWindow.show()
sys.exit(app.exec_())
