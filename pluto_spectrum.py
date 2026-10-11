"""AquaWave standalone live PlutoSDR spectrum analyzer and waterfall.

Install: pip install numpy matplotlib pyadi-iio
Run:     python pluto_spectrum.py
Close any other app using the PlutoSDR before starting.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import adi

CENTER_FREQ = 433.92e6  # Hz: set to your transmitter's actual frequency
SAMPLE_RATE = 2_000_000  # samples/s
FFT_SIZE = 2048
RX_GAIN = 40  # dB
WATERFALL_ROWS = 120
PLUTO_URI = "ip:192.168.2.1"

sdr = adi.Pluto(PLUTO_URI)
sdr.sample_rate = SAMPLE_RATE
sdr.rx_lo = int(CENTER_FREQ)
sdr.rx_rf_bandwidth = SAMPLE_RATE
sdr.rx_buffer_size = FFT_SIZE * 4
sdr.gain_control_mode_chan0 = "manual"
sdr.rx_hardwaregain_chan0 = RX_GAIN

freqs = (np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, d=1 / SAMPLE_RATE)) + CENTER_FREQ) / 1e6
window = np.hanning(FFT_SIZE)
waterfall = np.full((WATERFALL_ROWS, FFT_SIZE), -100.0)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [1, 1.5]})
fig.suptitle("AquaWave - Live RF Spectrum Analyzer")
line, = ax1.plot(freqs, np.full(FFT_SIZE, -100.0), linewidth=1)
ax1.set(title="Live RF Spectrum", xlabel="Frequency (MHz)", ylabel="Relative magnitude (dB)", ylim=(-120, 100))
ax1.grid(True, alpha=0.3)
img = ax2.imshow(waterfall, aspect="auto", origin="upper",
                 extent=[freqs[0], freqs[-1], WATERFALL_ROWS, 0],
                 cmap="viridis", vmin=-100, vmax=100)
ax2.set(title="RF Waterfall Spectrogram", xlabel="Frequency (MHz)", ylabel="Recent frames (newest at top)")
fig.colorbar(img, ax=ax2, label="Relative magnitude (dB)")
fig.tight_layout()


def update(_frame):
    global waterfall
    iq = np.asarray(sdr.rx()).flatten()
    if iq.size < FFT_SIZE:
        return line, img
    iq = iq[:FFT_SIZE] - np.mean(iq[:FFT_SIZE])
    spectrum = np.fft.fftshift(np.fft.fft(iq * window))
    magnitude = np.abs(spectrum) / np.sum(window)
    magnitude_db = 20 * np.log10(magnitude + 1e-12)
    line.set_ydata(magnitude_db)
    waterfall = np.roll(waterfall, 1, axis=0)
    waterfall[0] = magnitude_db
    img.set_data(waterfall)
    return line, img


ani = FuncAnimation(fig, update, interval=100, blit=False, cache_frame_data=False)
try:
    plt.show()
finally:
    sdr.rx_destroy_buffer()
    del sdr
