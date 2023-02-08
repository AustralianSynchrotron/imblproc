#!/usr/bin/env python3

import sys, os, re, psutil, time, signal
from os import path

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QSettings, QProcess, QEventLoop, QObject, QTimer
from PyQt5.QtWidgets import QFileDialog, QApplication
from PyQt5.uic import loadUi


execPath = path.dirname(path.realpath(__file__)) + path.sep
warnStyle = 'background-color: rgba(255, 0, 0, 128);'
initFileName = '.initstitch'


def onBrowse(wdg, desc, forFile=False):
    dest = ""
    if forFile:
        dest, _filter = QFileDialog.getOpenFileName(wdg, desc, wdg.text())
    else:
        dest = QFileDialog.getExistingDirectory(wdg, desc, wdg.text())
    if dest:
        wdg.setText(dest)



class Script(QObject) :

    shell = os.environ['SHELL'] if os.environ['SHELL'] else "/bin/sh"
    bodySet = pyqtSignal()
    finished = pyqtSignal(int)
    started = pyqtSignal()
    scriptPrefix = "script_"
    procPrefix = "proc_"


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


    def setRole(self, role):
        self.setObjectName(self.scriptPrefix + role)
        self.proc.setObjectName(self.procPrefix + role)


    def role(self):
        return self.objectName().removeprefix(self.scriptPrefix)


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
        return self.proc.exitCode()


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


    def run(body) :
        scr = Script()
        scr.setBody(body)
        scr.exec()
        return scr.proc.exitCode() \
             , scr.proc.readAllStandardOutput().data().decode() \
             , scr.proc.readAllStandardError().data().decode()



class UScript(QtWidgets.QWidget) :

    editingFinished = pyqtSignal()
    uscriptPrefix = "uscript_"

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
        self.updateBody()


    def setRole(self, role):
        self.setObjectName(self.uscriptPrefix + role)
        self.script.setRole(role)


    def role(self):
        return self.objectName().removeprefix(self.uscriptPrefix)


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
        isGood = not self.script.evaluate()
        self.ui.body.setStyleSheet( "" if isGood else "color: rgb(255, 0, 0);")
        self.ui.execute.setStyleSheet("")
        self.ui.execute.setEnabled(self.script.isRunning() or (len(self.ui.body.text().strip()) and isGood) )



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



def hdf5shape(filename, dataset):
    _, outed, _ = Script.run(f"h5ls {filename}/{dataset}")
    if lres := re.search('.*{([0-9]+), ([0-9]+), ([0-9]+)}.*', outed) :
        return int(lres.group(3)), int(lres.group(2)), int(lres.group(1))
    else:
        return None, None, None



class MainWindow(QtWidgets.QMainWindow):

    configName = ".imbl-ui"
    etcConfigName = path.join(path.expanduser("~"), configName)
    amLoading = False
    placePrefix="placeScript_"


    def __init__(self):
        super(MainWindow, self).__init__()
        cfgProp="saveInConfig" # objects with this property (containing int read order) will be saved in config
        self.ui = loadUi(execPath + '../share/imblproc/imbl-ui.ui', self)

        self.scrInitiate = Script(self)
        self.scrInitiate.setRole("initiate")
        self.scrStitch = Script(self)
        self.scrStitch.setRole("stitch")
        self.scrCOR = Script(self)
        self.scrCOR.setRole("rotation center")
        self.scrRec = Script(self)
        self.scrRec.setRole("reconstruct")
        for place in self.ui.findChildren(QtWidgets.QLayout, QtCore.QRegExp(self.placePrefix+"\w+")):
            role = place.objectName().removeprefix(self.placePrefix)
            scrw = UScript(self)
            scrw.setRole(role)
            scrw.setProperty(cfgProp, 2)
            place.addWidget(scrw)
        self.cResizer = ColumnResizer(self)
        self.cResizer.addWidgetsFromLayout(self.ui.tabRec.layout(), 4)
        for script in self.ui.tabRec.findChildren(UScript):
            self.cResizer.addWidgetsFromLayout(script.ui.layout(), 1)
        for script in self.ui.findChildren(Script):
            self.ui.outPath.textChanged.connect(script.proc.setWorkingDirectory)
            script.proc.readyReadStandardOutput.connect(self.parseScriptOut)
            script.proc.readyReadStandardError.connect(self.parseScriptOut)
            script.started.connect(self.onScriptStarted)
            script.finished.connect(self.onScriptFinished)
            script.proc.stateChanged.connect(self.update_termini_state)
        self.collectOut = None
        self.collectErr = None

        self.on_individualIO_toggled()
        self.on_ctFilter_currentTextChanged()
        self.ui.inProgress.setVisible(False)
        self.ui.autoMin.setVisible(False) # feature not implemented
        self.ui.autoMax.setVisible(False) # feature not implemented

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

        # connect signals which are not connected by name
        self.ui.notFnS.clicked.connect(self.needReinitiation)
        self.ui.ignoreLog.clicked.connect(self.needReinitiation)
        self.ui.yIndependent.clicked.connect(self.needReinitiation)
        self.ui.zIndependent.clicked.connect(self.needReinitiation)
        self.ui.excludes.editingFinished.connect(self.needReinitiation)
        self.ui.expUpdate.clicked.connect(self.on_expPath_textChanged)
        self.ui.ignoreLog.toggled.connect(self.on_inPath_textChanged)
        self.ui.excludes.editingFinished.connect(self.on_inPath_textChanged)
        self.ui.minProj.valueChanged.connect(self.onMinMaxProjectionChanged)
        self.ui.maxProj.valueChanged.connect(self.onMinMaxProjectionChanged)
        self.ui.procAll.clicked.connect(self.onStitch)
        self.ui.procThis.clicked.connect(self.onStitch)
        self.ui.prFile.clicked.connect(lambda :
            QApplication.clipboard().setText(path.realpath(self.ui.prFile.text())))

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
        if not path.exists(fileName):
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
        scrollBar = self.ui.console.verticalScrollBar()
        atTheBottom = scrollBar.value() == scrollBar.maximum()
        self.ui.console.append(str(text).strip('\n'))
        if atTheBottom:
            scrollBar.setValue(scrollBar.maximum())


    def addOutToConsole(self, text):
        self.addToConsole(text, QtCore.Qt.cyan)


    def addErrToConsole(self, text):
        self.addToConsole(text, QtCore.Qt.red)


    @pyqtSlot()
    def parseScriptOut(self):

        proc = self.sender()
        role = proc.objectName().removeprefix(Script.procPrefix)
        outed = proc.readAllStandardOutput().data().decode(sys.getdefaultencoding())
        erred = proc.readAllStandardError().data().decode(sys.getdefaultencoding())
        if not outed and not erred:
            return
        if self.collectOut is not None:
            self.collectOut += outed
        if self.collectErr is not None:
            self.collectErr += erred

        progg = proggMax = None
        proggTxt = None
        addToOut = ""
        for curL in outed.splitlines():
            # poptmx start
            if lres := re.search('Starting process \((.*) steps\)\: (.*)\.', curL) :
                progg=0
                proggMax=int(lres.group(1))
                proggTxt = f"{role} - {lres.group(2)}"
                addToOut += curL.strip() + '\n'
            # poptmx complete
            elif "Successfully finished" in curL or "DONE" in curL :
                progg=-1
                addToOut += curL.strip() + '\n'
            # poptmx progg
            elif lres := re.search('^([0-9]+)/([0-9]+)$', curL) :
                progg=int(lres.group(1))
                proggMax=int(lres.group(2))
            # other
            elif len(curL):
                addToOut += curL + '\n'

        addToErr = ""
        for curL in erred.splitlines(): # GNU parallel in err
            # GNU parallel start
            if 'Computers / CPU cores / Max jobs to run' in curL:
                proggTxt = role
            # GNU parallel skip
            elif 'Computer:jobs running/jobs completed/%of started jobs/Average seconds to complete' in curL \
                 or re.search('.+ / [0-9]+ / [0-9]+', curL) :
                progg=0
            # GNU parallel progg
            elif lres := re.search('ETA\: .* Left\: ([0-9]+) AVG\: .*\:[0-9]+/([0-9]+)/.*/.*', curL) :
                leftToDo = int(lres.group(1))
                progg = int(lres.group(2)) if leftToDo else -1
                proggMax = progg + leftToDo
            # other
            elif len(curL):
                addToErr += curL + '\n'

        if progg is None or progg < 1:
            if outed:
                print(outed.strip('\n'), end=None)
            if erred:
                print(erred.strip('\n'), end=None, file=sys.stderr)
        if progg is not None:
            if progg < 0:
                self.counter += 1
            self.ui.inProgress.setValue(0 if progg < 0 else progg)
        if proggMax is not None  and  proggMax != self.ui.inProgress.maximum() :
            self.ui.inProgress.setMaximum(proggMax)
        if proggTxt:
            self.ui.inProgress.setFormat( (f"({self.counter+1}) " if self.counter else "")
                                        + proggTxt + ": %v of %m (%p%)" )
        self.addOutToConsole(addToOut)
        self.addErrToConsole(addToErr)


    @pyqtSlot()
    def onScriptStarted(self):
        self.counter = 0
        script = self.sender()
        role = "\"" + script.role() + "\""
        self.ui.inProgress.setValue(0)
        self.ui.inProgress.setMaximum(0)
        self.ui.inProgress.setFormat(f"Starting script {role}")
        self.ui.inProgress.setVisible(True)
        self.addToConsole(f"Executing script {role} in {path.realpath(script.proc.workingDirectory())}:")
        self.addToConsole(f"{script.body()}", QtCore.Qt.green)


    @pyqtSlot(int)
    def onScriptFinished(self):
        self.ui.inProgress.setVisible(False)
        script = self.sender()
        role = "\"" + script.role() + "\""
        exitCode = script.proc.exitCode()
        self.addToConsole(f"Script {role} stopped after {int(script.time)}s with exit code {exitCode}.")
        if exitCode:
            self.addErrToConsole(f"WARNING! Exit code {exitCode} of script {role} indicates error.")


    @pyqtSlot()
    def needReinitiation(self):
        self.ui.width.setValue(0)
        self.ui.hight.setValue(0)
        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.widget(tabIdx).setEnabled(False)


    def update_initiate_state(self):
        self.ui.initiate.setEnabled(path.isdir(self.ui.inPath.text()) and
                                    (path.isdir(self.ui.outPath.text()) or
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
        if not path.isdir(epath):
            self.ui.expSample.addItem("Experiment does not exist")
            return
        eipath = path.join(epath, 'input')
        if not path.exists(eipath):
            self.ui.expSample.addItem("No input subdirectory")
            return

        self.ui.expSample.addItem("Loading...")
        self.update()
        QtCore.QCoreApplication.processEvents()
        samples = [name for name in sorted(os.listdir(eipath))
                   if path.isdir(path.join(eipath, name))]
        self.ui.expSample.clear()
        self.ui.expSample.setStyleSheet('')
        self.ui.expSample.addItems(samples)
        if ciName[:len(eipath)] == eipath:
            sample = ciName[len(eipath):].lstrip(path.sep)
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
        self.ui.inPath.setText(path.join(epath, 'input', sample))
        self.ui.outPath.setText(path.join(epath, 'output', sample))


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
        if not path.isdir(ipath):
            self.ui.inPath.setStyleSheet(warnStyle)
            return

        cfgName = ''
        attempt = 0
        while True:
            n_cfgName = path.join(ipath, f"acquisition.{attempt}.configuration")
            if path.exists(n_cfgName):
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
        self.ui.ignoreLog.setVisible(path.exists(logName))
        logInfo = []
        if path.exists(logName) and not self.ui.ignoreLog.isChecked() :
            grepsPps = ""
            if self.ui.excludes.isVisible() and self.ui.excludes.text():
                for grep in self.ui.excludes.text().split():
                    grepsPps += f" | grep -v -e '{grep}' "
            labels = os.popen('cat ' + path.join(ipath, "acquisition*log")
                                 + ' | ' + execPath + 'imbl-log.py'
                                 + ' | tail -n +3 | cut -d\' \' -f2 | cut -d\':\' -f 1 '
                                 + grepsPps).read().strip("\n").replace("\n", " ")
            logInfo = os.popen('cat ' + path.join(ipath, "acquisition*log")
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
        if not path.isdir(opath):
            self.ui.outPath.setStyleSheet(
                warnStyle if self.ui.individualIO.isChecked() else "")
            return
        self.ui.outPath.setStyleSheet('')
        os.chdir(opath)

        initiatedFile = path.join(opath, initFileName)
        if not path.exists(initiatedFile):
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
        self.ui.testSubDir.addItems(filemask.split() if sds else ["."])
        self.ui.testSubDir.setVisible(sds)
        self.ui.testSubDirLabel.setVisible(sds)
        self.ui.procThis.setVisible(sds)
        setMyMax(self.ui.testProjection, pjs)
        setMyMax(self.ui.minProj, pjs)
        setMyMax(self.ui.maxProj, pjs)

        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.widget(tabIdx).setEnabled(True)
        self.update_reconstruction_state()


    @pyqtSlot()
    def on_initiate_clicked(self):
        if self.scrInitiate.isRunning():
            self.scrInitiate.stop()
            return

        opath = self.ui.outPath.text()
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
            labels = os.popen('cat ' + path.join(self.ui.inPath.text(), "acquisition*log")
                                 + ' | ' + execPath + 'imbl-log.py'
                                 + ' | tail -n +3 | cut -d\' \' -f2 | cut -d\':\' -f 1 '
                                 + grepsPps).read().strip("\n").replace("\n", " ")
            command += f" -L \"{labels}\" "
        command += f" -o \"{opath}\" "
        command += f" \"{self.ui.inPath.text()}\" "

        self.needReinitiation()
        self.ui.initInfo.setEnabled(False)
        self.ui.initiate.setStyleSheet(warnStyle)
        self.ui.initiate.setText('Stop')

        if not self.ui.individualIO.isChecked() and \
           not path.isdir(opath):
            os.makedirs(opath, exist_ok=True)
        self.scrInitiate.setBody(command)
        self.scrInitiate.exec()

        self.ui.initInfo.setEnabled(True)
        self.ui.initiate.setStyleSheet('')
        self.ui.initiate.setText('Initiate')
        self.on_outPath_textChanged()
        if self.ui.procAfterInit.isChecked():
            self.ui.procAll.click()


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


    @pyqtSlot(int)
    def onMinMaxProjectionChanged(self):
        minProj = self.ui.minProj.value()
        maxProj = self.ui.maxProj.value()
        if maxProj == self.ui.maxProj.minimum():
            maxProj = int(self.ui.projections.text())
        nstl = "" if minProj <= maxProj else warnStyle
        self.ui.minProj.setStyleSheet(nstl)
        self.ui.maxProj.setStyleSheet(nstl)


    @pyqtSlot()
    @pyqtSlot(str)
    def on_maskPath_textChanged(self):
        maskOK = path.exists(self.ui.maskPath.text()) or not len(self.ui.maskPath.text().strip())
        self.ui.maskPath.setStyleSheet("" if maskOK else warnStyle)


    def common_test_proc(self, wdir, actButton, ars=None):
        if self.scrStitch.isRunning():
            self.scrStitch.stop()
            return -1

        prms = " "
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

        disableWdgs = [ wdg for wdg in [*self.configObjects, *self.ui.findChildren(QtWidgets.QAbstractButton)]
                            if wdg is not actButton and wdg is not self.ui.termini
                               and not isinstance(wdg, QtWidgets.QButtonGroup) ]
        for wdg in disableWdgs:
            wdg.setEnabled(False)
        actText = actButton.text()
        actButton.setStyleSheet(warnStyle)
        actButton.setText('Stop')

        self.scrStitch.proc.setWorkingDirectory(wdir)
        self.scrStitch.setBody(execPath + "imbl-stitch.sh" + prms)
        toRet = self.scrStitch.exec()

        for wdg in disableWdgs:
            wdg.setEnabled(True)
        actButton.setText(actText)
        actButton.setStyleSheet("")
        self.on_sameBin_toggled()  # to correct state of the yBin
        self.update_reconstruction_state()
        return toRet


    @pyqtSlot()
    def on_testProj_clicked(self):
        self.collectOut = ""
        ars = f" -t {self.ui.testProjection.value()}"
        wdir = path.join(self.ui.outPath.text(),
                            self.ui.testSubDir.currentText())
        hasFailed = self.common_test_proc(wdir, self.ui.testProj, ars)
        lastLine = self.collectOut.splitlines()[-1]
        self.collectOut = None
        if hasFailed or not lastLine or not (lres := re.search('^([0-9]+) ([0-9]+) ([0-9]+) (.*)', lastLine)):
            return
        z, y, x, imageFile = lres.groups()
        self.addToConsole(f"Results of stitching projection {self.ui.testProjection.value()}"
                          f" are in {path.realpath(imageFile)}."
                          f" Stitched volume will be {x}(w) x {y}(h) x {z}(d) pixels (at least "
                          + '{0:,}'.format(4*int(x)*int(y)*int(z)).replace(',', ' ')+" B in size).")
        if not self.ui.recAfterStitch.isChecked() or not self.ui.distance.value() or not self.ui.d2b.value():
            return # no phase retruval
        imcomp = path.splitext(imageFile)
        oImageFile = imcomp[0] + "_phase" + imcomp[1]
        self.scrPhase.setBody(f" ctas ipc {imageFile} -o {oImageFile} -e "
                              f" -z {self.ui.distance.value()}"
                              f" -d {self.ui.d2b.value()}"
                              f" -r {self.ui.pixelSize.value()}"
                              f" -w {12.398/self.ui.energy.value()} ") # keV to Angstrom
        self.scrPhase.proc.setWorkingDirectory(wdir)
        if not self.scrPhase.exec():
            self.addToConsole(f"Results of phase retrival are in"
                              f" {path.realpath(oImageFile)}.")


    @pyqtSlot()
    def onStitch(self):
        ars = ( "" if self.ui.wipeStitched.isChecked() else " -w " ) \
            + ( "" if self.ui.saveStitched.isChecked() else " -s " )
        subOnStart = self.ui.testSubDir.currentIndex()
        pidxs = [subOnStart] if self.sender() is self.ui.procThis else \
                range(self.ui.testSubDir.count())
        for curIdx in pidxs:
            self.ui.testSubDir.setCurrentIndex(curIdx)
            subdir = self.ui.testSubDir.currentText()
            wdir = path.join(self.ui.outPath.text(), subdir)
            self.saveConfiguration(path.join(wdir, self.configName))
            self.common_test_proc(wdir, self.ui.procAll, ars)
        self.ui.testSubDir.setCurrentIndex(subOnStart)
        self.update_reconstruction_state()


    def inMemNamePrexix(self):
        cOpath = path.join(self.ui.outPath.text(), self.ui.testSubDir.currentText())
        cOpath = path.realpath(cOpath)
        return f"/dev/shm/imblproc_{cOpath.replace('/','_')}_"


    def update_reconstruction_state(self):
        file_postfix = "clean.hdf"
        memName = self.inMemNamePrexix() + file_postfix
        diskName=path.join(self.ui.outPath.text(), self.ui.testSubDir.currentText(), file_postfix)
        projFile = memName if path.exists(memName) else diskName
        x, y, z = hdf5shape(projFile, "data")
        projShape = f"{x} x {y} x {z}" if x and y and z else None
        self.ui.prShape.setText(projShape)
        self.ui.prFile.setText(projFile if projShape else "can't find projections volume.")
        self.ui.prFile.setEnabled(projShape is not None)
        self.ui.testSlice.setEnabled(projShape is not None)
        self.ui.testSliceNum.setEnabled(projShape is not None)
        self.ui.reconstruct.setEnabled(projShape is not None)


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
            self.ui.ctFilterParam.setMinimum(0)
            self.ui.filterParamLabel.setVisible(True)
            self.ui.filterParamLabel.setText("Alpha parameter")

        elif self.ui.ctFilter.currentText() == "Gauss":
            self.ui.ctFilterParam.setVisible(True)
            self.ui.ctFilterParam.setMinimum(0.01)
            self.ui.filterParamLabel.setVisible(True)
            self.ui.filterParamLabel.setText("Sigma parameter")
        else:
            self.ui.ctFilterParam.setVisible(False)
            self.ui.filterParamLabel.setVisible(False)


    @pyqtSlot()
    def on_wipe_clicked(self):
        Script.run(f"rm -rf {self.inMemNamePrexix()}*")


    @pyqtSlot()
    def on_testSlice_clicked(self):
        if self.scrRec.isRunning():
            self.scrRec.stop()
            return -1


    @pyqtSlot()
    def on_reconstruct_clicked(self):
        if self.scrRec.isRunning():
            self.scrRec.stop()
            return -1

        wdir = path.join(self.ui.outPath.text(), self.ui.testSubDir.currentText())
        projFile = path.realpath(self.ui.prFile.text())
        x, y, z = hdf5shape(projFile, "data")
        if not x or not y or not z:
            self.addErrToConsole(f"Can't find projections in file \"{projFile}\". Aborting reconstruction.")
            return -1
        step = 0
        try:
            myInitFile = path.join(wdir,initFileName)
            _, outed, _ = Script.run(f"cat {myInitFile} | grep 'step=' | cut -d'=' -f 2 ")
            step = abs(float(outed))
            if step == 0:
                raise Exception("Step is 0.")
        except Exception:
            self.addErrToConsole(f"Failed to get step from init file \"{myInitFile}\". Aborting reconstruction.")
            return -1
        ark180 = int(180.0/step) + 1
        if ark180 >= z:
            self.addErrToConsole(f"Not enough projections {z} for step {step} to form 180 deg ark. Aborting reconstruction.")
            return -1

        if self.ui.autocor.isChecked():
            self.collectOut = ""
            self.scrCOR.setBody(f"ctas ax {projFile}:/data:0 {projFile}:/data:{ark180}")
            self.scrCOR.proc.setWorkingDirectory(wdir)
            self.scrCOR.exec()
            try:
                cor = float(self.collectOut)
                self.ui.cor.setValue(cor)
            except Exception:
                self.addErrToConsole(f"Failed to calculate rotation centre. Aborting reconstruction.")
                return -1
            self.collectOut = None

        command = ""
        ringLine = "" if self.ui.ring.value() == 0 else \
            f"ctas ring -v -R {self.ui.ring.value()} {projFile}:/data:y \n"
        phaseLine = "" if self.ui.distance.value() == 0 or self.ui.d2b.value() == 0.0 else \
            f"ctas ipc {projFile}:/data -e -v " \
            f" -z {self.ui.distance.value()}" \
            f" -d {self.ui.d2b.value()}" \
            f" -r {self.ui.pixelSize.value()}" \
            f" -w {12.398/self.ui.energy.value()} \n"  # keV to Angstrom
        if self.ui.ringGroup.checkedButton() is self.ui.ringBeforePhase :
            command = ringLine + phaseLine
        else:
            command = phaseLine + ringLine

        fltLine = self.ui.ctFilter.currentText().upper()
        if self.ui.ctFilterParam.isVisible():
            fltLine += f":{self.ui.ctFilterParam.value()}"
        kontrLine = "FLT" if fltLine == "NONE" else "ABS"
        fltLine = "" if fltLine == "NONE" else f" -f {fltLine}"
        mmLine = f" -m {self.ui.min.value()} -M {self.ui.max.value()}" \
            if self.ui.resTIFF.isChecked() and self.ui.resToInt.isChecked() else ""
        outPath = ""
        if self.ui.resTIFF.isChecked():
            odir = "rec8int" if self.ui.resToInt.isChecked() else "rec"
            Script.run(f"mkdir -p {path.join(wdir,odir)} ")
            outPath = path.join(odir,"rec_@.tif")
        else:
            outPath = "rec.hdf:/data"
        command += f"ctas ct -v {projFile}:/data:y " \
                   f" -o {outPath}" \
                   f" -k {kontrLine} " \
                   f" -c {self.ui.cor.value()}" \
                   f" -a {step} -r {self.ui.pixelSize.value()}" \
                   f"{fltLine}" \
                   f"{mmLine}" \
                   "\n"

        self.addToConsole(f"Reconstruction command: {command}", QtCore.Qt.magenta)








    @pyqtSlot()
    def update_termini_state(self):
        isrunning = False
        for script in self.ui.findChildren(Script):
            isrunning = isrunning or script.isRunning()
        self.ui.termini.setEnabled(isrunning)
        self.ui.termini.setStyleSheet(warnStyle if isrunning else "")


    @pyqtSlot()
    def on_termini_clicked(self):
        for script in self.ui.findChildren(Script):
            script.stop()





signal.signal(signal.SIGINT, signal.SIG_DFL) # Ctrl+C to quit
app = QApplication(sys.argv)
my_mainWindow = MainWindow()
my_mainWindow.show()
sys.exit(app.exec_())
