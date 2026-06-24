import threading, time

import PySide6.QtCore as Qtc
import PySide6.QtWidgets as Qtw

class TopBar(Qtw.QWidget):
    def __init__(self, music_player, library, parent_widget):
        super().__init__()
        self.setMaximumHeight(200)
        self.parent_widget = parent_widget

        self.h_layout = Qtw.QHBoxLayout()
        self.setLayout(self.h_layout)
        self.buttons_h_layout = Qtw.QHBoxLayout()
        self.back_button = Qtw.QPushButton("<<")
        self.play_button = Qtw.QPushButton("\u25B6")
        self.pause_button = Qtw.QPushButton("\u25AE\u200A\u25AE")
        self.next_button = Qtw.QPushButton(">>")

        self.back_button.setToolTip("Backtrack")
        self.play_button.setToolTip("Play")
        self.pause_button.setToolTip("Pause")
        self.next_button.setToolTip("Next Track")

        self.dummy_mid_display = Qtw.QFrame()
        self.song_title_text = Qtw.QLabel("")
        self.seek_bar = Qtw.QSlider()
        self.dummy_mid_display_v_layout = Qtw.QVBoxLayout()

        self.volume_slider = Qtw.QSlider()

        self.music_player = None
        self.library = None
        self.is_shutting_down = False

        self.back_button.clicked.connect(self._on_back_button_clicked)
        self.play_button.clicked.connect(self._on_play_button_clicked)
        self.pause_button.clicked.connect(self._on_pause_button_clicked)
        self.next_button.clicked.connect(self._on_next_button_clicked)

        self.buttons_h_layout.addWidget(self.back_button)
        self.buttons_h_layout.addWidget(self.play_button)
        self.buttons_h_layout.addWidget(self.pause_button)
        self.buttons_h_layout.addWidget(self.next_button)

        self.dummy_mid_display.setFrameStyle(Qtw.QFrame.Shape.Panel | Qtw.QFrame.Shadow.Sunken)
        self.song_title_text.setAlignment(Qtc.Qt.AlignmentFlag.AlignCenter)
        self.seek_bar.setOrientation(Qtc.Qt.Orientation.Horizontal)
        self.seek_bar.setRange(0,1000)
        self.dummy_mid_display_v_layout.addWidget(self.song_title_text)
        self.dummy_mid_display_v_layout.addWidget(self.seek_bar)
        self.dummy_mid_display.setLayout(self.dummy_mid_display_v_layout)

        self.volume_slider.setOrientation(Qtc.Qt.Orientation.Horizontal)
        self.volume_slider.setMaximumWidth(200)
        self.volume_slider.setRange(0,100)
        self.volume_slider.setValue(100)

        # where to put this?
        self.temp_right_v_layout = Qtw.QVBoxLayout()
        self.add_button = Qtw.QPushButton()
        self.add_button.setIcon(self.style().standardIcon(Qtw.QStyle.StandardPixmap.SP_DirOpenIcon))
        self.add_button.setIconSize(Qtc.QSize(28, 28))
        self.add_button.setFixedSize(40, 40)
        self.add_button.clicked.connect(self._add_local)
        self.add_button.setToolTip("Add local files")
        self.temp_right_v_layout.addWidget(self.add_button)

        self.h_layout.addLayout(self.buttons_h_layout)
        self.h_layout.addWidget(self.dummy_mid_display)
        self.h_layout.addWidget(self.volume_slider)
        self.h_layout.addLayout(self.temp_right_v_layout)

        self.music_player = music_player
        self.library = library
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

        seek_bar_thread = threading.Thread(target=self._update_seek_bar, daemon=True)
        seek_bar_thread.start()

    def set_is_shutting_down(self, boolean):
        self.is_shutting_down = boolean

    def set_now_playing(self, title, artist):
        if title or artist:
            self.song_title_text.setText(f"{title} - {artist}")
        else:
            self.song_title_text.setText("")

    def _on_volume_changed(self, value):
        self.music_player.set_volume(value)

    def _on_back_button_clicked(self):
        self.music_player.skip_backward()

    def _on_play_button_clicked(self):
        self.music_player.resume_all()

    def _on_pause_button_clicked(self):
        self.music_player.pause_all()

    def _on_next_button_clicked(self):
        self.music_player.skip_forward()

    def _update_seek_bar(self):
        while not self.is_shutting_down:
            curr_slider_position = self.seek_bar.value()

            if self.seek_bar.isSliderDown():
                self.music_player.seek_to_position(curr_slider_position)
            else:
                new_position = self.music_player.get_new_slider_position(curr_slider_position)
                self.seek_bar.setValue(new_position)

            if self.music_player.is_playing:
                self.music_player.check_if_ended()

            now_playing = self.music_player.now_playing
            self.set_now_playing(
                now_playing.get("title", "") if now_playing else "",
                now_playing.get("artist", "") if now_playing else "",
            )

            time.sleep(0.1)

    def _add_local(self):
        file_dialog = Qtw.QFileDialog()
        file_dialog.setFileMode(Qtw.QFileDialog.FileMode.ExistingFiles)
        selected_files = file_dialog.getOpenFileNames()[0]
        if selected_files:
            self.library.preprocess_files(selected_files)

