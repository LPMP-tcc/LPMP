import PySide6.QtCore as Qtc
import PySide6.QtWidgets as Qtw


class ArtArea(Qtw.QLabel):
    def __init__(self, show_add=True, parent=None):
        super().__init__(parent)
        self._show_add = show_add
        self.setFixedWidth(200)
        self.setFixedHeight(200)
        self.setScaledContents(True)

        self.add_button = Qtw.QPushButton("+", self)
        self.add_button.setFixedSize(28, 28)
        self.add_button.move(168, 4)
        self.add_button.hide()

        self.play_button = Qtw.QPushButton("▶", self)
        self.play_button.setFixedSize(28, 28)
        self.play_button.move(168, 168)
        self.play_button.hide()

    def enterEvent(self, event):
        super().enterEvent(event)
        if self._show_add:
            self.add_button.show()
        self.play_button.show()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.add_button.hide()
        self.play_button.hide()


class ElidedLabel(Qtw.QLabel):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setText(text)
        self.setSizePolicy(Qtw.QSizePolicy.Policy.Ignored, Qtw.QSizePolicy.Policy.Preferred)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        elided = self.fontMetrics().elidedText(self._full_text, Qtc.Qt.TextElideMode.ElideRight, self.width())
        super().setText(elided)
