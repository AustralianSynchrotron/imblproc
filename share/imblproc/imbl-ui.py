#!/usr/bin/env python3

import sys, os, re, psutil, time, signal, argparse
from os import path
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QSettings, QProcess, QEventLoop, QObject, QTimer
from PyQt5.QtWidgets import QFileDialog, QApplication
from PyQt5.uic import loadUi
from xml.sax.saxutils import escape
from argparse import RawTextHelpFormatter


myPath = path.dirname(path.realpath(__file__)) + path.sep
execPath = path.realpath(path.join(myPath, "..", "..", "bin") )
uiPath = myPath
#uiPath = path.join(execPath, "..", "share", "imblproc")
warnStyle = 'background-color: rgba(255, 0, 0, 128);'
initFileName = '.initstitch'
listOfCreatedMemFiles = []


def onBrowse(wdg, desc, forFile=False):
    dest = ""
    if forFile:
        dest, _filter = QFileDialog.getOpenFileName(wdg, desc, wdg.text())
    else:
        dest = QFileDialog.getExistingDirectory(wdg, desc, wdg.text())
    if dest:
        wdg.setText(dest)



class Script(QObject) :

    shell = os.environ['SHELL'] if 'SHELL' in os.environ else "/bin/sh"
    bodySet = pyqtSignal()
    finished = pyqtSignal(int)
    started = pyqtSignal()
    scriptPrefix = "script_"
    procPrefix = "proc_"


    def __init__(self, parent=None):
        super(Script, self).__init__(parent)
        self.fileExec = QtCore.QTemporaryFile()
        if not self.fileExec.open():
            print("ERROR! Unable to open temporary file.")
            return
        self.proc = QProcess(self)
        self.proc.setProgram(self.shell)
        self.proc.stateChanged.connect(self.onState)
        self.time=0
        self.dryRun = False


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
        body=body.strip()
        if not body:
            return
        body += "\n"
        self.fileExec.write(body.encode())
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
        if self.dryRun:
            self.started.emit()
            print(f"Dry run for:\n{self.body()}")
            self.finished.emit(True)
            return True
        else:
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
        self.ui = loadUi(path.join(uiPath, "script.ui"), self)
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
    # with locking used, following commands may work very slow if the file was not closed properly
    Script.run(f"HDF5_USE_FILE_LOCKING=FALSE h5clear -s --increment {filename}")
    outed = Script.run(f"export HDF5_USE_FILE_LOCKING=FALSE ; "
                       f"h5clear -s --increment {filename} 2>&1 /dev/null ; "
                       f"h5ls {filename}/{dataset}")[1]
    if lres := re.search('.*{([0-9]+), ([0-9]+), ([0-9]+)}.*', outed) :
        return int(lres.group(3)), int(lres.group(2)), int(lres.group(1))
    else:
        return None, None, None



class ScrollToEnd(QObject):
    def __init__(self, parent):
        super(ScrollToEnd, self).__init__(parent)
    def eventFilter(self, obj, event):
        if isinstance(self.parent(), QtWidgets.QTextBrowser) and event.type() == QtCore.QEvent.Resize:
            scrollBar = self.parent().verticalScrollBar()
            if scrollBar.value() == scrollBar.maximum():
                QtCore.QTimer.singleShot(100, self.scrollMe)
        return False
    def scrollMe(self):
        if isinstance(self.parent(), QtWidgets.QTextBrowser):
            scrollBar = self.parent().verticalScrollBar()
            scrollBar.setValue(scrollBar.maximum())



class MainWindow(QtWidgets.QMainWindow):

    configName = ".imbl-ui"
    historyName = ".proc.history"
    etcConfigName = path.join(path.expanduser("~"), configName)
    amLoading = False
    placePrefix="placeScript_"
    cfgProp="saveInConfig" # objects with this property (containing int read order) will be saved in config


    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = loadUi(path.join(uiPath, "imbl-ui.ui"), self)

        # place Script UI's
        self.scrProc = Script(self)
        for place in self.ui.findChildren(QtWidgets.QLayout, QtCore.QRegExp(self.placePrefix+"\w+")):
            role = place.objectName().removeprefix(self.placePrefix)
            scrw = UScript(self.ui)
            scrw.setRole(role)
            scrw.setProperty(self.cfgProp, 2)
            place.addWidget(scrw)
        #self.cResizer = ColumnResizer(self)
        #self.cResizer.addWidgetsFromLayout(self.ui.tabRec.layout(), 4)
        #for script in self.ui.tabRec.findChildren(UScript):
        #    self.cResizer.addWidgetsFromLayout(script.ui.layout(), 1)
        for script in self.ui.findChildren(Script):
            self.ui.outPath.textChanged.connect(script.proc.setWorkingDirectory)
            script.proc.readyReadStandardOutput.connect(self.parseScriptOut)
            script.proc.readyReadStandardError.connect(self.parseScriptOut)
            script.started.connect(self.onScriptStarted)
            script.finished.connect(self.onScriptFinished)
            script.proc.stateChanged.connect(self.update_termini_state)
        self.collectOut = None
        self.collectErr = None

        # prepare UI elements
        self.on_individualIO_toggled()
        self.on_ctFilter_currentTextChanged()
        self.ui.noConfigLabel.hide()
        self.ui.oldConfigLabel.hide()
        self.ui.inProgress.setVisible(False)
        self.ui.termini.setVisible(False)
        self.ui.recInMemOnly.setVisible(False)
        self.ui.autoMin.setVisible(False) # feature not implemented
        self.ui.autoMax.setVisible(False) # feature not implemented
        self.ui.cleanToMemory.setVisible(False)
        self.ui.console.installEventFilter(ScrollToEnd(self.ui.console))

        # add status bar elements
        saveBtn = QtWidgets.QPushButton("Save", self.ui)
        saveBtn.setFlat(True)
        saveBtn.clicked.connect(lambda : self.saveConfiguration(""))
        self.ui.statusBar().addPermanentWidget(saveBtn)
        loadBtn = QtWidgets.QPushButton("Load", self.ui)
        loadBtn.setFlat(True)
        loadBtn.clicked.connect(lambda : self.loadConfiguration(""))
        self.ui.statusBar().addPermanentWidget(loadBtn)

        # prepare list of disabled elements
        self.doYst = False
        self.doZst = False
        self.doFnS = False
        exceptFromDisabled = [ self.ui.tabWidget.tabBar(), *self.ui.tabConsole.findChildren(QtWidgets.QWidget)]
        exceptMe = self.ui.tabConsole
        while isinstance(exceptMe, QtWidgets.QWidget):
            exceptFromDisabled.append(exceptMe)
            exceptMe = exceptMe.parent()
        self.disabledWidgetws = [ wdg for wdg in self.ui.findChildren(QtWidgets.QWidget)
                                      if wdg not in exceptFromDisabled ]
        self.wereDisabled = []

        # to implement stitch geometry adjustment on binning changes
        self.previousBinn = None
        self.ui.xBin.valueChanged.connect(self.onBinChange)
        self.ui.yBin.valueChanged.connect(self.onBinChange)
        self.ui.sameBin.toggled.connect(self.onBinChange)
        self.ui.binAdjust.toggled.connect(self.onBinChange)

        # connect signals which are not connected by name
        self.ui.notFnS.clicked.connect(self.needReinitiation)
        self.ui.ignoreLog.clicked.connect(self.needReinitiation)
        self.ui.yIndependent.clicked.connect(self.needReinitiation)
        self.ui.zIndependent.clicked.connect(self.needReinitiation)
        self.ui.inInclude.editingFinished.connect(self.needReinitiation)
        self.ui.inExclude.editingFinished.connect(self.needReinitiation)
        self.ui.inInclude.editingFinished.connect(self.on_inPath_textChanged)
        self.ui.inExclude.editingFinished.connect(self.on_inPath_textChanged)
        self.ui.expUpdate.clicked.connect(self.on_expPath_textChanged)
        self.ui.ignoreLog.toggled.connect(self.on_inPath_textChanged)
        self.ui.minProj.valueChanged.connect(self.onMinMaxProjectionChanged)
        self.ui.maxProj.valueChanged.connect(self.onMinMaxProjectionChanged)
        self.ui.testSubDir.currentTextChanged.connect(self.update_reconstruction_state)
        self.ui.prFile.clicked.connect(lambda :
            QApplication.clipboard().setText(path.realpath(self.ui.prFile.text())))

        # prepare list of config patrameters and make them updated in auto-saved config
        confsWithOrder = { obj: obj.property(self.cfgProp) for obj in self.ui.findChildren(QObject)
                                                      if obj.property(self.cfgProp) is not None}
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

        # parse commandline arguments
        parser = argparse.ArgumentParser(description='IMBL processing pipeline.',
                                         allow_abbrev=False,
                                         formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('config', type=str, nargs='?',
                            help='Configuration file to load on start. Default: ~/' + self.configName,
                            default=self.etcConfigName)
        parser.add_argument("-I", "--init", action='store_true', help="Launches sample initiation." \
                                                                 " Proceeds to further step(s) if set.")
        parser.add_argument("-P", "--proj", action='store_true', help="Launches projections formation." \
                                                                 " Proceeds to reconstruction(s) if set.")
        parser.add_argument("--proj-one", action='store_true', help=
                            "Launches projection formation for a single sub-sample. Proceeds to reconstruction if set." )
        parser.add_argument("--proj-test", action='store_true', help="Launches test of stitching procedure.")
        parser.add_argument("-R", "--rec", action='store_true', help="Launches CT and related processing.")
        parser.add_argument("--rec-test", action='store_true', help="Launches test of CT reconstruction.")
        pgrp = parser.add_mutually_exclusive_group()
        pgrp.add_argument("-H", "--headless", action='store_true', help="Starts pipeline withoput UI." \
                                         " Only makes sense with one of the above processing launchers.")
        pgrp.add_argument("-U", "--keep-ui", action='store_true', help="Does not exit after launcher finishes.")
        awdg = self.ui.tabWidget
        while isinstance(awdg := awdg.nextInFocusChain(), QtWidgets.QWidget) and \
              awdg is not self.ui.tabWidget:
            if awdg.property(self.cfgProp) is not None:
                name = awdg.objectName()
                help = awdg.toolTip().replace("f ticked", "f true") \
                    if isinstance(awdg, QtWidgets.QWidget) else ""
                if isinstance(awdg, QtWidgets.QLineEdit):
                    parser.add_argument(f"--{name}" , type=str, metavar="STR", help=help)
                elif isinstance(awdg, QtWidgets.QCheckBox):
                    parser.add_argument(f"--{name}" , type=bool, metavar="BOOL", help=help)
                elif isinstance(awdg, QtWidgets.QSpinBox):
                    parser.add_argument(f"--{name}" , type=int, metavar="INT", help=help)
                elif isinstance(awdg, QtWidgets.QDoubleSpinBox):
                    parser.add_argument(f"--{name}" , type=float, metavar="FLOAT", help=help)
                elif isinstance(awdg, QtWidgets.QComboBox):
                    listOfItems = [ awdg.itemText(i) for i in range(0,awdg.count()) ]
                    help += f" Possible values are: {listOfItems}" if len(listOfItems) else ""
                    parser.add_argument(f"--{name}" , type=str, metavar="STR", choices=listOfItems, help = help)
                elif isinstance(awdg, UScript):
                    parser.add_argument(f"--{name}" , type=str, metavar="STR",
                                        help = f"Script is executed before {awdg.role()}.")
        for grp in self.ui.findChildren(QtWidgets.QButtonGroup):
            if not grp.buttons():
                continue
            name = grp.objectName()
            help = "Possible values are:\n"
            for butt in grp.buttons() :
                help += f"'{butt.objectName()}' - {butt.toolTip()}\n"
            parser.add_argument(f"--{name}" , type=str, metavar="STR", choices=listOfItems, help=help)
        args = parser.parse_args()

        # reformat tool tips limiting horizontal box size and adding parameter name.
        # must happen after CMD parsing because toolTips are used as help text there.
        minToolTipWidth = 400
        fm = QtGui.QFontMetrics(QtGui.QFont())
        for swdg in self.ui.findChildren(QtWidgets.QWidget):
            tip = swdg.toolTip().strip()
            if not tip or tip[:6] == '<html>' :
                continue
            addParam = "Parameter name: " + swdg.objectName() if swdg.property(self.cfgProp) is not None else ""
            minWidth = max(minToolTipWidth, fm.width(addParam))
            if len(addParam):
                addParam = "<br><p>" + addParam + "</p>"
            tip_width = fm.width(tip)
            escape(tip)
            if tip_width <= minWidth :
                tip += "</p>"
            else:
                line_break_index = len(tip) * minWidth // tip_width
                tip = tip[:line_break_index] + "</p>" + tip[line_break_index:]
            swdg.setToolTip("<style>p { margin: 0 0 0 0 }</style><p style='white-space:pre'>" +
                                tip + addParam )

        # This will run only after QApplication was executed
        def afterStart() :
            self.ui.setEnabled(False)
            if not args.headless:
                self.show()
            self.loadConfiguration(args.config, vars(args))
            self.ui.setEnabled(True)
            acted = False
            if args.init:
                acted = True
                self.on_initiate_clicked()
            if args.proj_test:
                acted = True
                self.on_testProj_clicked()
            if args.proj_one:
                acted = True
                self.on_procThis_clicked()
            if args.proj:
                acted = True
                self.on_procAll_clicked()
            if args.rec_test:
                acted = True
                self.on_testSlice_clicked()
            if args.proj:
                acted = True
                self.on_reconstruct_clicked()
            if args.headless and not acted:
                QtCore.QTimer.singleShot(0, self.close)
                raise SyntaxError("No action launch requested in the headless mode.")
            if acted and not args.keep_ui:
                QtCore.QTimer.singleShot(0, self.close)
        QtCore.QTimer.singleShot(0, afterStart)


    def canSee(self, wdg):
        return wdg.isVisibleTo(self.ui.centralWidget())


    def execScrRole(self, role):
        for script in self.ui.findChildren(Script):
            if script.role() == role:
                return script.exec()
        return -1


    def execScrProc(self, role, command, wdir=None):
        if wdir is not None and wdir:
            self.scrProc.proc.setWorkingDirectory(wdir)
        self.scrProc.setRole(role)
        self.scrProc.setBody(command)
        return self.scrProc.exec()


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
                return swdg.checkedButton().objectName() if swdg.checkedButton() else ""

        for swdg in self.configObjects:
            config.setValue(swdg.objectName(), valToSave(swdg))


    @pyqtSlot()
    def loadConfiguration(self, fileName=etcConfigName, vargs={}):

        if not fileName:
            newfile, _filter = QFileDialog.getOpenFileName(
                self, "IMBL processing configuration",
                directory=self.ui.outPath.text())
            if newfile:
                fileName = newfile
        if not path.exists(fileName):
            print(f"Error loading configuration. File '{fileName}' does not exist.", file=sys.stderr)
            self.update_reconstruction_state()
            return

        self.amLoading = True
        config = QSettings(fileName, QSettings.IniFormat)

        def getVal(swdg, type):
            nm = swdg.objectName()
            if nm in vargs and vargs[nm] is not None:
                if isinstance(vargs[nm], type):
                    return vargs[nm]
                else:
                    errMsg = f"Parameter --{nm} of the command line produced variable of unexpected" \
                             f" type {type(vargs[nm])}, where {type} was expected."
                    print(errMsg, file=sys.stderr)
                    self.addErrToConsole(errMsg)
            elif config.contains(nm):
                return config.value(nm, type=type)
            return None

        for wdg in self.configObjects:
            if isinstance(wdg, QtWidgets.QLineEdit) and ( val := getVal(wdg,str) ) is not None :
                wdg.setText(val)
            elif isinstance(wdg, QtWidgets.QCheckBox) and ( val := getVal(wdg,bool) ) is not None :
                wdg.setChecked(val)
            elif isinstance(wdg, QtWidgets.QSpinBox) and ( val := getVal(wdg,int) ) is not None :
                if wdg.maximum() < val: wdg.setMaximum(val)
                if wdg.minimum() > val: wdg.setMinimum(val)
                wdg.setValue(val)
            elif isinstance(wdg, QtWidgets.QDoubleSpinBox) and ( val := getVal(wdg,float) ) is not None :
                if wdg.maximum() < val: wdg.setMaximum(val)
                if wdg.minimum() > val: wdg.setMinimum(val)
                wdg.setValue(val)
            elif isinstance(wdg, QtWidgets.QComboBox) and ( val := getVal(wdg,str) ) is not None :
                didx = wdg.findText(val)
                if didx >= 0:
                    wdg.setCurrentIndex(didx)
            elif isinstance(wdg, UScript) and ( val := getVal(wdg,str) ) is not None :
                wdg.ui.body.setText(val)
            elif isinstance(wdg, QtWidgets.QButtonGroup) and ( val := getVal(wdg,str) ) is not None :
                for butt in wdg.buttons():
                    if butt.objectName() == val:
                        butt.setChecked(True)
            else:
                continue
            if wdg is self.ui.outPath:
                self.on_outPath_textChanged()

        self.amLoading = False
        self.update_initiate_state()
        self.update_reconstruction_state()
        self.onBinChange()


    def addToConsole(self, text=None, qcolor=None):
        if text is None:
            text=""
        else:
            text = text.strip()
            if not text:
                return
        if not self.isVisible():
            print(text)
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
        self.ui.iwidth.setValue(0)
        self.ui.ihight.setValue(0)
        for wdg in (self.ui.testProj, self.ui.procThis, self.ui.procAll):
            wdg.setEnabled(False)
        self.ui.procAll.setText("(Re)initiate first")


    def update_initiate_state(self):
        #self.on_wipe_clicked()
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
    def on_expPath_textChanged(self, _=None):

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
    def on_expSample_currentTextChanged(self, _=None):
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
    def on_inPath_textChanged(self, _=None):

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
            cfgName = Script.run(f"ls {ipath}/acquisition.*conf* | sort -V | tail -n 1")[1].strip("\n")
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
        self.ui.inexclLabel.setVisible(serialScan)
        self.ui.inexclWidget.setVisible(serialScan)

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
            if self.canSee(self.ui.inexclWidget) :
                if self.ui.inExclude.text():
                    for grep in self.ui.inExclude.text().split():
                        grepsPps += f" | grep -v -e '{grep}' "
                if self.ui.inInclude.text():
                    grepsPps += f" | grep "
                    for grep in self.ui.inInclude.text().split():
                        grepsPps += f" -e '{grep}' "
            labels = Script.run(f"cat {path.join(ipath,'acquisition*log')} "
                                f" | {path.join(execPath,'imbl-log.py')} "
                                 " | tail -n +3 | cut -d' ' -f2 | cut -d':' -f 1"
                                f" {grepsPps}") \
                            [1].strip("\n").replace("\n", " ")
            logInfo = Script.run(f"cat {path.join(ipath, 'acquisition*log')} "
                                 f" | {path.join(execPath,'imbl-log.py')} {labels} "
                                  " | grep '# Common' | cut -d\' \' -f 4- " ) \
                            [1].strip("\n").split()
            if len(logInfo) == 3 :
                fromlog = True

        scanrange = float(logInfo[0]) if fromlog else cfg.value('scan/range', type=float)
        self.ui.scanRange.setText(str(scanrange))
        self.ui.notFnS.setVisible(scanrange >= 360)
        projections = int(logInfo[1]) if fromlog else cfg.value('scan/steps', type=int)
        self.ui.projections.setValue(projections)
        step = float(logInfo[2]) if fromlog else scanrange / projections
        self.ui.step.setText(str(step))

        self.update_initiate_state()


    @pyqtSlot()
    def on_outBrowse_clicked(self):
        onBrowse(self.ui.outPath, "Output directory")


    @pyqtSlot()
    @pyqtSlot(str)
    def on_outPath_textChanged(self, _=None):

        QtCore.QCoreApplication.processEvents()  # to update ui.outPath
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

        self.ui.iwidth.setValue(width)
        self.ui.ihight.setValue(hight)

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

        for wdg in (self.ui.testProj, self.ui.procThis, self.ui.procAll):
            wdg.setEnabled(True)
        self.ui.procAll.setText("Stitch All")
        self.update_reconstruction_state()


    @pyqtSlot()
    def on_initiate_clicked(self):
        if self.scrProc.isRunning():
            self.scrProc.stop()
            return

        self.addToConsole()

        opath = self.ui.outPath.text()
        command = path.join(execPath, "imbl-init.sh")
        command += " -v "
        if self.ui.notFnS.isChecked():
            command += " -f "
        if self.ui.yIndependent.isChecked():
            command += " -y "
        if self.ui.zIndependent.isChecked():
            command += " -z "
        if self.ui.noNewFF.isChecked():
            command += " -e "
        if not self.ui.ignoreLog.isChecked() and self.canSee(self.ui.ignoreLog) :
            command += " -l "
        if self.canSee(self.ui.inexclWidget) \
               and (self.ui.inExclude.text() or self.ui.inInclude.text()) :
            grepsPps = ""
            if self.ui.inExclude.text():
                for grep in self.ui.inExclude.text().split():
                    grepsPps += f" | grep -v -e '{grep}' "
            if self.ui.inInclude.text():
                grepsPps += f" | grep "
                for grep in self.ui.inInclude.text().split():
                    grepsPps += f" -e '{grep}' "
            labels = Script.run(f"cat {path.join(self.ui.inPath.text(), 'acquisition*log')} "
                                f" | {path.join(execPath,'imbl-log.py')} "
                                 " | tail -n +3 | cut -d' ' -f2 | cut -d':' -f 1 "
                                f" {grepsPps} " ) \
                            [1].strip("\n").replace("\n", " ")
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
        self.execScrRole("initialization")
        self.execScrProc("Initiating", command)

        self.ui.initInfo.setEnabled(True)
        self.ui.initiate.setStyleSheet('')
        self.ui.initiate.setText('Initiate')
        self.on_outPath_textChanged()
        if self.ui.procAfterInit.isChecked():
            self.ui.procAll.click()


    @pyqtSlot(int)
    @pyqtSlot(bool)
    def onBinChange(self):
        self.ui.yBin.setEnabled(not self.ui.sameBin.isChecked())
        if self.amLoading :
            return
        if self.ui.sameBin.isChecked():
            self.ui.yBin.setValue(self.ui.xBin.value())
        def correctVal(wdg, adj) :
            cval = wdg.value()
            # explicit type conversion below needed to address bug
            # https://bugs.launchpad.net/rapid/+bug/1946407
            nval = type(cval)(adj*cval)
            wdg.setValue(nval)
        if self.ui.binAdjust.isChecked() and self.previousBinn :
            if self.ui.xBin.value() != self.previousBinn[0] :
                xadj = self.previousBinn[0] / self.ui.xBin.value()
                for xwdg in [ self.ui.iStX, self.ui.oStX, self.ui.fStX,
                              self.ui.fCropLeft, self.ui.fCropRight, self.ui.cor ] :
                    correctVal(xwdg, xadj)
            if self.ui.yBin.value() != self.previousBinn[1] :
                yadj =  self.previousBinn[1] / self.ui.yBin.value()
                for ywdg in [ self.ui.iStY, self.ui.oStY, self.ui.fStY,
                              self.ui.fCropTop, self.ui.fCropBottom ] :
                    correctVal(ywdg, yadj)
        self.previousBinn = [ self.ui.xBin.value(), self.ui.yBin.value() ]


    @pyqtSlot()
    def on_maskBrowse_clicked(self):
        onBrowse(self.ui.maskPath, "Mask image.", True)


    @pyqtSlot(int)
    def onMinMaxProjectionChanged(self):
        minProj = self.ui.minProj.value()
        maxProj = self.ui.maxProj.value()
        if maxProj == self.ui.maxProj.minimum():
            maxProj = self.ui.projections.value()
        nstl = "" if minProj <= maxProj else warnStyle
        self.ui.minProj.setStyleSheet(nstl)
        self.ui.maxProj.setStyleSheet(nstl)


    @pyqtSlot()
    @pyqtSlot(str)
    def on_maskPath_textChanged(self, _=None):
        maskOK = path.exists(self.ui.maskPath.text()) or not len(self.ui.maskPath.text().strip())
        self.ui.maskPath.setStyleSheet("" if maskOK else warnStyle)


    def enableWidgets(self, onlyMe=None):
        enableAll = onlyMe is None
        topDisable = not enableAll and self.ui.statusBar().isEnabled()
        if topDisable:
            self.wereDisabled = []
        for wdg in self.disabledWidgetws :
            if topDisable and not wdg.isEnabledTo(wdg.parent()):
                self.wereDisabled.append(wdg)
            wdg.setEnabled(enableAll and wdg not in self.wereDisabled)
        while isinstance(onlyMe, QtWidgets.QWidget):
            onlyMe.setEnabled(True)
            onlyMe = onlyMe.parent()


    def common_stitch(self, wdir, actButton, ars=None):

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
        if 0.0 != self.ui.maskEdge.value():
            prms += f" -E {self.ui.maskEdge.value()} "
        crops = (self.ui.sCropTop.value(), self.ui.sCropLeft.value(),
                 self.ui.sCropBottom.value(), self.ui.sCropRight.value())
        if sum(crops):
            prms += " -c %i,%i,%i,%i " % crops
        crops = (self.ui.fCropTop.value(), self.ui.fCropLeft.value(),
                 self.ui.fCropBottom.value(), self.ui.fCropRight.value())
        if sum(crops):
            prms += " -C %i,%i,%i,%i " % crops
        if not self.ui.allProj.isChecked() :
            minProj = self.ui.minProj.value()
            maxProj = self.ui.maxProj.value()
            pjs = self.ui.projections.value()
            if maxProj == self.ui.maxProj.minimum()  or maxProj >= pjs  :
                maxProj = pjs
            prms += f" -m {minProj} -M {maxProj} "
        if 1 != self.ui.projBin.value() :
            prms += f" -z {self.ui.projBin.value()} "
        prms += " -v "
        if ars:
            prms += ars

        actText = actButton.text()
        actButton.setStyleSheet(warnStyle)
        actButton.setText('Stop')

        self.execScrRole("stitching")
        toRet = self.execScrProc("Stitching", path.join(execPath, "imbl-stitch.sh") + prms, wdir)

        actButton.setText(actText)
        actButton.setStyleSheet("")
        self.onBinChange()  # to correct state of the yBin
        self.update_reconstruction_state()
        return toRet


    @pyqtSlot()
    def on_testProj_clicked(self):
        if self.scrProc.isRunning():
            self.scrProc.stop()
            return -1

        self.addToConsole()
        self.enableWidgets(self.ui.testProj)
        self.collectOut = ""
        ars = f" -t {self.ui.testProjection.value()}"
        wdir = self.onStorNamePrefix()
        hasFailed = self.common_stitch(wdir, self.ui.testProj, ars)
        lres = False if hasFailed else \
            re.search('^([0-9]+) ([0-9]+) ([0-9]+) (.*)', self.collectOut.splitlines()[-1])
        self.collectOut = None
        if not hasFailed and lres:
            z, y, x, imageFile = lres.groups()
            imageFile =  Script.run(f"cd {wdir} ; realpath {imageFile}")[1].strip()
            self.addToConsole(f"Results of stitching projection {self.ui.testProjection.value()}"
                              f" are in {imageFile}."
                              f" Stitched volume will be {x}(w) x {y}(h) x {z}(d) pixels (at least "
                              + '{0:,}'.format(4*int(x)*int(y)*int(z)).replace(',', ' ')+" B in size).")
            if self.ui.distance.value() and self.ui.d2b.value():
                # phase proc
                imcomp = path.splitext(imageFile.strip())
                oImageFile = imcomp[0] + "_phase" + imcomp[1]
                Script.run(f"cp -f {imageFile} {oImageFile} ")
                if self.applyPhase(oImageFile):
                    self.execScrProc("Cleaning phase image.", f"rm -f {oImageFile} " )
                else:
                    self.addToConsole(f"Results of phase retrival are in {path.realpath(oImageFile)}.")
        self.enableWidgets()


    @pyqtSlot()
    def on_procThis_clicked(self):
        self.onStitch(False)


    @pyqtSlot()
    def on_procAll_clicked(self):
        self.onStitch(True)


    def onStitch(self, doAll):
        if self.scrProc.isRunning():
            self.scrProc.stop()
            return -1

        self.saveConfiguration(path.join(self.ui.outPath.text(), self.configName))
        self.addToConsole()
        actBut = self.ui.procAll if doAll else self.ui.procThis
        subOnStart = self.ui.testSubDir.currentIndex()
        pidxs = [subOnStart] if actBut is self.ui.procThis else range(self.ui.testSubDir.count())
        ars = ( "" if self.ui.wipeStitched.isChecked() else " -w " ) \
            + ( "" if self.ui.saveStitched.isChecked() else " -s " )
        for curIdx in pidxs:
            self.ui.testSubDir.setCurrentIndex(curIdx)
            wdir = self.onStorNamePrefix()
            self.enableWidgets(actBut)
            if self.common_stitch(wdir, actBut, ars) :
                break
            self.update_reconstruction_state()
            projFile = path.realpath(self.ui.prFile.text())
            if not path.exists(projFile):
                self.addErrToConsole(f"Can't find stitched projections.")
                break
            dgln=len(f"{self.ui.maxProj.value()-1}")
            for ridx in 0, 1, 2, 3, 4:
                idx = self.ui.minProj.value() + ridx * (self.ui.maxProj.value() - self.ui.minProj.value() - 1) / 4
                idx = int(idx)
                Script.run(f"ctas v2v {projFile}:/data:{idx} -o {wdir}/clean_{idx:0{dgln}d}.tif")
            if self.ui.recAfterProj.isChecked() and self.on_reconstruct_clicked():
                break
        self.ui.testSubDir.setCurrentIndex(subOnStart)
        self.enableWidgets()
        self.update_reconstruction_state()


    def onStorNamePrefix(self):
        return path.join(self.ui.outPath.text(), self.ui.testSubDir.currentText(), '')


    def inMemNamePrexix(self):
        global listOfCreatedMemFiles
        cOpath = path.realpath(self.onStorNamePrefix())
        toRet = f"/dev/shm/imblproc_{cOpath.replace('/','_')}_"
        if 'InMemIndicator' in os.environ:
            print(f"{os.environ['InMemIndicator']}{toRet}")
        if toRet not in listOfCreatedMemFiles:
            listOfCreatedMemFiles.append(toRet)
        return toRet


    @pyqtSlot()
    def on_cleanToMemory_clicked(self):
        file_postfix = "clean.hdf"
        memName = self.inMemNamePrexix() + file_postfix
        diskName = self.onStorNamePrefix() + file_postfix
        if not path.exists(diskName):
            return
        self.enableWidgets(self.ui.prFile)
        if self.execScrProc("Copying projections into memory.", f"  cp '{diskName}' '{memName}' " ) :
            self.addErrToConsole(f"Filed to copy cleaned projections file {diskName} into memory {memName}."
                                  " Most probable cause is insufficient free memory."
                                  " You may try to reconstruct from storage, but it is slow.")
        else:
            self.update_reconstruction_state()
        self.enableWidgets()


    def update_reconstruction_state(self):
        file_postfix = "clean.hdf"
        memName = self.inMemNamePrexix() + file_postfix
        diskName = self.onStorNamePrefix() + file_postfix
        inMem = path.exists(memName)
        self.ui.cleanToMemory.setVisible(not inMem and path.exists(diskName))
        projFile = memName if inMem else diskName
        projFile = path.realpath(projFile)
        x, y, z = hdf5shape(projFile, "data")
        projShape = f"{x} x {y} x {z}" if x and y and z else None
        recFile = self.inMemNamePrexix() + "rec.hdf"
        x, y, z = hdf5shape(recFile, "data")
        recShape = f"{x} x {y} x {z}" if x and y and z else None
        enableRec = projShape is not None
        self.ui.testSlice.setEnabled(enableRec)
        self.ui.testSliceNum.setEnabled(enableRec)
        self.ui.reconstruct.setEnabled(enableRec)
        if enableRec:
            self.ui.prShape.setText(projShape)
            self.ui.prFile.setText(projFile)
            self.ui.prFile.setEnabled(True)
        elif recShape is not None:
            self.ui.prShape.setText(recShape)
            self.ui.prFile.setText(recFile)
            self.ui.prFile.setEnabled(True)
        else:
            self.ui.prShape.setText("")
            self.ui.prFile.setText("no projection or reconstruction volumes found in memory.")
            self.ui.prFile.setEnabled(False)
        if projShape is None: # check for broken link
            Script.run(f" if [ -e \"{file_postfix}\" ] && " \
                       f"    [ -n \"$(readlink {file_postfix})\" ] && " \
                       f"    [ ! -e \"$(readlink {file_postfix})\" ] ; " \
                       f" then rm -f {file_postfix} ; fi ")


    def updateRingOrderVisibility(self):
        vis = self.ui.distance.value() > 0 and self.ui.d2b.value() > 0 and self.ui.ring.value() > 0
        self.ui.ringOrderLabel.setVisible(vis)
        self.ui.ringOrderWidget.setVisible(vis)


    @pyqtSlot(int)
    def on_distance_valueChanged(self, _=None):
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
            self.ui.ctFilterOpt.setVisible(True)
            self.ui.ctFilterOpt.setMinimum(0)
            self.ui.filterParamLabel.setVisible(True)
            self.ui.filterParamLabel.setText("Alpha parameter")

        elif self.ui.ctFilter.currentText() == "Gauss":
            self.ui.ctFilterOpt.setVisible(True)
            self.ui.ctFilterOpt.setMinimum(0.01)
            self.ui.filterParamLabel.setVisible(True)
            self.ui.filterParamLabel.setText("Sigma parameter")
        else:
            self.ui.ctFilterOpt.setVisible(False)
            self.ui.filterParamLabel.setVisible(False)


    @pyqtSlot()
    def on_wipe_clicked(self):
        toRm = ""
        for rmfn in set(listOfCreatedMemFiles):
            toRm += f" {rmfn}*"
        if toRm:
            self.execScrProc("Wiping memory", f"rm -f {toRm}")
        self.update_reconstruction_state()


    def applyPhase(self, volumeDesc, saveHist=False):
        if self.ui.distance.value() == 0 or self.ui.d2b.value() == 0.0:
            return 0
        self.execScrRole("phase")
        command = f"ctas ipc {volumeDesc} -e -v " \
                                f" -z {self.ui.distance.value()}" \
                                f" -d {self.ui.d2b.value()}" \
                                f" -r {self.ui.pixelSize.value()}" \
                                f" -w {12.398/self.ui.energy.value()}"   # keV to Angstrom
        if saveHist :
            Script.run(f"echo '{command}' >> {self.historyName}")
        return self.execScrProc( "Retrieving phase", command)



    def applyRing(self, iVol, oVol=None, saveHist=False):
        if self.ui.ring.value() == 0:
            return 0
        command = f"ctas ring -v -R {self.ui.ring.value()} {iVol} " + \
                                (f" -o {oVol}" if oVol else "")
        if saveHist :
            Script.run(f"echo '{command}' >> {self.historyName}")
        return self.execScrProc( "Applying ring filter", command )


    def applyCT(self, step, istr, ostr, saveHist=False):
        fltLine = self.ui.ctFilter.currentText().upper().split()[0]
        if self.canSee(self.ui.ctFilterOpt):
            fltLine += f":{self.ui.ctFilterOpt.value()}"
        kontrLine = "FLT" if fltLine == "NONE" else "ABS"
        fltLine = "" if fltLine == "NONE" else f" -f {fltLine}"
        resLine = f" -r {self.ui.pixelSize.value()} " + \
            "" if self.ui.outMu.isChecked() else f" -w {12.398/self.ui.energy.value()}"
        mmLine = f" -m {self.ui.toIntMin.value()} -M {self.ui.toIntMax.value()} " \
            if self.ui.resTIFF.isChecked() and self.ui.resToInt.isChecked() else ""
        command =   f"ctas ct -v {istr} " \
                    f" -o {ostr}" \
                    f" -k {kontrLine} " \
                    f" -c {self.ui.cor.value()}" \
                    f" -a {step}" + \
                    resLine + fltLine + mmLine
        self.execScrRole("ct")
        if saveHist :
            Script.run(f"echo '{command}' >> {self.historyName}")
        toRet = self.execScrProc("Reconstructing", command)
        if toRet :
            self.addErrToConsole(f"Cleaning after itself on failure: {ostr}*" )

        return toRet


    def common_rec(self, isTest):

        wdir  = self.onStorNamePrefix()
        self.scrProc.proc.setWorkingDirectory(wdir)
        projFile = path.realpath(self.ui.prFile.text())
        x, y, z = hdf5shape(projFile, "data")
        if not x or not y or not z:
            self.addErrToConsole(f"Can't find projections in file \"{projFile}\". Aborting test.")
            return None
        slice= self.ui.testSliceNum.value()
        doPhase = self.ui.distance.value() > 0 and self.ui.d2b.value() > 0
        addToSl = 64 if isTest and doPhase else 0
        if slice-addToSl < 0 or slice+addToSl >= y:
            self.addErrToConsole(f"Slice {slice} is out of range [{addToSl}, {y-addToSl}). Aborting test.")
            return None
        step = 0
        try:
            myInitFile = path.join(wdir,initFileName)
            outed = Script.run(f"cat {myInitFile} | grep 'step=' | cut -d'=' -f 2 ")[1]
            step = abs(float(outed))
            if step == 0:
                raise Exception("Step is 0.")
        except Exception:
            self.addErrToConsole(f"Failed to get step from init file \"{myInitFile}\". Aborting reconstruction.")
            return None

        if self.ui.autocor.isChecked():
            ark180 = int(180.0/step) + 1
            if ark180 == z and z > 900:
                ark180 -= 1 # ease restriction on last projection, if scan has sufficient steps.
            if ark180 >= z:
                self.addErrToConsole(f"Cannot automatically calculate rotation axis because there are"
                                     f" no enough projections {z} for step {step} to form 180 deg ark"
                                     f" ({step}*({z}-1)={step*(z-1)} < 180.0)."
                                      " Calculate it manually to proceed with reconstruction.")
                return None
            cor = None
            self.collectOut = ""
            Script.run(f"mkdir -p \"tmp\"")
            if self.execScrProc( "Searching for rotation centre",
                                f"ctas ax {projFile}:/data:0 {projFile}:/data:{ark180}" + \
                                (f" -o tmp/SAMPLE_cor.tif" if isTest else "")  ) :
                return None
            try:
                cor = 0.0 if self.scrProc.dryRun else float(self.collectOut)
                self.ui.cor.setValue(cor)
            except Exception:
                self.addErrToConsole(f"Failed to calculate rotation centre.")
                return None
            #self.collectOut = ""
            #self.scrProc.setRole("Searching for rotation centre using raw sinogram.")
            #self.scrProc.setBody(f"ctas ax {rawSino} -o tmp/{outPrefix}_rawCOR.tif")
            #if self.scrProc.exec():
            #    return stopTestSlice()
            #try:
            #    cor = 0.0 if self.scrProc.dryRun else float(self.collectOut)
            #    self.ui.cor.setValue(cor)
            #except Exception:
            #    self.addErrToConsole(f"Failed to calculate rotation centre. Aborting test.")
            #    stopTestSlice()
            #    return -1
            self.collectOut = None

        return projFile, slice, y, step, wdir


    @pyqtSlot()
    def on_testSlice_clicked(self):
        if self.scrProc.isRunning():
            self.scrProc.stop()
            return -1

        self.enableWidgets(self.ui.testSlice)
        self.addToConsole()
        self.ui.testSlice.setStyleSheet(warnStyle)
        self.ui.testSlice.setText('Stop')
        phaseSubVol = None
        def onStopMe(errMsg=None):
            nonlocal phaseSubVol
            if phaseSubVol:
                self.execScrProc("Cleaning phase sub-volume", f"rm {phaseSubVol}" )
            self.ui.testSlice.setStyleSheet("")
            self.ui.testSlice.setText('Test slice')
            self.enableWidgets()
            if errMsg:
                self.addErrToConsole(errMsg)
                return -1
            else:
                return self.scrProc.proc.exitCode()

        if (commres := self.common_rec(True)) is None:
            onStopMe()
            return -1
        Script.run(f"mkdir -p \"tmp\"")
        projFile, slice, y, step, _ = commres
        dgln=len(f"{y-1}")
        testPrefix = f"tmp/SINO_{slice:0{dgln}d}"

        def saveSino(istr, ostr, role):
            return self.execScrProc(f"Saving {role} sinogram into {ostr}",
                                    f"ctas v2v {istr} -o {ostr}")

        rawSino = f"{testPrefix}_raw.tif"
        if saveSino(f"{projFile}:/data:y{slice}", rawSino, "raw"):
            return onStopMe()
        recSino = rawSino

        if self.ui.distance.value() > 0 and self.ui.d2b.value() != 0.0:

            phaseSubVol = f"{path.splitext(projFile)[0]}_phase.hdf"
            if self.execScrProc( "Extracting phase subvolume",
                                f"ctas v2v -v {projFile}:/data -o {phaseSubVol}:/data" \
                                f" -c {slice-64},0,{y-slice-64},0 ") :
                return onStopMe()

            if  self.ui.ringOrder.checkedButton() is self.ui.ringBeforePhase:
                if self.applyRing(f"{phaseSubVol}:/data:y") or \
                   saveSino(f"{phaseSubVol}:/data:y64", f"{testPrefix}_ring.tif", "ring-filtered"):
                    return onStopMe()

            phaseSino = f"{testPrefix}_phase.tif"
            if self.applyPhase(f"{phaseSubVol}:/data") or \
               saveSino(f"{phaseSubVol}:/data:y64", phaseSino, "phase-filtered"):
                return onStopMe()
            recSino = phaseSino

            if  self.ui.ringOrder.checkedButton() is self.ui.ringAfterPhase:
                ringSino = f"{testPrefix}_ring.tif"
                if self.applyRing(phaseSino, ringSino):
                    return onStopMe()
                recSino = ringSino

        elif self.ui.ring.value() != 0:
            ringSino = f"{testPrefix}_ring.tif"
            if self.applyRing(recSino, ringSino):
                return onStopMe()
            recSino = ringSino

        outPath = f"tmp/SLICE_{slice:0{dgln}d}"
        if self.ui.resTIFF.isChecked() and self.ui.resToInt.isChecked():
            outPath += "_8int"
        outPath += ".tif"
        if self.applyCT(step, recSino, outPath):
            return onStopMe()

        if self.ui.resHDF.isChecked() and self.ui.resToInt.isChecked():
            self.execScrProc( "Converting to integer",
                             f"ctas v2v {outPath} -v -o {outPath}_8int.tif  " \
                             f" -m {self.ui.toIntMin.value()} -M {self.ui.toIntMax.value()}" )
            self.scrProc.exec()

        if self.scrProc.dryRun:
            self.addErrToConsole("Dry run. No reconstruction performed.")
        return onStopMe()


    @pyqtSlot()
    def on_reconstruct_clicked(self):
        if self.scrProc.isRunning():
            self.scrProc.stop()
            return -1

        self.saveConfiguration(path.join(self.ui.outPath.text(), self.configName))
        self.addToConsole()
        recBut = self.ui.reconstruct
        self.enableWidgets(recBut)
        recBut.setStyleSheet(warnStyle)
        recBut.setText('Stop')
        delMe = None
        def onStopMe(errMsg=None):
            nonlocal delMe
            if delMe and path.exists(delMe):
                self.execScrProc("Cleaning projections volume", f"rm -f {delMe} & " )
            recBut.setStyleSheet("")
            recBut.setText('Reconstruct')
            if self.sender() is recBut:
                self.enableWidgets()
                self.update_reconstruction_state()
            else:
                recBut.setEnabled(False)
            if errMsg:
                self.addErrToConsole(errMsg)
                return -1
            else:
                return self.scrProc.proc.exitCode()

        if (commres := self.common_rec(False)) is None:
            onStopMe()
            return -1
        projFile, _, _, step, wdir = commres
        if projFile == self.onStorNamePrefix() + "clean.hdf" \
           and self.ui.saveStitched.isChecked() :
                interimFile = self.onStorNamePrefix() + "clean_deleteMeWhenDone.hdf"
                if self.execScrProc("Creating interim projections volume."
                                    , f"  cp '{projFile}' '{interimFile}' " ) :
                    return onStopMe(f"Failed to create interim projections volume in {outPath}.")
                projFile = interimFile
        delMe = projFile

        if self.ui.ringOrder.checkedButton() is self.ui.ringBeforePhase :
            if self.applyRing(f"{projFile}:/data:y", saveHist=True) or self.applyPhase(f"{projFile}:/data", True):
                return onStopMe()
        else:
            if self.applyPhase(f"{projFile}:/data", True) or self.applyRing(f"{projFile}:/data:y", saveHist=True):
                return onStopMe()

        outPath = ""
        if self.ui.recInMem.isChecked():
            x, y, z = hdf5shape(projFile, "data")
            if not (x and y and z):
                return onStopMe(f"Failed to read sizes of projecion file {projFile}")
            outTest = self.inMemNamePrexix() + "prerec.tif"
            outFile = self.inMemNamePrexix() + "rec.hdf"
            outPath = outFile + ":/data"
            self.addToConsole(f"Reconstructing into memory: {outPath}.")
            if self.execScrProc("Creating file for reconstructed volume.",
                    f"convert -size {x}x{x} -colorspace gray canvas:black {outTest} && \n"
                    f"ctas v2v {outTest} -o {outPath}:-{y - 1} && \n"
                    f"if (( {4*x*x*y} >  $( du --block-size=1 {outFile} | cut -d$'\t' -f1 ) )) ; then \n"
                    f"  cp --sparse=never {outFile} {outFile}.tmp  && \n"
                    f"  mv {outFile}.tmp {outFile}\n"
                     "fi\n"
                    f"rm -f {outTest}\n" ) :
                return onStopMe(f"Failed to create reconstructed volume in {outPath}."
                                 "Probably not enough memory. Try to reconstruct directly into storage.")
        elif self.ui.resTIFF.isChecked():
            odir = "rec8int" if self.ui.resToInt.isChecked() else "rec"
            Script.run(f"mkdir -p {path.join(wdir,odir)} ")
            outPath = path.join(odir,"rec_@.tif")
        else:
            outPath = "rec.hdf:/data"
        if self.applyCT(step, f"{projFile}:/data:y", outPath, True):
            return onStopMe()

        if self.ui.resHDF.isChecked() and self.ui.resToInt.isChecked() :
            Script.run(f"mkdir -p {path.join(wdir,'rec8int')} ")
            self.execScrProc( "Converting to integer",
                             f"ctas v2v {outPath} -v -o rec8int/rec_@.tif "
                             f" -m {self.ui.toIntMin.value()} -M {self.ui.toIntMax.value()}" )
        if self.ui.recInMem.isChecked() and not self.ui.recInMemOnly.isChecked():
            resPath = path.join(path.realpath(wdir),'rec.hdf')
            self.execScrProc(f"Copying reconstruction to the storage into {resPath}",
                             f"cp -f {self.inMemNamePrexix()}rec.hdf {resPath}")

        self.execScrRole("finish")
        if self.scrProc.dryRun:
            delMe = None
            self.addErrToConsole("Dry run. No reconstruction performed.")
        return onStopMe()


    @pyqtSlot()
    def update_termini_state(self):
        isrunning = False
        for script in self.ui.findChildren(Script):
            isrunning = isrunning or script.isRunning()
        self.ui.termini.setVisible(isrunning)
        self.ui.termini.setStyleSheet(warnStyle if isrunning else "")


    @pyqtSlot()
    def on_termini_clicked(self):
        for script in self.ui.findChildren(Script):
            script.stop()



signal.signal(signal.SIGINT, signal.SIG_DFL) # Ctrl+C to quit
app = QApplication(sys.argv)
my_mainWindow = MainWindow()
exitSts=app.exec_()
toRm = ""
for rmfn in set(listOfCreatedMemFiles):
    toRm += f" {rmfn}*"
if toRm:
    Script.run(f"rm -f {toRm} &")
sys.exit(exitSts)
