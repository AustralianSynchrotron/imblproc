#!/usr/bin/env python3

import sys, os, re, psutil, time, itertools
from tabnanny import check


from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QSettings, QProcess, QEventLoop, QObject, QTimer
from PyQt5.QtWidgets import QFileDialog, QApplication
from PyQt5.uic import loadUi

from subprocess import Popen
from pathlib import Path
# sys.path.append("..")
# from share import ui_imbl

execPath = os.path.dirname(os.path.realpath(__file__)) + os.path.sep
warnStyle = 'background-color: rgba(255, 0, 0, 128);'

def killProcTree(pid):
    try:
        proc=psutil.Process(pid)
        for child in proc.children(recursive=True):
            child.kill()
        proc.kill()
    except Exception:
        pass


previousParse = ""
proggMax = None
def parseOutProgg(outed, erred):
    global previousParse, proggMax
    progg = proggTxt = None
    addToOut = outed
    addToErr = erred
    if not outed and not erred:
        return progg, proggMax, proggTxt, addToOut, addToErr


    addToOut = ""
    for curL in outed.splitlines():
        # poptmx start
        if lres := re.search('Starting process \((.*) steps\)\: (.*)\.', curL) :
            progg=0
            proggMax=int(lres.group(1))
            proggTxt=lres.group(2)
            addToOut += curL + '\n'
        # poptmx complete
        elif "Successfully finished" in curL or "DONE" in curL :
            progg=-1
            addToOut += curL + '\n'
        # poptmx progg
        elif lres := re.search('^([0-9]+)/([0-9]+)$', curL) :
            progg=int(lres.group(1))
            proggMax=int(lres.group(2))
        #xwrap reading progg
        elif lres := re.search('Reading projections: ([0-9]+)/([0-9]+)', curL) :
            procName = "CT: reading projections."
            proggTxt = procName
            progg=int(lres.group(1))
            proggMax=int(lres.group(2))
            if not progg:
                addToOut += procName + '\n'
        #xwrap reading complete.
        elif 'Reading projections: DONE.' in curL:
            progg = -1
            addToOut += " DONE." + '\n'
        #xwrap reconstructing progg
        elif lres := re.search('Reconstructing volume: ([0-9]+)/([0-9]+)', curL) :
            procName = "CT: reconstructing volume."
            proggTxt = procName
            progg=int(lres.group(1))
            proggMax=int(lres.group(2))
            if not progg:
                addToOut += procName + '\n'
        #xwrap reconstion complete.
        elif 'Reconstructing volume: DONE' in curL:
            progg = -1
            addToOut += " DONE." + '\n'
        # other
        elif len(curL):
            addToOut += curL + '\n'
        if len(curL.strip()) :
            previousParse = curL.strip()

    addToErr = ""
    for curL in erred.splitlines(): # GNU parallel in err
        if 'Computers / CPU cores / Max jobs to run' in curL:
            if lres := re.search('Starting (.*)\:', previousParse) :
                progg=0
                proggTxt=lres.group(1)
        # GNU parallel skip
        elif    'Computer:jobs running/jobs completed/%of started jobs/Average seconds to complete' in curL \
             or re.search('.+ / [0-9]+ / [0-9]+', curL) :
            progg=0
        # GNU parallel progg
        elif lres := re.search('ETA\: .* Left\: ([0-9]+) AVG\: .*\:[0-9]+/([0-9]+)/.*/.*', curL) :
            leftToDo = int(lres.group(1))
            progg = int(lres.group(2))
            proggMax = progg + leftToDo
            if not leftToDo :
                llres = re.search('ETA\: .* Left\: ([0-9]+) AVG\: .*\:[0-9]+/([0-9]+)/.*/.*', previousParse)
                if not llres or progg != int(llres.group(2)) :
                  progg = -1
                  addToOut += " DONE.\n"
        # other
        elif len(curL):
            addToErr += curL + '\n'
        if len(curL.strip()) :
            previousParse = curL.strip()

    return progg, proggMax, proggTxt, addToOut, addToErr


class Script(QObject) :

    shell = os.environ['SHELL'] if os.environ['SHELL'] else "/bin/sh"
    bodySet = pyqtSignal()
    finished = pyqtSignal(int)
    started = pyqtSignal()


    def __init__(self, parent=None):
        super(QObject, self).__init__(parent)
        self.fileExec = QtCore.QTemporaryFile()
        if not self.fileExec.open():
            print("ERROR! Unable to open temporary file.")
            return
        self.proc = QProcess(self)
        self.proc.setProgram(self.shell)
        self.proc.stateChanged.connect(self.onState)
        self.time=0


    @pyqtSlot(str)
    def setBody(self, body):
        if not self.fileExec.isOpen() or self.isRunning():
            return
        self.fileExec.resize(0)
        self.fileExec.write(body.strip().encode())
        #self.fileExec.write(" $@\n".encode())
        self.fileExec.flush()
        self.bodySet.emit()


    def body(self):
        if not self.fileExec.isOpen():
            return ""
        self.fileExec.seek(0)
        return self.fileExec.readAll().data().decode()


    @pyqtSlot()
    def onState(self):
        state = self.proc.state()
        if state == QProcess.NotRunning:
            self.time = time.time() - self.time
            self.finished.emit(self.proc.exitCode())
        if state == QProcess.Running:
            self.time = time.time()
            self.started.emit()


    def isRunning(self):
        return self.proc.state() != QProcess.NotRunning


    @pyqtSlot(list)
    def start(self, par=None):
        if self.isRunning():
            return False
        if not self.fileExec.size():
            return True
        args = [self.fileExec.fileName()]
        if par:
            if isinstance(par, str):
                args.append(par)
            else:
                args += par
        self.proc.setArguments(args)
        self.proc.start()
        self.proc.waitForStarted(500)
        return self.isRunning()


    @pyqtSlot(list)
    def exec(self, par=None):
        return self.waitStop() if self.start(par) else None


    def stop(self):
        if not self.isRunning():
            return
        try:
            psproc=psutil.Process(self.proc.pid())
            for child in psproc.children(recursive=True):
                child.kill()
            self.proc.kill()
        except Exception:
            pass


    def waitStop(self):
        q = QEventLoop()
        self.finished.connect(q.quit)
        if self.isRunning():
            q.exec()
        return self.exitCode()


    def evaluate(self, par=None):
        tempproc = QProcess(self)
        args = ["-n", self.fileExec.fileName()]
        if par:
            if isinstance(par, str):
                args.append(par)
            else:
                args += par
        tempproc.start(self.shell, args)
        tempproc.waitForFinished()
        return tempproc.exitCode()


def onBrowse(wdg, desc, forFile=False):
    dest = ""
    if forFile:
        dest, _filter = QFileDialog.getOpenFileName(wdg, desc, wdg.text())
    else:
        dest = QFileDialog.getExistingDirectory(wdg, desc, wdg.text())
    if dest:
        wdg.setText(dest)


class UScript(QtWidgets.QWidget) :

    editingFinished = pyqtSignal()

    def __init__(self, parent=None):
        super(QtWidgets.QWidget, self).__init__(parent)
        self.ui = loadUi(execPath + '../share/imblproc/script.ui', self)
        self.script = Script(self)
        self.ui.body.textChanged.connect(self.script.setBody)
        self.ui.browse.clicked.connect(lambda : onBrowse(self.ui.body, "Command", True))
        self.ui.execute.clicked.connect(self.onStartStop)
        self.ui.body.editingFinished.connect(self.editingFinished.emit)
        self.script.started.connect(self.updateState)
        self.script.finished.connect(self.updateState)
        self.script.bodySet.connect(self.updateBody)

    @pyqtSlot()
    def onStartStop(self):
        if self.script.isRunning():
            self.script.stop()
        else:
            self.script.start()

    @pyqtSlot()
    def updateState(self):
        isrunning = self.script.isRunning()
        self.ui.browse.setEnabled(not isrunning)
        self.ui.body.setEnabled(not isrunning )
        self.ui.execute.setText( "Stop" if isrunning else "Execute" )
        self.ui.execute.setStyleSheet( "color: rgb(255, 0, 0);" if isrunning or self.script.proc.exitCode() else "")

    @pyqtSlot()
    def updateBody(self):
        self.ui.body.setStyleSheet("color: rgb(255, 0, 0);" if self.script.evaluate() else "")
        self.ui.execute.setStyleSheet("")


class ColumnResizer(QObject):

    def __init__(self, parent=None):
        super(QObject, self).__init__(parent)
        self.updateTimer = QTimer(self)
        self.updateTimer.setSingleShot(True)
        self.updateTimer.setInterval(0)
        self.updateTimer.timeout.connect(self.updateWidth)
        self.widgets = []
        self.columnsInfo = {}

    def addWidget(self, widget):
        self.widgets.append(widget)
        widget.installEventFilter(self)
        self.updateTimer.start()

    def addWidgetsFromLayout(self, layout, column):
        if not layout or not isinstance(layout, QtWidgets.QGridLayout):
            return
        for row in range(0,layout.rowCount()):
            if (item := layout.itemAtPosition(row, column)) and (wdg := item.widget()) and wdg not in self.widgets :
                self.addWidget(wdg)
        self.columnsInfo[layout] = column

    @pyqtSlot()
    def updateWidth(self):
        width = 0
        for wdg in self.widgets:
            width = max(wdg.sizeHint().width(), width)
        for layout, column in self.columnsInfo.items():
            layout.setColumnMinimumWidth(column, width)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Resize:
            self.updateTimer.start()
        return False


class MainWindow(QtWidgets.QMainWindow):

    configName = ".imbl-ui"
    etcConfigName = os.path.join(Path.home(), configName)
    amLoading = False


    def __init__(self):
        super(MainWindow, self).__init__()
        cfgProp="saveInConfig" # objects with this property (containing int read order) will be saved in config
        self.ui = loadUi(execPath + '../share/imblproc/imbl-ui.ui', self)

        self.previousParse = ""
        self.proggMax = None
        self.counter=0
        placePrefix="placeScript_"
        for place in self.ui.findChildren(QtWidgets.QLayout, QtCore.QRegExp(placePrefix+"\w+")):
            scrw = UScript(self)
            scrw.setObjectName("script_"+place.objectName().removeprefix(placePrefix))
            scrw.setProperty(cfgProp, 2)
            self.ui.outPath.textChanged.connect(scrw.script.proc.setWorkingDirectory)
            place.addWidget(scrw)
            scrw.script.proc.readyReadStandardOutput.connect(self.parseScriptOut)
            scrw.script.proc.readyReadStandardError.connect(self.parseScriptOut)
            scrw.script.started.connect(self.onScriptStarted)
            scrw.script.finished.connect(self.onScriptFinished)
        self.cResizer = ColumnResizer(self)
        self.cResizer.addWidgetsFromLayout(self.ui.tabRec.layout(), 4)
        for script in self.ui.tabRec.findChildren(UScript):
            self.cResizer.addWidgetsFromLayout(script.ui.layout(), 1)

        self.on_individualIO_toggled()
        self.ui.inProgress.setVisible(False)

        saveBtn = QtWidgets.QPushButton("Save", self)
        saveBtn.setFlat(True)
        saveBtn.clicked.connect(lambda : self.saveConfiguration(""))
        self.ui.statusBar().addPermanentWidget(saveBtn)
        loadBtn = QtWidgets.QPushButton("Load", self)
        loadBtn.setFlat(True)
        loadBtn.clicked.connect(lambda : self.loadConfiguration(""))
        self.ui.statusBar().addPermanentWidget(loadBtn)

        self.doYst = False
        self.doZst = False
        self.doFnS = False

        confsWithOrder = { wdg: wdg.property(cfgProp) for wdg in self.ui.findChildren(QObject)
                                                      if wdg.property(cfgProp) is not None}
        self.configObjects = [ pr[0] for pr in sorted(confsWithOrder.items(), key=lambda x:x[1]) ]
        # dynamic property of the QButtonGroup is not read from ui file; have to add them manually:
        self.configObjects.extend([grp for grp in self.ui.findChildren(QtWidgets.QButtonGroup)
                                       if not grp in self.configObjects])
        for swdg in self.configObjects:
            if isinstance(swdg, QtWidgets.QLineEdit):
                swdg.textChanged.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QCheckBox):
                swdg.toggled.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QAbstractSpinBox):
                swdg.valueChanged.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QComboBox):
                swdg.currentTextChanged.connect(self.saveConfiguration)
            elif isinstance(swdg, UScript):
                swdg.editingFinished.connect(self.saveConfiguration)
            elif isinstance(swdg, QtWidgets.QButtonGroup):
                swdg.buttonClicked.connect(self.saveConfiguration)

        self.ui.notFnS.clicked.connect(self.needReinitiation)
        self.ui.ignoreLog.clicked.connect(self.needReinitiation)
        self.ui.yIndependent.clicked.connect(self.needReinitiation)
        self.ui.zIndependent.clicked.connect(self.needReinitiation)
        self.ui.excludes.editingFinished.connect(self.needReinitiation)
        self.ui.expUpdate.clicked.connect(self.on_expPath_textChanged)
        self.ui.ignoreLog.toggled.connect(self.on_inPath_textChanged)
        self.ui.excludes.editingFinished.connect(self.on_inPath_textChanged)

        QtCore.QTimer.singleShot(100, self.loadConfiguration)


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
            elif isinstance(wdg, UScript):
                return wdg.ui.body.text()
            elif isinstance(swdg, QtWidgets.QButtonGroup):
                return swdg.checkedButton().text() if swdg.checkedButton() else ""

        for swdg in self.configObjects:
            config.setValue(swdg.objectName(), valToSave(swdg))


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
            elif isinstance(wdg, QtWidgets.QSpinBox):
                val = config.value(oName, type=int)
                if wdg.maximum() < val: wdg.setMaximum(val)
                if wdg.minimum() > val: wdg.setMinimum(val)
                wdg.setValue(val)
            elif isinstance(wdg, QtWidgets.QDoubleSpinBox):
                val = config.value(oName, type=float)
                if wdg.maximum() < val: wdg.setMaximum(val)
                if wdg.minimum() > val: wdg.setMinimum(val)
                wdg.setValue(val)
            elif isinstance(wdg, QtWidgets.QComboBox):
                txt = config.value(oName, type=str)
                didx = wdg.findText(txt)
                if not didx < 0:
                    wdg.setCurrentIndex(didx)
            elif isinstance(wdg, UScript):
                wdg.ui.body.setText(config.value(oName, type=str))
            elif isinstance(swdg, QtWidgets.QButtonGroup):
                txt = config.value(oName, type=str)
                for but in wdg.buttons():
                    if but.text() == txt:
                        but.setChecked(True)

        for swdg in self.configObjects:
            oName = swdg.objectName()
            if config.contains(oName):
                valToLoad(swdg, oName)
            if swdg is self.ui.outPath:
                self.on_outPath_textChanged()
            if swdg is self.ui.sameBin:
                self.on_sameBin_toggled()

        self.amLoading = False


    def addToConsole(self, text, qcolor=None):
        text.strip()
        if not text:
            return
        if not qcolor:
            qcolor = self.ui.console.palette().text().color()
        self.ui.console.setTextColor(qcolor)
        self.ui.console.append(str(text).strip('\n'))


    def addOutToConsole(self, text):
        self.addToConsole(text, QtCore.Qt.cyan)


    def addErrToConsole(self, text):
        self.addToConsole(text, QtCore.Qt.red)


    @pyqtSlot()
    def parseScriptOut(self):

        proc = self.sender()
        outed = proc.readAllStandardOutput().data().decode(sys.getdefaultencoding()).strip()
        erred = proc.readAllStandardError().data().decode(sys.getdefaultencoding()).strip()
        if not outed and not erred:
            return
        if outed :
          print(outed, end=None)
        if erred :
          print(erred, end=None, file=sys.stderr)

        progg = proggTxt = None
        addToOut = addToErr = ""
        for curL in outed.splitlines():
            # poptmx start
            if lres := re.search('Starting process \((.*) steps\)\: (.*)\.', curL) :
                progg=0
                self.proggMax=int(lres.group(1))
                proggTxt=lres.group(2)
                addToOut += curL + '\n'
            # poptmx complete
            elif "Successfully finished" in curL or "DONE" in curL :
                progg=-1
                addToOut += curL + '\n'
            # poptmx progg
            elif lres := re.search('^([0-9]+)/([0-9]+)$', curL) :
                progg=int(lres.group(1))
                self.proggMax=int(lres.group(2))
            # other
            elif len(curL):
                addToOut += curL + '\n'
            if len(curL.strip()) :
                self.previousParse = curL.strip()

        for curL in erred.splitlines(): # GNU parallel in err
            if 'Computers / CPU cores / Max jobs to run' in curL:
                if lres := re.search('Starting (.*)\:', self.previousParse) :
                    progg=0
                    proggTxt=lres.group(1)
            # GNU parallel skip
            elif    'Computer:jobs running/jobs completed/%of started jobs/Average seconds to complete' in curL \
                 or re.search('.+ / [0-9]+ / [0-9]+', curL) :
                progg=0
            # GNU parallel progg
            elif lres := re.search('ETA\: .* Left\: ([0-9]+) AVG\: .*\:[0-9]+/([0-9]+)/.*/.*', curL) :
                leftToDo = int(lres.group(1))
                progg = int(lres.group(2))
                self.proggMax = progg + leftToDo
                if not leftToDo :
                    llres = re.search('ETA\: .* Left\: ([0-9]+) AVG\: .*\:[0-9]+/([0-9]+)/.*/.*', self.previousParse)
                    if not llres or progg != int(llres.group(2)) :
                      progg = -1
                      addToOut += " DONE.\n"
            # other
            elif len(curL):
                addToErr += curL + '\n'
            if len(curL.strip()) :
                self.previousParse = curL.strip()

        if progg is not None:
            if progg < 0:
                self.counter += 1
                self.ui.inProgress.setVisible(False)
            else:
                self.ui.inProgress.setValue(progg)
        if self.proggMax  and  self.proggMax != self.ui.inProgress.maximum() :
            self.ui.inProgress.setMaximum(self.proggMax)
        if proggTxt:
            self.ui.inProgress.setFormat( (f"({self.counter+1}) " if self.counter else "")
                                        + proggTxt + ": %v of %m (%p%)" )
        self.addOutToConsole(addToOut)
        self.addErrToConsole(addToErr)


    @pyqtSlot()
    def onScriptStarted(self):
        self.ui.inProgress.setValue(0)
        self.ui.inProgress.setMaximum(0)
        self.ui.inProgress.setFormat("Starting...")
        self.ui.inProgress.setVisible(True)
        script = self.sender()
        self.addToConsole( f"Executing command in {script.proc.workingDirectory()}:\n"
                           f"  {script.body()}"
            , QtCore.Qt.green)


    @pyqtSlot()
    def onScriptFinished(self):
        self.ui.inProgress.setVisible(False)
        script = self.sender()
        (self.addErrToConsole if script.proc.exitCode() else self.addOutToConsole)
        (f"Stopped after {int(script.time)}s with exit status {script.proc.exitCode()}.")


    def execInBg(self, proc, parseProc=None):

        self.addToConsole("Executing command:")
        printproc = proc.program() + " " + ' '.join([ar for ar in proc.arguments()])
        printpwd = os.path.realpath(proc.workingDirectory())
        self.addToConsole(f"cd \"{printpwd}\"    && \\ \n {printproc}", QtCore.Qt.green)
        eloop = QEventLoop(self)
        proc.finished.connect(eloop.quit)
        proc.readyReadStandardOutput.connect(eloop.quit)
        proc.readyReadStandardError.connect(eloop.quit)
        self.ui.inProgress.setValue(0)
        self.ui.inProgress.setMaximum(0)
        self.ui.inProgress.setFormat(f"Starting {printproc}")
        counter=0

        start_time = time.time()
        proc.start()
        proc.waitForStarted(500)
        while True:
            addOut = proc.readAllStandardOutput().data().decode(sys.getdefaultencoding())
            if addOut and len(addOut.strip()):
              print(addOut, end=None)
            addErr = proc.readAllStandardError().data().decode(sys.getdefaultencoding())
            if addErr and len(addErr.strip()):
              print(addErr, end=None, file=sys.stderr)
            if not parseProc:
                self.addOutToConsole(addOut)
                self.addErrToConsole(addErr)
                continue
            progg = proggMax = proggTxt = None
            toOut = toErr = ""
            try :
                progg, proggMax, proggTxt, toOut, toErr = parseProc(addOut, addErr)
                if progg is not None:
                    if progg < 0:
                        counter += 1
                        self.ui.inProgress.setVisible(False)
                    else:
                        self.ui.inProgress.setValue(progg)
                    self.ui.inProgress.setVisible(progg>=0)
                if proggMax  and  proggMax != self.ui.inProgress.maximum() :
                    self.ui.inProgress.setMaximum(proggMax)
                if proggTxt:
                    self.ui.inProgress.setFormat( (f"({counter+1}) " if counter else "")
                                                  + proggTxt + ": %v of %m (%p%)" )
            except Exception:
                pass
            self.addOutToConsole(toOut)
            self.addErrToConsole(toErr)

            if proc.state():
                eloop.exec_()
            else:
                break

        proc_time = time.time() - start_time
        final_msg = f"Stopped after {int(proc_time)}s with exit status {proc.exitCode()}."
        if proc.exitCode():
            self.addErrToConsole(final_msg)
        else:
            self.addOutToConsole(final_msg)
        self.ui.inProgress.setVisible(False)


    @pyqtSlot()
    def needReinitiation(self):
        self.ui.width.setValue(0)
        self.ui.hight.setValue(0)
        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.widget(tabIdx).setEnabled(False)


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


    def generalBrowse(self, wdg, desc, forFile=False):
        dest = ""
        if forFile:
            dest, _filter = QFileDialog.getOpenFileName(self, desc, wdg.text())
        else:
            dest = QFileDialog.getExistingDirectory(self, desc, wdg.text())
        if dest:
            wdg.setText(dest)


    @pyqtSlot()
    def on_expBrowse_clicked(self):
        onBrowse(self.ui.expPath, "Experiment directory")


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
        onBrowse(self.ui.inPath, "Sample directory")


    @pyqtSlot()
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
            n_cfgName = os.path.join(ipath, f"acquisition.{attempt}.configuration")
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
        self.ui.exclLabel.setVisible(serialScan)
        self.ui.excludes.setVisible(serialScan)

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
            grepsPps = ""
            if self.ui.excludes.isVisible() and self.ui.excludes.text():
                for grep in self.ui.excludes.text().split():
                    grepsPps += f" | grep -v -e '{grep}' "
            labels = os.popen('cat ' + os.path.join(ipath, "acquisition*log")
                                 + ' | ' + execPath + 'imbl-log.py'
                                 + ' | tail -n +3 | cut -d\' \' -f2 | cut -d\':\' -f 1 '
                                 + grepsPps).read().strip("\n").replace("\n", " ")
            logInfo = os.popen('cat ' + os.path.join(ipath, "acquisition*log")
                                + ' | ' + execPath + 'imbl-log.py ' + labels
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
        onBrowse(self.ui.outPath, "Output directory")


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
        except Exception:
            self.addErrToConsole("Corrupt init file \"{initiatedFile}\"")
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

        if self.ui.individualIO.isChecked():
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

        def setMyMax(wdg, mymax):
            if wdg.maximum() < mymax: wdg.setMaximum(mymax)

        def setMyRange(wdg, mymax, mymin):
            if wdg.maximum() < mymax: wdg.setMaximum(mymax)
            if wdg.minimum() > mymin: wdg.setMinimum(mymin)

        setMyMax(self.ui.sCropTop, hight)
        setMyMax(self.ui.sCropBottom, hight)
        setMyMax(self.ui.sCropLeft, width)
        setMyMax(self.ui.sCropRight, width)
        setMyRange(self.ui.iStX, -2*width, 2*width)
        setMyRange(self.ui.iStY, -2*hight, 2*hight)
        setMyRange(self.ui.oStX, -2*width, 2*width)
        setMyRange(self.ui.oStY, -2*hight, 2*hight)
        setMyRange(self.ui.fStX, -2*width, 2*width)
        setMyRange(self.ui.fStY, -2*hight, 2*hight)
        msz = max(1,ys, zs)
        setMyMax(self.ui.fCropTop, hight*msz)
        setMyMax(self.ui.fCropBottom, hight*msz)
        setMyMax(self.ui.fCropRight, width*msz)
        setMyMax(self.ui.fCropLeft, width*msz)

        self.ui.testSubDir.clear()
        sds = 'subdirs' in initDict
        self.ui.testSubDir.addItems(filemask.split() if sds else (".",))
        self.ui.testSubDir.setVisible(sds)
        self.ui.testSubDirLabel.setVisible(sds)
        self.ui.procThis.setVisible(sds)
        setMyMax(self.ui.testProjection, pjs)
        setMyMax(self.ui.minProj, pjs)
        setMyMax(self.ui.maxProj, pjs)

        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.widget(tabIdx).setEnabled(True)


    initproc = QProcess()

    @pyqtSlot()
    def on_initiate_clicked(self):
        if self.initproc.state():
            killProcTree(self.initproc.processId())
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
        command += " -v "
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
        if self.ui.excludes.isVisible() and self.ui.excludes.text():
            grepsPps = ""
            for grep in self.ui.excludes.text().split():
                grepsPps += f" | grep -v -e '{grep}' "
            labels = os.popen('cat ' + os.path.join(self.ui.inPath.text(), "acquisition*log")
                                 + ' | ' + execPath + 'imbl-log.py'
                                 + ' | tail -n +3 | cut -d\' \' -f2 | cut -d\':\' -f 1 '
                                 + grepsPps).read().strip("\n").replace("\n", " ")
            command += f" -L \"{labels}\" "

        command += f" -o \"{opath}\" "
        command += f" \"{self.ui.inPath.text()}\" "

        self.initproc.setProgram("/bin/sh")
        self.initproc.setArguments(("-c", command))
        self.execInBg(self.initproc, parseOutProgg)

        self.ui.initInfo.setEnabled(True)
        self.ui.initiate.setStyleSheet('')
        self.ui.initiate.setText('Initiate')

        self.on_outPath_textChanged()

        if self.ui.procAfterInit.isChecked():
            self.on_procAll_clicked()


    @pyqtSlot(bool)
    def on_sameBin_toggled(self):
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
    def on_maskBrowse_clicked(self):
        onBrowse(self.ui.maskPath, "Mask image.", True)


    @pyqtSlot()
    @pyqtSlot(str)
    def on_maskPath_textChanged(self):
        maskOK = os.path.exists(self.ui.maskPath.text()) or not len(self.ui.maskPath.text().strip())
        self.ui.maskPath.setStyleSheet("" if maskOK else warnStyle)


    stitchproc = QProcess()

    def common_test_proc(self, wdir, actButton, ars=None):
        if self.stitchproc.state():
            killProcTree(self.stitchproc.processId())
            return

        disableWdgs = (*self.configObjects,
                       self.ui.procAll, self.ui.procThis, self.ui.test.proj, self.ui.initiate)
        for wdg in disableWdgs:
            if wdg is not actButton:
                wdg.setEnabled(False)
        actText = actButton.text()
        actButton.setText('Stop')
        actButton.setStyleSheet(warnStyle)

        prms = str()
        if self.doYst or self.doZst:
            if self.doZst:
                prms += f" -g {self.ui.iStX.value()},{self.ui.iStY.value()} "
            else:
                prms += f" -g {self.ui.oStX.value()},{self.ui.oStY.value()} "
        if self.doYst and self.doZst:
            prms += f" -G {self.ui.oStX.value()},{self.ui.oStY.value()} "
        if self.doFnS:
            prms += f" -f {self.ui.fStX.value()},{self.ui.fStY.value()} "
        if len(self.ui.maskPath.text().strip()) :
            prms += f" -i \"{self.ui.maskPath.text().strip()}\" "
        if 1 != self.ui.xBin.value() * self.ui.yBin.value():
            prms += f" -b {self.ui.xBin.value()},{self.ui.yBin.value()} "
        if 0.0 != self.ui.rotate.value():
            prms += f" -r {self.ui.rotate.value()} "
        if 0.0 != self.ui.peakRad.value():
            prms += f" -n {self.ui.peakRad.value()} -N {self.ui.peakThr.value()} "
        if 0.0 != self.ui.edge.value():
            prms += f" -E {self.ui.edge.value()} "
        crops = (self.ui.sCropTop.value(), self.ui.sCropLeft.value(),
                 self.ui.sCropBottom.value(), self.ui.sCropRight.value())
        if sum(crops):
            prms += " -c %i,%i,%i,%i " % crops
        crops = (self.ui.fCropTop.value(), self.ui.fCropLeft.value(),
                 self.ui.fCropBottom.value(), self.ui.fCropRight.value())
        if sum(crops):
            prms += " -C %i,%i,%i,%i " % crops
        minProj = self.ui.minProj.value()
        maxProj = self.ui.maxProj.value()
        pjs=int(self.ui.projections.text())
        if maxProj == self.ui.maxProj.minimum()  or maxProj >= pjs  :
            maxProj = pjs
        prms += f" -m {minProj} -M {maxProj} "
        prms += " -v "
        if ars:
            prms += ars

        self.stitchproc.setProgram("/bin/sh")
        self.stitchproc.setArguments(("-c", execPath + "imbl-proc.sh " + prms))
        self.stitchproc.setWorkingDirectory(wdir)
        self.execInBg(self.stitchproc, parseOutProgg)

        for wdg in disableWdgs:
            wdg.setEnabled(True)
        actButton.setText(actText)
        actButton.setStyleSheet("")
        self.on_sameBin_toggled()  # to correct state of the yBin
        self.update_initiate_state()


    @pyqtSlot()
    def on_testProj_clicked(self):
        ars = f" -t {self.ui.testProjection.value()}"
        wdir = os.path.join(self.ui.outPath.text(),
                            self.ui.testSubDir.currentText())
        self.common_test_proc(wdir, self.ui.testProj, ars)


    @pyqtSlot()
    def on_procAll_clicked(self):
        wdir = self.ui.outPath.text()
        self.saveConfiguration(os.path.join(wdir, self.configName))
        self.common_test_proc(wdir, self.ui.procAll)


    @pyqtSlot()
    def on_procThis_clicked(self):
        wdir = os.path.join(self.ui.outPath.text(),
                            self.ui.testSubDir.currentText())
        self.saveConfiguration(os.path.join(wdir, self.configName))
        self.common_test_proc(wdir, self.ui.procThis)


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


    def updateRingOrderVisibility(self):
        vis = self.ui.distance.value() > 0 and self.ui.d2b.value() > 0 and self.ui.ring.value() > 0
        self.ui.ringOrderLabel.setVisible(vis)
        self.ui.ringOrder.setVisible(vis)


    @pyqtSlot(int)
    def on_distance_valueChanged(self):
        phasevis = self.ui.distance.value() > 0
        self.ui.d2b.setVisible(phasevis)
        self.ui.d2bLabel.setVisible(phasevis)
        self.updateRingOrderVisibility()


    @pyqtSlot(float)
    def on_d2b_valueChanged(self):
        self.updateRingOrderVisibility()


    @pyqtSlot(int)
    def on_ring_valueChanged(self):
        self.updateRingOrderVisibility()


    @pyqtSlot(str)
    def on_ctFilter_currentTextChanged(self):
        if self.ui.ctFilter.currentText() == "Kaiser":
            self.ui.ctFilterParam.setVisible(True)
            self.ui.filterParamLabel.setVisible(True)
            self.ui.filterParamLabel.setText("Alpha parameter")
        elif self.ui.ctFilter.currentText() == "Gauss":
            self.ui.ctFilterParam.setVisible(True)
            self.ui.filterParamLabel.setVisible(True)
            self.ui.filterParamLabel.setText("Sigma parameter")
        else:
            self.ui.ctFilterParam.setVisible(False)
            self.ui.filterParamLabel.setVisible(False)


    @pyqtSlot()
    def on_testSlice_clicked(self):
        print("Not yet ready")


    @pyqtSlot()
    def on_reconstruct_clicked(self):
        print("rec is Not yet ready")




app = QApplication(sys.argv)
my_mainWindow = MainWindow()
my_mainWindow.show()
sys.exit(app.exec_())
