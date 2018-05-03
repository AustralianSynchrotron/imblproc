#!/usr/bin/env python3

import sys
import os
import glob

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QFileDialog
from PyQt5.uic import loadUi

sys.path.append("..")
from share import ui_imbl


warnStyle = 'background-color: rgba(255, 0, 0, 128);'


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()
        # self.ui = loadUi('../share/imbl-ui.ui')
        self.ui = ui_imbl.Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.initiate.clicked.connect(self.initiateExp)
        self.ui.inBrowse.clicked.connect(self.browseExp)
        self.ui.inPath.textChanged.connect(self.updateExp)

        # self.ui.show()
        self.show()

    def initiateExp(self):
        self.ui.initiate.setText('bb')

    def browseExp(self):
        newdir = QFileDialog.getExistingDirectory(self, "Experiment directory",
                                                  os.getcwd())
        if newdir:
            self.ui.inPath.setText(newdir)

    def updateExp(self, text):
        dirok = os.path.isdir(text)
        if dirok:
            os.chdir(text)
            self.ui.inPath.setStyleSheet('')
        else:
            self.ui.inPath.setStyleSheet(warnStyle)


app = QtWidgets.QApplication(sys.argv)
my_mainWindow = MainWindow()
sys.exit(app.exec_())
