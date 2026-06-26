import sys

import PySide6.QtCore as Qtc
import PySide6.QtWidgets as Qtw

class Application:
    music_player = None
    library = None
    qt_app = None
    main_window = None

    def __init__(self):
        self.qt_app = Qtw.QApplication(sys.argv)
        self.qt_app.styleHints().setColorScheme(Qtc.Qt.ColorScheme.Light)
        dummy = Qtw.QWidget() # needed because Qt is an inscrutable mess

        from model.music_player import MusicPlayer
        from model.library import Library
        from view.main_window import MainWindow

        self.music_player = MusicPlayer()
        self.library = Library()
        self.main_window = MainWindow(self.music_player, self.library)
        self.main_window.show()
        self.qt_app.exec()

Application()