from __future__ import annotations

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat


def _fmt(r: int, g: int, b: int, bold: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(r, g, b))
    if bold:
        from PyQt6.QtGui import QFont
        fmt.setFontWeight(QFont.Weight.Bold)
    return fmt


_RULES: list[tuple[QRegularExpression, QTextCharFormat]] = [
    (QRegularExpression(r"^\+\+\+.*"),   _fmt(166, 227, 161)),   # +++ header — green
    (QRegularExpression(r"^---.*"),       _fmt(243, 139, 168)),   # --- header — red
    (QRegularExpression(r"^\+[^+].*"),   _fmt(166, 227, 161)),   # added line
    (QRegularExpression(r"^\+$"),         _fmt(166, 227, 161)),   # bare +
    (QRegularExpression(r"^-[^-].*"),    _fmt(243, 139, 168)),   # removed line
    (QRegularExpression(r"^-$"),          _fmt(243, 139, 168)),   # bare -
    (QRegularExpression(r"^@@.*@@"),      _fmt(137, 180, 250, bold=True)),  # hunk header — blue
    (QRegularExpression(r"^(diff|index|new file|deleted file).*"), _fmt(108, 112, 134)),  # meta — gray
]


class DiffHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in _RULES:
            match = pattern.match(text)
            if match.hasMatch():
                self.setFormat(0, len(text), fmt)
                return
