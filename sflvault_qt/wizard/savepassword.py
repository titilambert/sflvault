#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
#    sflvault_qt/wizard/savepassword.py
#
#    This file is part of SFLvault-QT
#
#    Copyright (C) 2009 Thibault Cohen
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import sys
from PyQt4 import QtCore, QtGui
import re
from PyQt4.QtCore import Qt
import sflvault
from sflvault.client import SFLvaultClient
from lib.auth import *
import shutil
import os

# Set page IDs
PAGE_INTRO = 0
PAGE_PASSWORD = 1
PAGE_SUCCESS = 2
PAGE_UNSUCCESS = 3

class SavePasswordWizard(QtGui.QWizard):
    def __init__(self, password=None, wallet_id=None, parent=None):
        """ Wizard to save password in wallet
        """
        QtGui.QWizard.__init__(self, parent)
        self.parent = parent
        self.password = password
        self.wallet_id = wallet_id

        self.setModal(True)
        self.setPage(PAGE_INTRO, Page1(self))
        self.setPage(PAGE_PASSWORD, Page2(self))
        self.setPage(PAGE_SUCCESS, Page3(self))
        self.setPage(PAGE_UNSUCCESS, Page4(self))

        self.setWindowTitle(self.tr("Save your password"))
        self.show()


class Page1(QtGui.QWizardPage):
    def __init__(self, parent=None):
        """ Intro page
        """
        QtGui.QWizard.__init__(self, parent)
        self.parent = parent
        self.settings = self.parent.parent.settings

        self.setTitle("Save your password in your wallet")

        label = QtGui.QLabel()
        label.setWordWrap(True)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(label)
        self.setLayout(layout)

        # Check if system has a supported wallet
        wallet_setting = str(self.settings.value("SFLvault-qt4/wallet").toString())
        if wallet_setting:
            label.setText("This wizard will save your vault password in you keyring system."
                        )
            self.next_page = PAGE_PASSWORD
        else:
            label.setText("Your system doesn't have a supported keyring system."
                        )
            self.next_page = PAGE_UNSUCCESS

    def nextId(self):
        return self.next_page


class Page2(QtGui.QWizardPage):
    def __init__(self, parent=None):
        """ Form page
        """
        QtGui.QWizardPage.__init__(self, parent)
        self.parent = parent
        self.setTitle(self.tr("Save your vault password"))
        self.setSubTitle(self.tr("Fill this form"))
        self.setCommitPage(True)
        self.next_page = PAGE_SUCCESS
        self.settings = self.parent.parent.settings

        if self.parent.wallet_id is None:
            wallet_label = QtGui.QLabel(self.tr("Choose your wallet"))
            self.wallet = QtGui.QComboBox()

        password1_label = QtGui.QLabel(self.tr("&Password"))
        self.password1 = QtGui.QLineEdit(self.parent.password)
        self.password1.setEchoMode(QtGui.QLineEdit.Password)
        password1_label.setBuddy(self.password1)

        password2_label = QtGui.QLabel(self.tr("Confirm your password"))
        self.password2 = QtGui.QLineEdit(self.parent.password)
        self.password2.setEchoMode(QtGui.QLineEdit.Password)
        password2_label.setBuddy(self.password2)

        layout = QtGui.QGridLayout(self)
        if self.parent.wallet_id is None:
            layout.addWidget(wallet_label, 0, 0)
            layout.addWidget(self.wallet, 0, 1)
        layout.addWidget(password1_label, 1, 0)
        layout.addWidget(self.password1, 1, 1)
        layout.addWidget(password2_label, 2, 0)
        layout.addWidget(self.password2, 2, 1)

        self.setLayout(layout)
        self.registerField("password1", self.password1)
        self.registerField("password2", self.password2)
        if self.parent.wallet_id is None:
            self.registerField("wallet", self.wallet)
            self.fillWallet()

    def validatePage(self):
        """ Check form and define next page
        """
        # Check if password match
        if self.password2.text().compare(self.password1.text()):
            error = QtGui.QMessageBox(QtGui.QMessageBox.Critical, "Password error", "Passwords don't match")
            error.exec_()
            return False
        # Empty password
        if not self.password2.text().compare(""):
            error = QtGui.QMessageBox(QtGui.QMessageBox.Critical, "Empty password", "Password can't be empty")
            error.exec_()
            return False
        # Check which wallet is used (kwallet or seahorse)
        if self.parent.wallet_id is None:
            wallet_id = self.wallet.currentIndex() + 1
        else:
            wallet_id = self.parent.wallet_id
        ret = setSecret(str(wallet_id), unicode(self.password1.text()))
        if ret:
            self.next_page = PAGE_SUCCESS
        else:
            self.next_page = PAGE_UNSUCCESS
        return True

    def nextId(self):
        return self.next_page

    def fillWallet(self):
        self.wallet.clear()
        client = SFLvaultClient(str(self.settings.fileName()))
        backend_list = client.cfg.wallet_list()
        for i,backend in enumerate(backend_list[1:]):
            # recommend
            if backend[3] == "Recommended":
                self.wallet.addItem("* - " + backend[1], QtCore.QVariant(backend[1]))
            # just supported
            elif backend[3] == "Supported":
                self.wallet.addItem(backend[1], QtCore.QVariant(backend[1]))
            # Set current wallet
            if backend[4] == True:
                self.wallet.setCurrentIndex(i - 1)


class Page3(QtGui.QWizardPage):
    def __init__(self, parent=None):
        """ Success page """
        QtGui.QWizardPage.__init__(self, parent)
        self.parent = parent

        self.setTitle("Password saved successfully")

        label = QtGui.QLabel("Your password was saved in your wallet."
                            )
        label.setWordWrap(True)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(label)
        self.setFinalPage(True)
        self.setLayout(layout)

    def nextId(self):
        return -1


class Page4(QtGui.QWizardPage):
    def __init__(self, parent=None):
        """ Unsuccess page
        """
        QtGui.QWizardPage.__init__(self, parent)
        self.parent = parent

        self.setTitle("Password saved unsuccessfully")

        label = QtGui.QLabel("Your password was NOT saved in your wallet."
                            )
        label.setWordWrap(True)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(label)
        self.setFinalPage(True)
        self.setLayout(layout)

    def nextId(self):
        return -1
