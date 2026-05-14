from __future__ import annotations

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QStyle

_SP = QStyle.StandardPixmap

_MAP: dict[str, _SP] = {
    "folder":    _SP.SP_DirOpenIcon,
    "scan":      _SP.SP_BrowserReload,
    "settings":  _SP.SP_FileDialogDetailedView,
    "info":      _SP.SP_MessageBoxInformation,
    "check_all": _SP.SP_DialogApplyButton,
    "uncheck":   _SP.SP_DialogResetButton,
    "trash":     _SP.SP_TrashIcon,
    "cancel":    _SP.SP_DialogCancelButton,
    "close":     _SP.SP_DialogCloseButton,
    "add":       _SP.SP_FileDialogNewFolder,
    "remove":    _SP.SP_DialogDiscardButton,
    "test":      _SP.SP_CommandLink,
    "save":      _SP.SP_DialogSaveButton,
}


def icon(name: str) -> QIcon:
    style = QApplication.style()
    sp = _MAP.get(name)
    if style and sp is not None:
        return style.standardIcon(sp)
    return QIcon()
