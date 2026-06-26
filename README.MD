Run the install.sh script to install the dependencies.
You'll need to download the latest release of go-librespot and run it.
Librespot only works with Spotify premium accounts, and with the provided config file, uses Spotify's own authentication flow.
You'll also need to have a SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET for the Spotify WebAPI-based search to work at all.
You can set up those credentials at Spotify's dev portal by registering a development mode "app" there: https://developer.spotify.com/

Python-VLC uses libVLC, which in turn uses the system's package manager's decoder libraries.
This means that if you're on a Fedora-based installation, not only will the installer.sh script not work, 
you'll also need to have some non-free packages installed, or else M4A (AAC) playback will not work.
