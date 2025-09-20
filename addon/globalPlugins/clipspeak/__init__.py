# -*- coding: utf-8 -*-
# Clipspeak
# An addon to monitor and speak messages relating to clipboard operations
# By: Damien Lindley Created: 19th April 2017
# Modified by Rui Fontes, Ângelo Miguel and Abel Júnior in 26/03/2022
# Modified by Rui Fontes and Ângelo Abrantes in 01/01/2024
# Copyright (C) 2022-2024 Rui Fontes <rui.fontes@tiflotecnia.com>
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

# Import the necessary modules
import globalPluginHandler
import globalVars
import wx
import gui
from gui.settingsDialogs import NVDASettingsDialog, SettingsPanel
from gui import guiHelper
import ui
import config
import api
import inputCore
from keyboardHandler import KeyboardInputGesture
import scriptHandler
from scriptHandler import script
import comtypes.client
import ctypes
import controlTypes
# For compatibility with old NVDA versions
if hasattr(controlTypes, "Role"):
	for r in controlTypes.Role: setattr(controlTypes, r.__str__().replace("Role.", "ROLE_"), r)
else:
	setattr(controlTypes, "Role", type('Enum', (), dict([(x.split("ROLE_")[1], getattr(controlTypes, x)) for x in dir(controlTypes) if x.startswith("ROLE_")])))
if hasattr(controlTypes, "State"):
	for r in controlTypes.State: setattr(controlTypes, r.__str__().replace("State.", "STATE_"), r)
else:
	setattr(controlTypes, "State", type('Enum', (), dict([(x.split("STATE_")[1], getattr(controlTypes, x)) for x in dir(controlTypes) if x.startswith("STATE_")])))

from time import sleep
from . import clipboardMonitor
import addonHandler
addonHandler.initTranslation()

# Constants:

def getAddon():
	return addonHandler.getCodeAddon()

Addon = getAddon()
def initConfiguration():
	confspec = {
		"announce": "boolean(default=True)",
	}
	config.conf.spec[Addon.name] = confspec

initConfiguration()

# Global variables
# Clipboard content: What are we working with?
cc_none=0
cc_text=1
cc_read_only_text=2
cc_file=3
cc_list=4
cc_other=5
cc_file1=6

# Clipboard mode: What are we doing?
cm_none=0
cm_cut=1
cm_copy=2
cm_paste=3
cm_copyAsPath=4

# Not strictly clipboard, but...
cm_undo=5
cm_redo=6

cc_last_flag = ""
cc_last_flag_1 = ""

if globalVars.appArgs.secure:
	# Override the global plugin to disable it.
	GlobalPlugin = globalPluginHandler.GlobalPlugin


class GlobalPlugin(globalPluginHandler.GlobalPlugin):	
	# Creating the constructor of the newly created GlobalPlugin class.
	def __init__(self):
		# Call of the constructor of the parent class.
		super(globalPluginHandler.GlobalPlugin, self).__init__()

		# Adding a NVDA configurations section
		gui.NVDASettingsDialog.categoryClasses.append(ClipSpeakSettingsPanel)

		# Creating an instance
		self.dataInstance = clipboardMonitor.clipboardMonitor()

	def terminate(self):
		super(GlobalPlugin, self).terminate()
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(ClipSpeakSettingsPanel)

	# Script functions:
	@script( 
		# Translators: Message to be announced during Keyboard Help 
		description=_("Cut selected item to clipboard, if appropriate."), 
		# Translators: Name of the section in "Input gestures" dialog. 
		category=_("Clipboard"), 
		gesture="kb:Control+X"
	)
	def script_cut(self, gesture):
		# Script activated: Cut.
		# Processing input gesture.
		if self.process_input(gesture):
			return
		sleep(0.06)
		# Speaking message.
		self.speak_appropriate_message(cm_cut)

	@script( 
		# Translators: Message to be announced during Keyboard Help 
		description=_("Copy selected item to clipboard, if appropriate."), 
		# Translators: Name of the section in "Input gestures" dialog. 
		category=_("Clipboard"), 
		gesture="kb:Control+C"
	)
	def script_copy(self, gesture):
		# Script activated: Copy.
		# Processing input gesture.
		if self.process_input(gesture):
			return
		sleep(0.06)
		# Speaking message.
		self.speak_appropriate_message(cm_copy)

	@script( 
		# Translators: Message to be announced during Keyboard Help 
		description=_("Copy path of selected file to clipboard, if appropriate."), 
		# Translators: Name of the section in "Input gestures" dialog. 
		category=_("Clipboard"), 
		gesture="kb:Control+Shift+C"
	)
	def script_copyAsPath(self, gesture):
		# Script activated: Copy as path
		focus=api.getFocusObject()
		if focus.windowClassName == "DirectUIHWND" or "SysListView32":
			# Processing input gesture.
			if self.process_input(gesture):
				return
			sleep(0.06)
			# Speaking message.
			self.speak_appropriate_message(cm_copyAsPath)
		else:
			pass

	@script( 
		# Translators: Message to be announced during Keyboard Help 
		description=_("Paste item from clipboard, if appropriate."), 
		# Translators: Name of the section in "Input gestures" dialog. 
		category=_("Clipboard"), 
		gesture="kb:Control+V"
	)
	def script_paste(self, gesture):
		# Script activated: Paste.
		# Processing input gesture.
		if self.process_input(gesture):
			return
		sleep(0.06)
		# Speaking message.
		self.speak_appropriate_message(cm_paste)

	@script( 
		# Translators: Message to be announced during Keyboard Help 
		description=_("Undo operation."),
		# Translators: Name of the section in "Input gestures" dialog. 
		category=_("Clipboard"), 
		gesture="kb:Control+Z"
	)
	def script_undo(self, gesture):
		# Script activated: Undo.
		# Processing input gesture.
		if self.process_input(gesture):
			return
		# Speaking message.
		self.speak_appropriate_message(cm_undo)

	@script( 
		# Translators: Message to be announced during Keyboard Help 
		description=_("Redo operation."),
		# Translators: Name of the section in "Input gestures" dialog.
		category=_("Clipboard"), 
		gesture="kb:Control+Y"
	)
	def script_redo(self, gesture):
		# Script activated: Redo.
		# Processing input gesture.
		if self.process_input(gesture):
			return
		# Speaking message.
		self.speak_appropriate_message(cm_redo)

	# Functions: Examines our environment so we can speak the appropriate message.
	def process_input(self, gesture):
		# Evaluating possible gestures.
		scripts=[]
		maps=[inputCore.manager.userGestureMap, inputCore.manager.localeGestureMap]
		# Found gesture mapping
		# Enumerating scripts for these maps.
		for map in maps:
			# Enumerating gestures for maps
			for identifier in gesture.identifiers:
				# Enumerating scripts for gesture
				scripts.extend(map.getScriptsForGesture(identifier))

		# Found scripts
		focus=api.getFocusObject()
		tree=focus.treeInterceptor
		# Checking tree interceptor state.
		if tree and tree.isReady:
			# Tree interceptor in use. Retrieving scripts for the interceptor.
			func=scriptHandler._getObjScript(tree, gesture, scripts)
			# Examining object
			# Examining function attributes.
			if func and (not tree.passThrough or getattr(func,"ignoreTreeInterceptorPassThrough",False)):
				# This gesture is already handled elsewhere.
				# Executing associated function.
				if api.getFocusObject().appModule.appName == "outlook":
					api.getFocusObject().WinwordSelectionObject.Copy()
					return False
				else:
					func(tree)
				return True
		else: 
			# Tree interceptor not in use. Checking the NVDA object.
			func = scriptHandler._getObjScript(focus, gesture, scripts) 
			if func: 
				# This gesture is already handled elsewhere.
				# Executing associated function.
				if api.getFocusObject().appModule.appName == "winword":
					api.getFocusObject().WinwordSelectionObject.Paste()
				elif api.getFocusObject().appModule.appName == "outlook":
					api.getFocusObject().WinwordSelectionObject.Paste()
				else:
					func(focus) 
				return False
		# Nothing associated here. Pass straight to the system.
		gesture.send()
		return False

	def examine_focus(self):
		global cc_last_flag, cc_last_flag_1
		cc_last_flag_1 = cc_last_flag
		focus = api.getFocusObject()
		if not focus:
			cc_last_flag = cc_none
			return cc_none
		# Examining focus object
		# Retrieve the control's states and roles.
		states=focus.states

		# Check for an explorer/file browser window.
		if focus.windowClassName == "DirectUIHWND":
			if  controlTypes.STATE_SELECTED in states:
				cc_last_flag = cc_file
				return cc_file
			elif  controlTypes.STATE_SELECTABLE in states:
				cc_last_flag = cc_file1
				return cc_file1
		if focus.windowClassName == "SysListView32":
			if  controlTypes.STATE_SELECTED in states:
				cc_last_flag = cc_file
				return cc_file
			elif  controlTypes.STATE_SELECTABLE in states:
				cc_last_flag = cc_file1
				return cc_file1

		# Check for a list item.
		elif focus.role == (controlTypes.ROLE_LISTITEM or controlTypes.ROLE_TABLEROW) and controlTypes.STATE_SELECTED in states:
			cc_last_flag = cc_list
			return cc_list

		# Check if we're looking at text.
		elif controlTypes.STATE_MULTILINE in states:
			if controlTypes.STATE_READONLY in states:
				cc_last_flag = cc_read_only_text
				return cc_read_only_text
			else:
				# Otherwise, we're just an ordinary text field.
				# Field seems to be editable.
				cc_last_flag = cc_text
				return cc_text

		elif controlTypes.STATE_EDITABLE in states:
			if controlTypes.STATE_READONLY in states:
				cc_last_flag = cc_read_only_text
				return cc_read_only_text
			else:
				# Otherwise, we're just an ordinary text field.
				# Field seems to be editable.
				cc_last_flag = cc_text
				return cc_text

		elif focus.role == controlTypes.ROLE_EDITABLETEXT:
		# For some reason, not all controls have an editable state, even when they clearly are.
			if controlTypes.STATE_READONLY in states:
				cc_last_flag = cc_read_only_text
				return cc_read_only_text
			else:
				# Otherwise, we're just an ordinary text field.
				# Field seems to be editable.")
				cc_last_flag = cc_text
				return cc_text
		elif focus.windowClassName == "RichEditD2DPT" or "Scintilla":
			cc_last_flag = cc_text
			return cc_text
		elif focus.windowClassName == "_WwG":
			if api.getFocusObject().appModule.appName == "winword" or "outlook":
				cc_last_flag = cc_none
				return cc_none
			else:
				cc_last_flag = cc_text
				return cc_text
		# Todo: Other control types we need to check?
		else:
			# Control type would not suggest clipboard operations.
			cc_last_flag = cc_none
			return cc_none

	# Validation functions: In case we need to extend the script to allow more control/window types etc.
	# Todo: Can we check a control to see if it enables these operations? For instance whether a list enables copy or a text field allows select all?
	def can_undo(self, cc_flag):
		if cc_flag==cc_read_only_text:
			return False
		return True

	def can_redo(self, cc_flag):
		if cc_flag==cc_read_only_text:
			return False
		return True

	def can_cut(self, cc_flag):
		changed = self.dataInstance.clipboardHasChanged()
		return changed

	def can_copy(self, cc_flag):
		changed = self.dataInstance.clipboardHasChanged()
		return changed

	def can_copyAsPath(self, cc_flag):
		changed = self.dataInstance.clipboardHasChanged()
		return changed

	def can_paste(self, cc_flag):
		global cc_last_flag, cc_last_flag_1
		focus=api.getFocusObject()
		states=focus.states
		if cc_last_flag_1 == cc_none:
			cc_flag = cc_none
			return False
		elif cc_last_flag_1 == cc_text or cc_read_only_text:
			cc_flag = cc_text
			# Check if we're looking at text.
			if (controlTypes.STATE_EDITABLE or controlTypes.STATE_MULTILINE) in states:
				if controlTypes.STATE_READONLY in states:
					return False
				else:
					# Otherwise, we're just an ordinary text field.
					# Field seems to be editable.")
					return True
			# For some reason, not all controls have an editable state, even when 		they clearly are.
			elif focus.role == controlTypes.ROLE_EDITABLETEXT:
				if controlTypes.STATE_READONLY in states:
					return False
				else:
					return True
			elif controlTypes.STATE_READONLY in states:
				return False
			elif focus.windowClassName == "RichEditD2DPT" or "Scintilla":
				return True
			elif focus.windowClassName == "_WwG":
				return True

		elif cc_last_flag_1 == cc_file:
			cc_flag = cc_file
			# Check for an explorer/file browser window.
			# Todo: Is this an accurate method?
			if (focus.windowClassName == "DirectUIHWND" or "SysListView32") and focus.appModule.appName == "explorer":
				if  (focus.role==controlTypes.ROLE_LISTITEM) and controlTypes.STATE_SELECTABLE in states:
					return True
				return False
			return False

		elif cc_last_flag_1 == cc_file1:
			cc_flag = cc_file
			# Check for an explorer/file browser window.
			# Todo: Is this an accurate method?
			if (focus.windowClassName == "DirectUIHWND" or "SysListView32") and focus.appModule.appName == "explorer":
				if  (focus.role==controlTypes.ROLE_LISTITEM) and controlTypes.STATE_SELECTABLE in states:
					return True
				return False
			return False

		elif cc_last_flag_1 == cc_list:
			# Check for a list item.
			if (focus.role == controlTypes.ROLE_LISTITEM or controlTypes.ROLE_TABLEROW) and controlTypes.STATE_SELECTED in states:
				cc_flag = cc_list
				return False

	def speak_appropriate_message(self, cm_flag):
		cc_flag = self.examine_focus()
		if cc_flag==cc_none:
			return
		elif cc_flag==cc_list:
			# Translators: A single word representing an item in a list.
			word=_("item")

		# Validate and speak.
		if cm_flag==cm_undo and self.can_undo(cc_flag):
			# Translators: Message to speak when undoing.
			ui.message(_("Undo"))

		elif cm_flag==cm_redo and self.can_redo(cc_flag):
			# Translators: A message spoken when redoing a previously undone operation.
			ui.message(_("Redo"))

		elif cm_flag==cm_cut and self.can_cut(cc_flag):
			focus = api.getFocusObject()
			states=focus.states
			if  controlTypes.STATE_READONLY in states:
				return
			# Choose the appropriate message.
			type, word = self.dataInstance.validClipboardData()
			if config.conf[Addon.name]["announce"]:
				word = ""
			if cc_flag == cc_text:
				# Translators: A message to speak when cutting text to the clipboard.
				ui.message(_("Cut %s")%word)
			elif cc_flag == cc_file:
				# Translators: A message to speak when cutting files/folders to the clipboard.
				ui.message(_("Cut %s")%word)
			elif cc_flag == cc_file1:
				pass

		elif cm_flag==cm_copy and self.can_copy(cc_flag):
			# Choose the appropriate message.
			type, word = self.dataInstance.validClipboardData()
			if config.conf[Addon.name]["announce"]:
				word = ""
			if cc_flag == cc_text:
				if type == 2:
					# Translators: A message spoken when copying text to the clipboard.
					ui.message(_("Copy %s")%word)
				else:
					pass
			if cc_flag == cc_read_only_text:
				# Choose the appropriate message.
				type, word = self.dataInstance.validClipboardData()
				if config.conf[Addon.name]["announce"]:
					word = ""
				if type == 2:
					# Translators: A message spoken when copying text to the clipboard.
					ui.message(_("Copy %s")%word)
				else:
					pass
			elif cc_flag == cc_file:
				if type == 1:
					# Translators: A message spoken when copying files/folders to the clipboard.
					ui.message(_("Copy %s")%word)
				else:
					pass
			elif cc_flag == cc_file1:
				pass

		elif cm_flag==cm_copyAsPath and self.can_copyAsPath(cc_flag):
			# Choose the appropriate message.
			type, word = self.dataInstance.validClipboardData()
			if config.conf[Addon.name]["announce"]:
				word = ""
			if cc_flag == cc_file:
				# Translators: A message spoken when copying the path of a file.
				ui.message(_("Copy %s")%word)
			else:
				pass

		elif cm_flag==cm_paste and self.can_paste(cc_flag):
			# Choose the appropriate message.
			type, word = self.dataInstance.validClipboardData()
			if config.conf[Addon.name]["announce"]:
				word = ""
			if cc_flag == cc_text:
				if type == 2:
					# Translators: A message spoken when pasting text from the clipboard.
					ui.message(_("Pasted %s")%word)
				else:
					pass

			if cc_flag == cc_file:
				if type == 1:
					# Translators: A message spoken when pasting text from the clipboard.
					ui.message(_("Pasted %s")%word)
				else:
					pass
			else:
				pass


class ClipSpeakSettingsPanel(gui.settingsDialogs.SettingsPanel):
	# Translators: Title of the ClipSpeak settings dialog in the NVDA settings.
	title = _("ClipSpeak")

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer = settingsSizer)

		# Translators: Checkbox name in the configuration dialog
		self.announceWnd = sHelper.addItem(wx.CheckBox(self, label=_("Announce only copy/cut/paste")))
		self.announceWnd.SetValue(config.conf[Addon.name]["announce"])

	def onSave (self):
		config.conf[Addon.name]["announce"] = self.announceWnd.GetValue()
