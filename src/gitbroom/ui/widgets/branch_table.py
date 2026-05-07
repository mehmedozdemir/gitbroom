from __future__ import annotations

from PyQt6.QtCore import Qt, QSortFilterProxyModel, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from gitbroom.core.models import BranchInfo
from gitbroom.ui.models.branch_table_model import BranchTableModel


class BranchTable(QWidget):
    branch_selected = pyqtSignal(object)   # BranchInfo | None
    selection_changed = pyqtSignal(int)    # count of checked branches
    delete_requested = pyqtSignal(list)    # list[BranchInfo]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = BranchTableModel()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(Qt.ItemDataRole.DisplayRole)

        self._view = QTableView()
        self._view.setModel(self._proxy)
        self._view.setSortingEnabled(True)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setAlternatingRowColors(True)
        self._view.setShowGrid(True)
        self._view.verticalHeader().setVisible(False)
        self._view.horizontalHeader().setStretchLastSection(False)
        self._view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_context_menu)
        self._view.clicked.connect(self._on_cell_clicked)
        self._view.selectionModel().currentRowChanged.connect(self._on_row_changed)

        # Column widths
        self._view.setColumnWidth(0, 36)   # checkbox
        self._view.setColumnWidth(2, 140)  # author
        self._view.setColumnWidth(3, 110)  # date
        self._view.setColumnWidth(4, 130)  # merge
        self._view.setColumnWidth(5, 130)  # risk
        self._view.setColumnWidth(6, 110)  # location

        layout.addWidget(self._view)

    def set_branches(self, branches: list[BranchInfo]) -> None:
        self._model.set_branches(branches)

    def apply_filter(
        self,
        text: str = "",
        show_merged: bool | None = None,
        show_stale: bool | None = None,
        mine_email: str | None = None,
        local_only: bool = False,
        remote_only: bool = False,
    ) -> None:
        self._model.filter(
            text=text,
            show_merged=show_merged,
            show_stale=show_stale,
            mine_email=mine_email,
            local_only=local_only,
            remote_only=remote_only,
        )

    def checked_branches(self) -> list[BranchInfo]:
        return self._model.checked_branches()

    def check_all(self, checked: bool) -> None:
        self._model.check_all(checked)
        self.selection_changed.emit(len(self._model.checked_branches()))

    def _on_cell_clicked(self, proxy_index) -> None:
        if proxy_index.column() == 0:
            source_index = self._proxy.mapToSource(proxy_index)
            check_index = self._model.index(source_index.row(), 0)
            current = self._model.data(check_index, Qt.ItemDataRole.CheckStateRole)
            new_state = (
                Qt.CheckState.Unchecked.value
                if current == Qt.CheckState.Checked.value
                else Qt.CheckState.Checked.value
            )
            self._model.setData(check_index, new_state, Qt.ItemDataRole.CheckStateRole)
            self.selection_changed.emit(len(self._model.checked_branches()))

    def _on_row_changed(self, current, previous) -> None:
        if not current.isValid():
            self.branch_selected.emit(None)
            return
        source = self._proxy.mapToSource(current)
        branch = self._model.branch_at(source.row())
        self.branch_selected.emit(branch)

    def _on_context_menu(self, pos) -> None:
        proxy_index = self._view.indexAt(pos)
        if not proxy_index.isValid():
            return
        source = self._proxy.mapToSource(proxy_index)
        branch = self._model.branch_at(source.row())
        if not branch:
            return

        menu = QMenu(self)
        action_detail = menu.addAction("Detaylar")
        menu.addSeparator()
        action_delete = menu.addAction("Sil")
        menu.addAction("Backup Tag Oluştur")

        action = menu.exec(self._view.viewport().mapToGlobal(pos))
        if action == action_detail:
            self.branch_selected.emit(branch)
        elif action == action_delete:
            self.delete_requested.emit([branch])
