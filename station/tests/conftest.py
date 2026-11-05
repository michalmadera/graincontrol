import os

# Zdjęcia w testach zawsze z atrapy silnika z acquisition/, także gdyby rpicam był zainstalowany.
os.environ["GRAINCONTROL_DUMMY"] = "1"
