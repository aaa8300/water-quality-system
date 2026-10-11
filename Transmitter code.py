import adi
import numpy as np
import json
import paho.mqtt.client as mqtt

# =====================================
# CONFIGURATION
# =====================================

URI = "usb:2.37.5"  # Change later

CENTER_FREQ = 433_800_000
SAMPLE_RATE = 1_000_000
RX_BANDWIDTH = 500_000
RX_GAIN_DB = 10
BUFFER_SIZE = 262144

DATA_RATE = 10_000
SAMPLES_PER_BIT = SAMPLE_RATE / DATA_RATE

SYNC_WORD = 0x1234
PREAMBLE_BITS = 64
PAYLOAD_BYTES = 32
CRC_BYTES = 2

MAG_SMOOTH = 64
DISC_SMOOTH = 20

THRESHOLD_MULTIPLIER = 1.5
MIN_BURST_MS = 8.0
MAX_GAP_US = 500

MIN_FSK_SEPARATION_KHZ = 45.0

SYNC_BITS = np.array(
    [(SYNC_WORD >> i) & 1
     for i in range(15, -1, -1)],
    dtype=np.uint8
)

# =====================================
# BIT HELPERS
# =====================================

def bits_to_bytes(bits):
    usable = len(bits) // 8 * 8

    if usable == 0:
        return b""

    return np.packbits(
        np.asarray(bits[:usable],
                   dtype=np.uint8)
    ).tobytes()


# =====================================
# PN9 DEWHITENING
# =====================================

def dewhiten(data):
    """
    PN9 decoder matching the original
    receiver's LFSR convention.
    """
    lfsr = 0x1FF
    output = bytearray()

    for byte in data:
        decoded = 0

        for bit in range(8):
            data_bit = (byte >> bit) & 1
            pn_bit = lfsr & 1

            decoded |= (
                (data_bit ^ pn_bit) << bit
            )

            feedback = (
                (lfsr ^ (lfsr >> 5)) & 1
            )

            lfsr = (
                (lfsr >> 1) |
                (feedback << 8)
            )

        output.append(decoded)

    return bytes(output)


# =====================================
# MQTT CONFIGURATION / PUBLISHER
# =====================================
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "knighthacks/water"

mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="knighthacks_plutosdr"
)

mqtt_ready = False
try:
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    mqtt_ready = True
    print(f"MQTT connecting: {MQTT_HOST}:{MQTT_PORT} -> {MQTT_TOPIC}")
except OSError as exc:
    print(f"WARNING: MQTT broker unavailable ({exc}). RF decoding will continue.")


def publish_sensor_data(message):
    # Example: T=23.75;U=483;P=13.12;S=1
    try:
        fields = dict(
            part.split("=", 1)
            for part in message.strip().split(";")
        )

        data = {
            "temperature_c": float(fields["T"]),
            "turbidity_adc": int(fields["U"]),
            "ph_simulated": float(fields["P"]),
            "ph_is_simulated": fields["S"] == "1"
        }

        payload = json.dumps(data)

        if not mqtt_ready:
            print("MQTT skipped (broker not connected):", payload)
            return

        info = mqtt_client.publish(MQTT_TOPIC, payload, qos=1)
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            print("MQTT publish queued:", payload)
        else:
            print("MQTT publish error:", info.rc)

    except (ValueError, KeyError, TypeError) as e:
        print("Invalid sensor packet:", e)



# =====================================
# BURST DETECTION
# =====================================

def find_regions(samples):
    magnitude = np.abs(samples)

    kernel = (
        np.ones(MAG_SMOOTH) / MAG_SMOOTH
    )

    smooth = np.convolve(
        magnitude, kernel, mode="same"
    )

    noise = np.percentile(smooth, 20)

    threshold = max(
        noise * THRESHOLD_MULTIPLIER,
        1e-9
    )

    active = np.where(
        smooth > threshold
    )[0]

    if len(active) == 0:
        return []

    max_gap = int(
        MAX_GAP_US * 1e-6 * SAMPLE_RATE
    )

    splits = np.where(
        np.diff(active) > max_gap + 1
    )[0]

    starts = np.r_[
        active[0],
        active[splits + 1]
    ]

    ends = np.r_[
        active[splits] + 1,
        active[-1] + 1
    ]

    min_samples = int(
        MIN_BURST_MS * 1e-3 * SAMPLE_RATE
    )

    regions = []

    for start, end in zip(starts, ends):
        if end - start >= min_samples:

            # Include a small margin
            start = max(0, start - 200)
            end = min(
                len(samples), end + 200
            )

            regions.append((start, end))

    return regions


# =====================================
# FREQUENCY DISCRIMINATOR
# =====================================

def discriminator(burst):
    phase_difference = np.angle(
        burst[1:] * np.conj(burst[:-1])
    )

    frequency_khz = (
        phase_difference
        * SAMPLE_RATE
        / (2 * np.pi * 1000)
    )

    kernel = (
        np.ones(DISC_SMOOTH) / DISC_SMOOTH
    )

    return np.convolve(
        frequency_khz,
        kernel,
        mode="same"
    )


# =====================================
# FSK LEVEL ESTIMATION
# =====================================

def find_fsk_levels(disc):
    lo = np.percentile(disc, 2)
    hi = np.percentile(disc, 98)

    values = disc[
        (disc >= lo) & (disc <= hi)
    ]

    if len(values) < 10:
        return 0, 0, 0

    c1, c2 = np.percentile(
        values, [25, 75]
    )

    for _ in range(15):
        distances1 = np.abs(values - c1)
        distances2 = np.abs(values - c2)

        group1 = values[
            distances1 <= distances2
        ]

        group2 = values[
            distances2 < distances1
        ]

        if len(group1):
            c1 = np.mean(group1)

        if len(group2):
            c2 = np.mean(group2)

    low, high = sorted([c1, c2])

    return low, high, (low + high) / 2


# =====================================
# FAST SYMBOL SAMPLING
# =====================================

def sample_symbols(disc, sps, phase):
    """
    Integrate the middle 50% of
    each symbol period.
    """

    n = int(
        (len(disc) - phase) / sps
    )

    if n < 90:
        return None

    positions = phase + (
        np.arange(n) * sps
    )

    a = (
        positions + 0.25 * sps
    ).astype(int)

    b = (
        positions + 0.75 * sps
    ).astype(int)

    valid = b < len(disc)

    a = a[valid]
    b = b[valid]

    if len(a) < 90:
        return None

    cumulative = np.r_[
        0, np.cumsum(disc)
    ]

    averages = (
        cumulative[b] - cumulative[a]
    ) / np.maximum(b - a, 1)

    return averages


# =====================================
# PREAMBLE VALIDATION
# =====================================

def preamble_errors(bits, sync_start):
    if sync_start < PREAMBLE_BITS:
        return 999

    preamble = bits[
        sync_start - PREAMBLE_BITS:
        sync_start
    ]

    pattern = (
        np.arange(PREAMBLE_BITS) % 2
    ).astype(np.uint8)

    errors = np.sum(
        preamble != pattern
    )

    return int(
        min(errors, PREAMBLE_BITS - errors)
    )


# =====================================
# FIXED 32-BYTE PACKET DECODER
# =====================================

def parse_packet(bits, sync_start):
    start = sync_start + 16
    end = start + PAYLOAD_BYTES * 8

    if len(bits) < end:
        return None

    raw = bits_to_bytes(
        bits[start:end]
    )

    # Try PN9 dewhitening
    decoded = dewhiten(raw)

    # Remove trailing zero padding
    payload = decoded.rstrip(b"\x00")

    try:
        message = payload.decode("ascii")
    except UnicodeDecodeError:
        return None

    if not (
        message.startswith("T=")
        and ";U=" in message
        and ";P=" in message
        and ";S=1" in message
    ):
        return None

    return message


# =====================================
# SYNC SEARCH
# =====================================

def search_sync(bits):
    """
    Find exact 0x1234 sync pattern.
    """

    if len(bits) < (
        PREAMBLE_BITS + 16 +
        PAYLOAD_BYTES * 8
    ):
        return []

    # Vectorized sync comparison
    matches = np.correlate(
        bits.astype(np.int16),
        SYNC_BITS.astype(np.int16) * 2 - 1,
        mode="valid"
    )

    # Exact match requires all 16 bits
    sync_positions = np.where(
        matches == int(SYNC_BITS.sum())
    )[0]

    return sync_positions


# =====================================
# DECODE BURST
# =====================================

def decode_burst(disc, threshold):

    sync_candidates = 0

    # Search symbol clock mismatch
    for sps in np.arange(
        99.0, 101.01, 0.5
    ):

        for phase in range(
            0, int(np.ceil(sps)), 2
        ):

            values = sample_symbols(
                disc, sps, phase
            )

            if values is None:
                continue

            raw_bits = (
                values > threshold
            ).astype(np.uint8)

            # Try both FSK polarities
            for polarity, bits in [
                ("NORMAL", raw_bits),
                ("INVERTED", 1 - raw_bits)
            ]:

                sync_positions = search_sync(
                    bits
                )

                for pos in sync_positions:

                    errors = preamble_errors(
                        bits, pos
                    )

                    if errors > 6:
                        continue

                    sync_candidates += 1

                    message = parse_packet(
                        bits, pos
                    )

                    if message is not None:
                        return {
                            "message": message,
                            "sps": sps,
                            "phase": phase,
                            "polarity": polarity,
                            "sync_position": int(pos),
                            "preamble_errors": errors
                        }, sync_candidates

    return None, sync_candidates


# =====================================
# PLUTOSDR SETUP
# =====================================

print("================================")
print("KNIGHT HACKS IX - RF RECEIVER")
print("CC1101 GFSK / 433.8 MHz")
print("================================")

print("Connecting to PlutoSDR...")

sdr = adi.Pluto(URI)

sdr.rx_lo = CENTER_FREQ
sdr.sample_rate = SAMPLE_RATE
sdr.rx_rf_bandwidth = RX_BANDWIDTH
sdr.rx_buffer_size = BUFFER_SIZE

sdr.gain_control_mode_chan0 = "manual"
sdr.rx_hardwaregain_chan0 = RX_GAIN_DB

print("PlutoSDR connected!")
print("Waiting for CC1101 packets...")

# Discard old samples
sdr.rx()

# =====================================
# LIVE RECEIVER
# =====================================

buffer_number = 0
decoded_packets = 0

try:
    while True:

        buffer_number += 1

        samples = sdr.rx()

        regions = find_regions(samples)

        print(
            f"Buffer {buffer_number}: "
            f"{len(regions)} candidate bursts"
        )

        for start, end in regions:

            burst = samples[start:end]

            duration_ms = (
                len(burst) / SAMPLE_RATE
                * 1000
            )

            disc = discriminator(burst)

            low, high, threshold = (
                find_fsk_levels(disc)
            )

            separation = high - low

            if separation < (
                MIN_FSK_SEPARATION_KHZ
            ):
                continue

            print(
                f"  CC1101-like burst: "
                f"{duration_ms:.1f} ms | "
                f"FSK {low:.1f} / "
                f"{high:.1f} kHz"
            )

            result, candidates = decode_burst(
                disc, threshold
            )

            if result is None:
                if candidates:
                    print(
                        "  Sync found, but "
                        "payload not decoded"
                    )
                continue

            decoded_packets += 1

            print()
            print("============================")
            print("PACKET DECODED")
            print("============================")

            print(result["message"])
            publish_sensor_data(result["message"])

            print(
                "Samples/symbol:",
                result["sps"]
            )

            print(
                "Polarity:",
                result["polarity"]
            )

            print(
                "Preamble errors:",
                result["preamble_errors"]
            )

            print(
                "FSK separation:",
                f"{separation:.1f} kHz"
            )

            print(
                "Total decoded:",
                decoded_packets
            )

            print("============================")
            print()

except KeyboardInterrupt:
    print("\nReceiver stopped.")

finally:
    if mqtt_ready:
        mqtt_client.disconnect()
        mqtt_client.loop_stop()
    del sdr
