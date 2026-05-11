
import threading
import time
import random
try:
    import winsound
except Exception:
    winsound = None

class SoundFX:
    """
    Synthetic Sci-Fi Sound Engine using system beeps.
    Runs in threads to prevent UI blocking.
    """
    
    @staticmethod
    def _play_freqs(sequence):
        """Play a sequence of (freq, duration) tuples."""
        def run():
            for freq, dur in sequence:
                if winsound is None:
                    continue
                # Clamp frequency to valid range for winsound
                f = max(37, min(32767, int(freq)))
                if f > 0:
                    try:
                        winsound.Beep(f, int(dur))
                    except Exception:
                        pass
        threading.Thread(target=run, daemon=True).start()

    @staticmethod
    def play_startup():
        """Aggressive ascension sound"""
        SoundFX._play_freqs([
            (400, 100), (800, 50), (1200, 50), (2000, 200)
        ])

    @staticmethod
    def play_click():
        """High tech click"""
        SoundFX._play_freqs([(2500, 30)])

    @staticmethod
    def play_hover():
        """Subtle tick"""
        SoundFX._play_freqs([(4000, 10)])
        
    @staticmethod
    def play_minimize():
        """Power down chirp"""
        SoundFX._play_freqs([(1500, 50), (800, 100)])
        
    @staticmethod
    def play_close():
        """Termination signal"""
        SoundFX._play_freqs([(2000, 50), (500, 150)])

    @staticmethod
    def play_mic_on():
        """Sonar ping"""
        SoundFX._play_freqs([(800, 50), (0, 50), (1200, 150)])
        
    @staticmethod
    def play_mic_off():
        """Low thud"""
        SoundFX._play_freqs([(600, 100), (300, 100)])

    @staticmethod
    def play_action():
        """Quick confirmation chirp for button presses"""
        SoundFX._play_freqs([(1200, 30), (1800, 50)])
