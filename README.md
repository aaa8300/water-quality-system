# water-quality-system

## Inspiration
Water quality is essential for healthy ecosystems and communities, but monitoring environmental conditions can require expensive equipment and complex infrastructure. We wanted to create a wireless monitoring system that could collect sensor data and make it accessible through cloud technology.

This inspired AquaWave, a project combining embedded systems, software-defined radio, and cloud analytics to explore a more accessible approach to environmental monitoring.

## What it does
AquaWave collects water-quality data using a temperature, pH, and turbidity sensor to predict the chance of an algae bloom. An Arduino transmits the readings wirelessly through a CC1101 radio module, while an ADALM-Pluto software-defined radio receives and decodes the signals.

The decoded measurements are published through MQTT and uploaded to Amazon S3 as JSON batches. Databricks provides a foundation for analyzing historical sensor data, while our dashboard is designed to visualize readings and environmental changes.

## How we built it
We started with an Arduino UNO R4 WiFi connected to our sensor inputs and a CC1101 radio operating at 433 MHz. The Arduino collects measurements and transmits them wirelessly.

On the receiving side, we used an ADALM-Pluto SDR and developed custom Python digital signal-processing code to recover the transmitted data. Our decoder processes frequency-shift-keyed signals, synchronizes with packets, and reconstructs the sensor readings.

We then connected the decoded telemetry to MQTT and built a Python pipeline that uploads JSON batches to Amazon S3. We configured a Databricks external location to support cloud-based analysis and worked on a dashboard for visualizing the data.

## Challenges we ran into
Our biggest challenge was the pH sensor. We spent approximately eight hours troubleshooting inconsistent readings before deciding to replace it with a potentiometer. This allowed us to simulate pH changes while keeping the rest of our system functional and avoiding inaccurate measurements.

Another major challenge was decoding wireless transmissions using the Pluto SDR. Recovering digital packets from raw radio signals required debugging frequency offsets, timing, synchronization, and signal processing.

Connecting the embedded hardware, radio receiver, MQTT, and cloud services also required careful coordination to keep the data flowing consistently.

## Accomplishments that we're proud of
Our proudest accomplishment was successfully transmitting sensor data over radio and decoding it with our own software-defined radio receiver. Instead of relying on a conventional receiver, we implemented the signal-processing pipeline ourselves.

We also established live MQTT telemetry and successfully uploaded JSON batches to Amazon S3. Bringing together embedded hardware, wireless communication, Python, and cloud infrastructure into one system was a major achievement for our team.

## What we learned
AquaWave gave us hands-on experience with embedded programming, RF communication, digital signal processing, MQTT, and cloud infrastructure.

We learned how software can recover information from raw radio signals and how sensor measurements can move from physical hardware into cloud storage and analytics.

Most importantly, we learned how to adapt when hardware does not behave as expected. Our pH sensor difficulties reinforced the importance of reliable measurements, honest reporting, and making practical engineering decisions under time constraints.

## What's next for AquaWave
We plan to integrate a properly calibrated pH sensor, improve wireless reliability, expand our Databricks analytics, and develop more advanced environmental alerts.

In the future, AquaWave could support multiple wireless sensor nodes and provide a more comprehensive platform for monitoring water conditions.
