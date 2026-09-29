import numpy as np
import scipy.io.wavfile as wavfile

sr = 44100
duration = 90.0
total_samples = int(sr * duration)
t = np.linspace(0, duration, total_samples, endpoint=False)

# Lo-fi Chord progression: Dm9 -> G13 -> Cmaj9 -> Am9 (classic lo-fi jazz progression)
# Chord frequencies in Hz
# Dm9: D3 (146.83), F3 (174.61), A3 (220.00), C4 (261.63), E4 (329.63)
# G13: G2 (98.00), F3 (174.61), B3 (246.94), E4 (329.63), A4 (440.00)
# Cmaj9: C3 (130.81), E3 (164.81), G3 (196.00), B3 (246.94), D4 (293.66)
# Am9: A2 (110.00), G3 (196.00), C4 (261.63), E4 (329.63), B4 (493.88)

chords = [
    [146.83, 174.61, 220.00, 261.63, 329.63],
    [98.00, 174.61, 246.94, 329.63, 440.00],
    [130.81, 164.81, 196.00, 246.94, 293.66],
    [110.00, 196.00, 261.63, 329.63, 493.88]
]

bar_duration = 3.0 # seconds per chord
audio = np.zeros(total_samples, dtype=np.float32)

num_bars = int(duration / bar_duration) + 1
for bar in range(num_bars):
    chord = chords[bar % len(chords)]
    start_idx = int(bar * bar_duration * sr)
    end_idx = min(int((bar + 1) * bar_duration * sr), total_samples)
    bar_len = end_idx - start_idx
    if bar_len <= 0:
        break
    
    t_bar = np.linspace(0, bar_len / sr, bar_len, endpoint=False)
    # Electric piano / Rhodes envelope (percussive attack, gentle decay)
    env = np.exp(-t_bar * 1.2)
    
    bar_signal = np.zeros(bar_len, dtype=np.float32)
    for freq in chord:
        # Fundamental + warm soft second harmonic with gentle vibrato (chorus / wow effect)
        vibrato = 0.5 * np.sin(2 * np.pi * 4.5 * t_bar)
        tone = np.sin(2 * np.pi * (freq + vibrato) * t_bar) + 0.3 * np.sin(2 * np.pi * (freq * 2) * t_bar)
        bar_signal += tone
    
    bar_signal = (bar_signal / len(chord)) * env
    audio[start_idx:end_idx] += bar_signal

# Add subtle mellow kick and snare / rim rhythm (lo-fi hip-hop groove)
# BPM = 80 => beat = 0.75s
beat_dur = 0.75
num_beats = int(duration / beat_dur)
for b in range(num_beats):
    beat_start = int(b * beat_dur * sr)
    beat_type = b % 4
    if beat_type in [0, 2]: # Kick on 1 and 3
        k_len = int(0.25 * sr)
        if beat_start + k_len < total_samples:
            t_k = np.linspace(0, 0.25, k_len, endpoint=False)
            freq_drop = 120 * np.exp(-t_k * 30) + 45
            phase = np.cumsum(freq_drop) / sr
            kick = np.sin(2 * np.pi * phase) * np.exp(-t_k * 15) * 0.4
            audio[beat_start:beat_start + k_len] += kick
    if beat_type in [1, 3]: # Soft snare/rim on 2 and 4
        s_len = int(0.18 * sr)
        if beat_start + s_len < total_samples:
            t_s = np.linspace(0, 0.18, s_len, endpoint=False)
            noise = np.random.uniform(-1, 1, s_len) * np.exp(-t_s * 25) * 0.12
            audio[beat_start:beat_start + s_len] += noise

# Add subtle vinyl crackle
vinyl = np.random.normal(0, 0.008, total_samples)
# occasional pops
pops = (np.random.uniform(0, 1, total_samples) > 0.9997) * np.random.uniform(-0.06, 0.06, total_samples)
audio += vinyl + pops

# Normalize to comfortable listening volume (-14 LUFS approx, peak at -1 dB)
max_val = np.max(np.abs(audio))
if max_val > 0:
    audio = audio / max_val * 0.85

# Convert to 16-bit PCM
audio_int16 = (audio * 32767).astype(np.int16)
wavfile.write("/tmp/proper_lofi.wav", sr, audio_int16)
print("Saved /tmp/proper_lofi.wav successfully")
