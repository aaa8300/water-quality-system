AquaWave: Wireless Water-Quality Monitoring with a Custom SDR Receiver

Team Perry the Platypus · Knight Hacks IX · October 2026

AquaWave is a low-cost wireless water-quality monitor. An Arduino node reads temperature, turbidity, and pH and transmits them over 433.8 MHz GFSK. An ADALM-Pluto software-defined radio running our own Python demodulator recovers the packets, and the readings flow through MQTT and Amazon S3 into Databricks for analysis and visualization.

Note on pH: after about eight hours of unreliable readings from the pH probe, we replaced it with a potentiometer so the rest of the pipeline could be tested end to end. pH values in this project are simulated and are flagged as such (ph_is_simulated) in every record.

<!-- TODO: add a screenshot of the live spectrum / waterfall here --> <!-- ![Pluto spectrum and waterfall](docs/waterfall.png) -->
Architecture
Sensors ─► Arduino UNO R4 WiFi ─► CC1101 radio (433.8 MHz, 10 kbps GFSK)
                                          │  over the air
                                          ▼
                               ADALM-Pluto SDR (IQ at 1 MS/s)
                                          │
                         Python receiver (custom demodulator)
                                          │  JSON over MQTT (topic: knighthacks/water)
                                          ▼
                         mqtt_to_s3.py ─► Amazon S3 (JSON batches)
                                          │  Databricks Auto Loader
                                          ▼
                         Bronze ─► Silver ─► Gold ─► Dashboard
Transmitter (Arduino + CC1101)
Item	Detail
Board	Arduino UNO R4 WiFi
Radio	CC1101, 433.8 MHz, 10 kbps, ±40 kHz deviation, Gaussian-shaped 2-FSK
Framing	64-bit preamble, sync word 0x1234, fixed 32-byte payload, PN9 whitening, 16-bit CRC
Power	−10 dBm (low-power bench testing; only transmit where permitted)
Temperature	OneWire digital sensor on D2 (DallasTemperature library)
Turbidity	Analog sensor on A1 (20-sample average, 10-bit ADC)
pH	Simulated with a potentiometer on A0, mapped to 0–14
Rate	about 1 packet every 2 s (sensor conversion + averaging + 1 s delay)

Packets are short ASCII strings, for example:

T=23.75;U=483;P=13.12;S=1

T is temperature in °C, U is the turbidity ADC value, P is pH, and S=1 means the pH value is simulated.

Receiver (ADALM-Pluto + Python)

The receiver does not use a prebuilt demodulator. Each captured buffer goes through:

Burst detection: smoothed magnitude against a percentile-based noise floor.
FM discriminator: phase difference of consecutive IQ samples gives instantaneous frequency.
Adaptive 2-FSK slicing: the two frequency levels are estimated per burst and the decision threshold is set at their midpoint, which also compensates for carrier frequency offset.
Symbol-timing search: candidate samples-per-bit and phase offsets, with mid-symbol integration.
Polarity search: both bit polarities are tried.
Sync and preamble validation: exact 0x1234 correlation plus a preamble error check.
PN9 de-whitening and parsing: the 32-byte payload is de-whitened, parsed, and published to MQTT as JSON.

Published JSON:

json
{"temperature_c": 23.75, "turbidity_adc": 483, "ph_simulated": 13.12, "ph_is_simulated": true}

A separate script (pluto_spectrum.py) shows a live spectrum and waterfall for locating and debugging the signal.

Cloud pipeline
MQTT → S3: decoded readings are published to a local Mosquitto broker, then uploaded to S3 as JSON batches.
Bronze: Databricks Auto Loader incrementally ingests the S3 JSON into a Delta table with an explicit schema.
Silver: removes duplicate rows and rows with missing fields.
Gold: 1-minute window aggregates (average temperature, turbidity, and pH, plus a reading count) that feed the dashboard.
<!-- TODO: add a dashboard screenshot using the overnight data range --> <!-- ![Dashboard](docs/dashboard.png) -->
Results
Metric	Value
Expected rate (from firmware timing)	about 30 packets/min
Observed at 3 m	typically 26–29 decoded readings/min, estimated 90%+ packet reception
Observed at 4 m	noticeably more decode glitches
Logged data	about 7 hours across two sessions (10/10 19:14 UTC to 10/11 13:17 UTC, with a gap)
Total readings	<!-- TODO: SELECT SUM(reading_count) FROM workspace.default.water_quality_gold -->

The reception figure is an estimate (decoded readings per minute against the rate implied by the transmitter loop), not a counted result from a sequence-numbered test.

Known limitations and next steps
pH is simulated. Next step is a properly calibrated pH sensor.
The decoder does not yet verify the CC1101 CRC. Corrupted packets that still parse as valid text can get through, which showed up as outlier values at 4 m. Adding a CRC check and counting CRC passes and failures would give a measured packet success rate.
The gold layer uses averages. In minutes with only a few readings, a single bad packet skews the result. A median or a minimum-count filter would be more robust.
Range is limited. Next steps include a higher receiver gain, a narrower receive bandwidth, and overlapping capture buffers so packets spanning two buffers are not lost.
Algae-bloom risk estimation is future work. The system collects the inputs (temperature, turbidity, pH); a risk model and alerts are not implemented yet.
Single node. The design could extend to multiple sensor nodes.
Run it

Requirements: Arduino IDE with RadioLib, OneWire, and DallasTemperature; Python 3 with pyadi-iio, numpy, paho-mqtt, and matplotlib; a local Mosquitto broker; an ADALM-Pluto; an AWS account with an S3 bucket; a Databricks workspace.

Flash the transmitter sketch in firmware/ to the Arduino and power it.
Start Mosquitto on 127.0.0.1:1883.
Set your Pluto URI in receiver/pluto_receiver.py, then run it.
Run cloud/mqtt_to_s3.py with your AWS credentials configured (environment variables or an AWS profile; never commit keys).
In Databricks, run the notebooks in databricks/ in order: bronze, silver, gold.
Repository layout
firmware/      Arduino transmitter sketch
receiver/      Pluto receiver and spectrum viewer
cloud/         MQTT-to-S3 uploader
databricks/    Bronze ingestion notebook, silver and gold SQL
docs/          Screenshots
