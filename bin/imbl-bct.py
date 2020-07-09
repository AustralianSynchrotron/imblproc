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
from os.path import isdir, isfile, dirname, basename, exists, join

execPath = dirname(os.path.realpath(__file__)) + os.path.sep
dataPath = "/data/imbl" # on ASCI
#dataPath = "/mnt/ct" # test on dj-station
#dataPath = "/mnt/tmp/data" # real on dj-station from home
#dataPath = "/mnt/asci.data" # real on dj-station from work

badStyle = "color: rgb(255, 0, 0)"
#preProcExec = "/user/home/Desktop/IMBLPreProc" # Alaleh
#preProcExec = "/user/home/usr/bin/IMBLPreProc" # mine
preProcExec = join(execPath, "../share/imblproc/IMBLPreProc") # universal
configName = ".imbl-bct"

class DistDeps:
    def __init__(self, overlap, pixelSize, rPrime, ctFilter):
        self.__dict__.update(locals())
distances = { # distance : overlap, pixelSize, rPrime, ctFilter
    "0" : DistDeps("253", "99"  , "0"       , "4"),
    "6" : DistDeps("263", "94.8", "5748000", "0")}

energies = {# energy : delta-to-beta
    "26" : "200",
    "28" : "226",
    "30" : "253",
    "32" : "275",
    "34" : "300",
    "35" : "320",
    "37" : "350",
    "60" : "550"}


def setVText(lineEdit, val, tp=None) :
    lineEdit.setStyleSheet("")
    if not val:
        lineEdit.setText("<none>")
        lineEdit.setStyleSheet(badStyle + ";font:italic")
        return
    sval = ""
    if tp:
        try:
            cval = tp(val)
            sval = str(val)
        except ValueError:
            lineEdit.setStyleSheet(badStyle)
    if sval == lineEdit.text() :
        lineEdit.textChanged.emit(sval)
    else :
        lineEdit.setText(sval)



class MainWindow(QtWidgets.QMainWindow):

    etcConfigName = join(Path.home(), configName)
    amLoading = False
    logName = ""
    stepU = 0
    tilesWU = 1
    tilesHU = 1
    fakeInPath = ""
    stitchedPath = ""
    stitchedSizes = False
    proc = QProcess()


    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = loadUi(join(execPath, "../share/imblproc/imbl-bct.ui"), self)
        self.ui.tabWidget.tabBar().setExpanding(True)
        for errLabel in self.ui.findChildren(QtWidgets.QLabel, QtCore.QRegExp("^err\\w+")):
            self.showWdg(errLabel, False)
        self.ui.distanceR.addItems(list(distances))
        self.ui.energyR.addItems(list(energies))
        self.proc.setProgram("/bin/bash")

        if isdir(dataPath) :
            selection = self.ui.expSelect
            selection.setEnabled(False)
            selection.clear()
            selection.addItem("Loading...")
            self.update()
            QtCore.QCoreApplication.processEvents()
            for name in sorted(os.listdir(dataPath)) :
                expPath = join(dataPath, name)
                if isdir(join(expPath, "input")):
                    selection.addItem(name, expPath)
            selection.removeItem(0) # Loading...
            if selection.count() :
                selection.setEnabled(True)
            else :
                selection.addItem("<none>")

        self.configObjects = (
            self.ui.outAuto,
            self.ui.expPath,
            self.ui.inPath,
            self.ui.outPath,
            self.ui.trimL,
            self.ui.trimR,
            self.ui.trimT,
            self.ui.trimB,
            self.ui.energyR,
            self.ui.distanceR,
            self.ui.testRing,
            self.ui.set1,
            self.ui.set2,
            self.ui.set4 )
        for swdg in self.configObjects:
            if isinstance(swdg, QtWidgets.QLineEdit):
                swdg.textChanged.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QCheckBox):
                swdg.toggled.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QAbstractSpinBox):
                swdg.valueChanged.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QComboBox):
                swdg.currentTextChanged.connect(self.saveConfiguration)

        def onBrowse(target, lineEdit):
            newPath = QFileDialog.getExistingDirectory(self, target + " directory", lineEdit.text())
            setVText(lineEdit, newPath, str)
        def onSelect(lineEdit):
            newPath = self.sender().currentData()
            setVText(lineEdit, newPath, str)
        self.ui.expBrowse.clicked.connect(lambda: onBrowse("Experiment", self.ui.expPath))
        self.ui.expSelect.activated.connect(lambda: onSelect(self.ui.expPath))
        self.ui.expPath.textChanged.connect(self.onNewExperiment)
        self.ui.inBrowse.clicked.connect(lambda: onBrowse("Sample input", self.ui.inPath))
        self.ui.inSelect.activated.connect(lambda: onSelect(self.ui.inPath))
        self.ui.inPath.textChanged.connect(lambda: (self.onNewSample(), self.setOutPath()))
        self.ui.outBrowse.clicked.connect(lambda: onBrowse("Sample output", self.ui.outPath))
        self.ui.outAuto.toggled.connect(self.setOutPath)
        self.ui.outPath.textChanged.connect(lambda: self.setOutPath(False))
        self.ui.ring.valueChanged[int].connect(lambda val:
            self.ui.ring.setStyleSheet("" if not val or val % 2 else badStyle))
        self.ui.goStitch.clicked.connect(self.onStitch)
        self.ui.testRing.clicked.connect(self.onRec)
        self.ui.goRec.clicked.connect(self.onRec)

        QtCore.QTimer.singleShot(100, self.loadConfiguration)
        QTimer.singleShot(0, (lambda: self.resize(self.minimumSizeHint())))


    def showWdg(self, wdg, showme=True):
        wdg.setVisible(showme)
        QTimer.singleShot(0, (lambda: self.resize(self.minimumSizeHint())))


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
        if not isfile(fileName):
            return
        config = QSettings(fileName, QSettings.IniFormat)

        def valToLoad(wdg):
            nm = wdg.objectName()
            if not config.contains(nm):
                return
            elif isinstance(wdg, QtWidgets.QLineEdit):
                setVText(wdg, config.value(nm, type=str), str)
            elif isinstance(wdg, QtWidgets.QCheckBox):
                wdg.setChecked(config.value(nm, type=bool))
            elif isinstance(wdg, QtWidgets.QAbstractSpinBox):
                wdg.setValue(config.value(nm, type=float))
            elif isinstance(wdg, QtWidgets.QComboBox):
                didx = wdg.findText(config.value(nm, type=str))
                if didx >= 0:
                    wdg.setCurrentIndex(didx)
        self.amLoading = True
        for swdg in self.configObjects:
            valToLoad(swdg)
        self.amLoading = False
        self.update()


    @pyqtSlot()
    def onNewExperiment(self):
        expPath = self.ui.expPath.text()
        expIdx = self.ui.expSelect.findData(expPath)
        if expIdx >= 0 :
            self.ui.expSelect.blockSignals(True)
            self.ui.expSelect.setCurrentIndex(expIdx)
            self.ui.expSelect.blockSignals(False)
            self.ui.expSelect.setStyleSheet("")
        else :
            self.ui.expSelect.setStyleSheet(badStyle)

        selection = self.ui.inSelect
        selection.blockSignals(True)
        selection.clear()
        selection.setEnabled(False)
        ePath = join(expPath, "input")
        if isdir(ePath):
            selection.addItem("Loading...")
            self.update()
            QtCore.QCoreApplication.processEvents()
            for name in sorted(os.listdir(ePath)):
                iPath = join(ePath, name)
                if isdir(iPath):
                    selection.addItem(name, iPath)
            selection.removeItem(0) # Loading...
        if  selection.count():
            selection.setEnabled(True)
        else :
            selection.addItem("<none>")
        selection.blockSignals(False)


    @pyqtSlot()
    def onNewSample(self):

        self.ui.goStitch.setEnabled(False)
        self.ui.goRec.setEnabled(False)
        for errLabel in self.ui.findChildren(QtWidgets.QLabel, QtCore.QRegExp("^err\\w+")):
            self.showWdg(errLabel, False)
        self.resize(self.minimumSizeHint())
        ipath = self.ui.inPath.text()
        if not isdir(ipath) :
            self.showWdg(self.ui.errNoPath, False)
            return
        inidx = self.ui.inSelect.findData(ipath)
        if inidx >= 0 :
            self.ui.inSelect.blockSignals(True)
            self.ui.inSelect.setCurrentIndex(inidx)
            self.ui.inSelect.blockSignals(False)
            self.ui.inSelect.setStyleSheet("")
        else:
            self.ui.inSelect.setStyleSheet(badStyle)

        parsed = parse.parse("{}_{}keV_{}m_{}mGy", basename(ipath))
        if parsed:
            parsed = parsed.fixed
        else:
            parsed = []
        def displayParsed(lineedit, combobox, text, tp):
            setVText(lineedit, text, tp)
            item = combobox.findText(text)
            if item != -1 :
                combobox.setCurrentIndex(item)
            lineedit.setStyleSheet( badStyle if item == -1 else "" )
        if len(parsed) == 4 :
            setVText(self.ui.sample, parsed[0], str)
            displayParsed(self.ui.energy, self.ui.energyR, parsed[1], float)
            displayParsed(self.ui.distance, self.ui.distanceR, parsed[2], float)
            setVText(self.ui.dose, parsed[3], float)
            if not self.ui.distance.styleSheet() :
                zeroDistance = self.ui.distanceR.currentText() == "0"
                self.ui.set1.setChecked(True)
                self.ui.set2.setChecked(not zeroDistance)
                self.ui.set4.setChecked(not zeroDistance)
        else:
            self.showWdg(self.ui.errFolderName, True)

        cfgName = ''
        attempt = 0
        while True:
            n_cfgName = join(ipath, 'acquisition.%i.configuration' % attempt)
            if exists(n_cfgName):
                cfgName = n_cfgName
            else:
                break
            attempt += 1
        if not cfgName:  # one more attempt for little earlier code
            cfgName = os.popen('ls ' + ipath + os.sep + 'acquisition.*conf* 2> /dev/null' +
                               ' | sort -V | tail -n 1' ).read().strip("\n")
        if not cfgName:
            self.showWdg(self.ui.errNoConfig, True)
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
            self.tilesWU = 1 if not serialScan else oSteps if not twodScans else iSteps
            setVText(self.ui.tilesW, self.tilesWU, int)
            self.tilesHU = 1 if not serialScan or not twodScans else oSteps
            setVText(self.ui.tilesH, self.tilesHU, int)
            arc = valFromConfig('scan/range', float)
            setVText(self.ui.arc, arc, float)
            setVText(self.ui.arcR, arc, float)
            projections = valFromConfig('scan/steps', int)
            setVText(self.ui.projections, projections, int)
            setVText(self.ui.projectionsR, projections, int)
            self.stepU = arc/projections
            self.updasteStitchedSizes()
            setVText(self.ui.step, self.stepU , float)
            setVText(self.ui.stepR, self.stepU, float)
        except:
            self.showWdg(self.ui.errBadConfig, True)
            return

        self.logName = re.sub(r"\.config.*", ".log", cfgName)
        if isfile(self.logName):
            logInfo = os.popen('cat "' + self.logName + '"'
                                + ' | ' + join(execPath, 'imbl-log.py -i')
                                + ' | grep \'# Common\' '
                                + ' | cut -d\' \' -f 4- ' ) \
                            .read().strip("\n").split()
            if len(logInfo) == 3:
                setVText(self.ui.arcR, logInfo[0], float)
                setVText(self.ui.projectionsR, logInfo[1], int)
                setVText(self.ui.stepR, logInfo[2], float)
            else:
                self.showWdg(self.ui.errBadLog, True)
        else :
            self.showWdg(self.ui.errNoLog, True)

        # this works much faster because find can quit after first match and
        # does not need to walk through all files in the input directory
        imgSizes = os.popen('identify $(find ' + ipath + ' -iname "*.tif" -print -quit) 2> /dev/null'
                            + ' | cut -d\' \' -f 3' ) \
                    .read().strip("\n").split('x')
        setVText(self.ui.imageW, imgSizes[0] if len(imgSizes) == 2 else "error", int)
        setVText(self.ui.imageH, imgSizes[1] if len(imgSizes) == 2 else "error", int)

        self.ui.goStitch.setEnabled(True)
        self.ui.goRec.setEnabled(True)


    def updasteStitchedSizes(self):
        self.stitchedSizes = False
        if not self.stepU:
            return
        lastImage = join(self.stitchedPath, "proj%i.tif" % int(180/self.stepU -1))
        if not isfile(lastImage) :
            return
        self.stitchedSizes = [ int(sz) for sz in 
            os.popen('identify ' + lastImage + ' 2> /dev/null' + ' | cut -d\' \' -f 3' ) \
              .read().strip("\n").split('x') ]


    def setOutPath(self, correctOut=True):
        iPath = self.ui.inPath.text()
        oPath = re.sub(r'/input/', r'/output/', iPath)
        inhasin = basename(dirname(iPath)) == "input"
        self.ui.outAuto.setStyleSheet("")
        self.ui.outAuto.setEnabled(inhasin)
        if correctOut and self.ui.outAuto.isChecked() :
            setVText(self.ui.outPath, oPath, str)
        self.ui.outAuto.setStyleSheet(
            "" if self.ui.outPath.text() == oPath or not self.ui.outAuto.isChecked() else badStyle)
        oPath = self.ui.outPath.text()
        self.fakeInPath = join(oPath, "fakeInput")
        self.stitchedPath = join(oPath, "stitched")
        self.updasteStitchedSizes()


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


    def execInBg(self, command):

        self.addToConsole("Executing command:")
        self.addToConsole(command, QtCore.Qt.green)
        self.proc.setArguments(("-c", command))

        eloop = QEventLoop(self)
        self.proc.finished.connect(eloop.quit)
        self.proc.readyReadStandardOutput.connect(eloop.quit)
        self.proc.readyReadStandardError.connect(eloop.quit)

        self.proc.start()
        self.proc.waitForStarted(500)
        while True:
            self.addOutToConsole(self.proc.readAllStandardOutput()
                                 .data().decode(sys.getdefaultencoding()))
            self.addErrToConsole(self.proc.readAllStandardError()
                                 .data().decode(sys.getdefaultencoding()))
            if self.proc.state():
                eloop.exec_()
            else:
                break
        self.addToConsole("Stopped with exit status %i" % self.proc.exitCode())


    @pyqtSlot()
    def onStitch(self):
        self.stitchedSizes = False
        inPath = self.ui.inPath.text()
        oPath = self.ui.outPath.text()
        if not exists(oPath):
            os.mkdir(oPath)
        parsedLogName =  join(oPath, ".parsed.log")
        self.execInBg("cat " + self.logName
                      + " | " + join(execPath, "imbl-log.py") + " -m 180 -s " + str(self.stepU)
                      + " > " + parsedLogName)
        self.fakeInPath = join(oPath, "fakeInput")
        if not exists(self.fakeInPath):
            os.mkdir(self.fakeInPath)
        self.execInBg("cat " + parsedLogName + " | grep -v '#' "
                      + " | parallel ' read lbl idx num <<< {} ; "
                                   + " ln -sf " + join(inPath, "SAMPLE_${lbl}_T$(printf %04i ${num}).tif") + " "
                                                + join(self.fakeInPath, "SAMPLE_${lbl}_T$(printf %04i ${idx}).tif") + "'")
        self.execInBg(" ls " + join(inPath, "BG") + "* " + join(inPath, "DF") + "* "
                      + " | parallel 'ln -sf  $(realpath {}) " + self.fakeInPath + os.path.sep + "'")
        preProcConfig = join(oPath , "IMBL_preproc.txt")
        if not exists(self.stitchedPath):
            os.mkdir(self.stitchedPath)
        os.popen("cat " + join(execPath, "../share/imblproc/IMBL_preproc.txt.template")
                 + " | sed -e 's REPLACEWITH_inPath " + self.fakeInPath + "/ g' "
                 + "       -e 's REPLACEWITH_outPath " + self.stitchedPath + "/ g' "
                 + "       -e 's REPLACEWITH_prefixBG " + ("BG_Y" if self.tilesWU > 1 else "BG_") + " g' "
                 + "       -e 's REPLACEWITH_prefixS " + ("SAMPLE_Y" if self.tilesWU > 1 else "SAMPLE_") + " g' "
                 + "       -e 's REPLACEWITH_tilesW " + str(self.tilesWU) + " g' "
                 + "       -e 's REPLACEWITH_overlap " + str(distances[self.ui.distanceR.currentText()].overlap) + " g' "
                 + "       -e 's REPLACEWITH_trimL " + str(self.ui.trimL.value()) + " g' "
                 + "       -e 's REPLACEWITH_trimR " + str(self.ui.trimR.value()) + " g' "
                 + "       -e 's REPLACEWITH_trimT " + str(self.ui.trimT.value()) + " g' "
                 + "       -e 's REPLACEWITH_trimB " + str(self.ui.trimB.value()) + " g' "
                 + " > " + preProcConfig )
        self.execInBg(preProcExec + " " + preProcConfig)
        os.popen("rm -rf " + self.fakeInPath)
        self.updasteStitchedSizes()


    @pyqtSlot()
    def onRec(self):
        oPath = self.ui.outPath.text()
        if not self.stitchedSizes :
            self.onStitch()
        if not self.stitchedSizes :
            return
        dist = self.ui.distanceR.currentText()
        enrg = self.ui.energyR.currentText()
        commonExec = join(execPath, 'imbl-xtract-wrapper.sh')
        commonParameters = " -p 'proj\w+.tif' " \
                         + " -r rec.tif " \
                         + " -e " + enrg \
                         + " -S " + distances[dist].pixelSize \
                         + " -P " + ("0" if dist == "0" else "1" ) \
                         + " -d " + distances[dist].rPrime \
                         + " -D " + energies[enrg] \
                         + " -R " + str(self.ui.ring.value()) \
                         + " -F " + distances[dist].ctFilter + " " \
                         + join(execPath, "../share/imblproc/params_ctworkflow.txt")

        if self.sender() is self.ui.testRing :
            recDir = join(oPath, "rec_test")
            if not exists(recDir):
                os.mkdir(recDir)
            halfH = self.stitchedSizes[1] // 2
            self.execInBg( commonExec
                           + " -a " + str(self.stepU)
                           + " -T " + "%i,%i,%i,%i" % 
                                      ( 0, self.stitchedSizes[0]-1, halfH - 50, halfH + 50) 
                           + commonParameters + " " + self.stitchedPath + " " + recDir)
            os.popen("rm -rf " + self.fakeInPath + "/*")
        else :
            for stepN in [1, 2, 4] :
                stepC = str(stepN)
                if not hasattr(self.ui, "set" + stepC) or not eval("self.ui.set" + stepC).isChecked():
                    continue
                iPath = self.stitchedPath
                if stepN != 1:
                    if not exists(self.fakeInPath):
                        os.mkdir(self.fakeInPath)
                    else :
                        os.popen("rm -rf " + self.fakeInPath + "/*")                    
                    self.execInBg("seq -w 0 " + stepC + " " + str(int(180/self.stepU))
                          + " | parallel ' src=$(realpath " + self.stitchedPath + "/proj{}.tif) ; " \
                                       + " if [ -e \"$src\" ] ; then " \
                                       + "   ln -sf  ${src} " + self.fakeInPath + os.path.sep + ";"\
                                       + " fi" + "'" )
                    iPath = self.fakeInPath
                recDir = join(oPath, "rec_" + stepC)
                if not exists(recDir):
                    os.mkdir(recDir)
                self.execInBg( commonExec
                               + " -a " + str(self.stepU * stepN)
                               + commonParameters + " " + iPath + " " + recDir )
                os.popen("rm -rf " + self.fakeInPath + "/*")
        os.popen("rm -rf " + self.fakeInPath)

















app = QApplication(sys.argv)
my_mainWindow = MainWindow()
my_mainWindow.show()
sys.exit(app.exec_())
