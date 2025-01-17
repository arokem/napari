"""
Custom Qt widgets that serve as native objects that the public-facing elements
wrap.
"""
# set vispy to use same backend as qtpy
from qtpy import API_NAME
from vispy import app

app.use_app(API_NAME)
del app

from qtpy.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QLabel,
    QAction,
    QShortcut,
)
from qtpy.QtGui import QKeySequence

from ..util.theme import template


class Window:
    """Application window that contains the menu bar and viewer.

    Parameters
    ----------
    qt_viewer : QtViewer
        Contained viewer widget.

    Attributes
    ----------
    qt_viewer : QtViewer
        Contained viewer widget.
    """

    def __init__(self, qt_viewer, *, show=True):

        self.qt_viewer = qt_viewer

        self._qt_window = QMainWindow()
        self._qt_window.setUnifiedTitleAndToolBarOnMac(True)
        self._qt_center = QWidget()
        self._qt_window.setCentralWidget(self._qt_center)
        self._qt_window.setWindowTitle(self.qt_viewer.viewer.title)
        self._qt_center.setLayout(QHBoxLayout())
        self._status_bar = self._qt_window.statusBar()
        self._qt_window.closeEvent = self.closeEvent
        self.close = self._qt_window.close

        self._add_menubar()

        self._add_file_menu()
        self._add_view_menu()
        self._add_window_menu()

        self._status_bar.showMessage('Ready')
        self._help = QLabel('')
        self._status_bar.addPermanentWidget(self._help)

        self._qt_center.layout().addWidget(self.qt_viewer)
        self._qt_center.layout().setContentsMargins(4, 0, 4, 0)

        self._update_palette(qt_viewer.viewer.palette)

        self.qt_viewer.viewer.events.status.connect(self._status_changed)
        self.qt_viewer.viewer.events.help.connect(self._help_changed)
        self.qt_viewer.viewer.events.title.connect(self._title_changed)
        self.qt_viewer.viewer.events.palette.connect(
            lambda event: self._update_palette(event.palette)
        )

        if show:
            self.show()

    def _add_menubar(self):
        self.main_menu = self._qt_window.menuBar()
        # Menubar shortcuts are only active when the menubar is visible.
        # Therefore, we set a global shortcut not associated with the menubar
        # to toggle visibility, *but*, in order to not shadow the menubar
        # shortcut, we disable it, and only enable it when the menubar is
        # hidden. See this stackoverflow link for details:
        # https://stackoverflow.com/questions/50537642/how-to-keep-the-shortcuts-of-a-hidden-widget-in-pyqt5
        self._main_menu_shortcut = QShortcut(
            QKeySequence('Ctrl+M'), self._qt_window
        )
        self._main_menu_shortcut.activated.connect(
            self._toggle_menubar_visible
        )
        self._main_menu_shortcut.setEnabled(False)

    def _toggle_menubar_visible(self):
        """Toggle visibility of app menubar.

        This function also disables or enables a global keyboard shortcut to
        show the menubar, since menubar shortcuts are only available while the
        menubar is visible.
        """
        if self.main_menu.isVisible():
            self.main_menu.setVisible(False)
            self._main_menu_shortcut.setEnabled(True)
        else:
            self.main_menu.setVisible(True)
            self._main_menu_shortcut.setEnabled(False)

    def _add_file_menu(self):
        open_images = QAction('Open', self._qt_window)
        open_images.setShortcut('Ctrl+O')
        open_images.setStatusTip('Open image file(s)')
        open_images.triggered.connect(self.qt_viewer._open_images)
        self.file_menu = self.main_menu.addMenu('&File')
        self.file_menu.addAction(open_images)

    def _add_view_menu(self):
        toggle_visible = QAction('Toggle menubar visibility', self._qt_window)
        toggle_visible.setShortcut('Ctrl+M')
        toggle_visible.setStatusTip('Hide Menubar')
        toggle_visible.triggered.connect(self._toggle_menubar_visible)
        self.view_menu = self.main_menu.addMenu('&View')
        self.view_menu.addAction(toggle_visible)

    def _add_window_menu(self):
        exit_action = QAction("Close window", self._qt_window)
        exit_action.setShortcut("Ctrl+W")
        exit_action.setStatusTip('Close napari window')
        exit_action.triggered.connect(self._qt_window.close)
        self.window_menu = self.main_menu.addMenu('&Window')
        self.window_menu.addAction(exit_action)

    def resize(self, width, height):
        """Resize the window.

        Parameters
        ----------
        width : int
            Width in logical pixels.
        height : int
            Height in logical pixels.
        """
        self._qt_window.resize(width, height)

    def show(self):
        """Resize, show, and bring forward the window.
        """
        self._qt_window.resize(self._qt_window.layout().sizeHint())
        self._qt_window.show()
        self._qt_window.raise_()

    def _update_palette(self, palette):
        # set window styles which don't use the primary stylesheet
        # FIXME: this is a problem with the stylesheet not using properties
        self._status_bar.setStyleSheet(
            template(
                'QStatusBar { background: {{ background }}; '
                'color: {{ text }}; }',
                **palette,
            )
        )
        self._qt_center.setStyleSheet(
            template('QWidget { background: {{ background }}; }', **palette)
        )

    def _status_changed(self, event):
        """Update status bar.
        """
        self._status_bar.showMessage(event.text)

    def _title_changed(self, event):
        """Update window title.
        """
        self._qt_window.setWindowTitle(event.text)

    def _help_changed(self, event):
        """Update help message on status bar.
        """
        self._help.setText(event.text)

    def closeEvent(self, event):
        # Forward close event to the console to trigger proper shutdown
        self.qt_viewer.console.shutdown()
        event.accept()
