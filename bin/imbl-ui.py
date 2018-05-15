#!/usr/bin/env python3

import sys
import os

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import pyqtSlot, QSettings
from PyQt5.QtWidgets import QFileDialog
from PyQt5.uic import loadUi

sys.path.append("..")
from share import ui_imbl


warnStyle = 'background-color: rgba(255, 0, 0, 128);'


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()
        # self.ui = loadUi('../share/imbl-ui.ui', self)
        self.ui = ui_imbl.Ui_MainWindow()
        self.ui.setupUi(self)

        self.on_outPath_textChanged()

        self.scanRange = 0
        self.doSerial = self.do2D = False

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
                'ls ' + ipath + '/acquisition.*config.* | sort -V | tail -n 1'
                ).read()
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

        scanrange = 0
        pjs = 0
        zs = 0
        ys = 0
        fshift = 0
        width = 0
        hight = 0
        execfile(initiatedFile)  # above variables are from initiatedFile

        for tabIdx in range(1, self.ui.tabWidget.count()-1):
            self.ui.tabWidget.setTabEnabled(tabIdx, False)

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

        if self.ui.initiate.styleSheet() == warnStyle:
            # stop initiate
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
                   + " -e " if self.ui.noFF.isChecked() else ""
                   + self.ui.inPath.text())
        os.system(command)

        self.ui.initInfo.setEnabled(True)
        self.ui.initiate.setStyleSheet('')
        self.ui.initiate.setText('Initiate')

        self.on_outPath_textChanged()


app = QtWidgets.QApplication(sys.argv)
my_mainWindow = MainWindow()
my_mainWindow.show()
sys.exit(app.exec_())
