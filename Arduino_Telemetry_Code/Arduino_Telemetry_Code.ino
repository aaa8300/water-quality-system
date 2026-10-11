
#include <SPI.h>
#include <RadioLib.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ===== SENSOR PINS =====
#define TEMP_PIN 2
#define TURBIDITY_PIN A1
#define PH_PIN A0

// ===== CC1101 PINS =====
#define CC_CS 10
#define CC_GDO0 3

// ===== RF SETTINGS =====
const float RF_FREQ = 433.8;
const float RF_RATE = 10.0;
const float RF_DEV = 40.0;
const float RF_BW = 464.0;
const int8_t RF_POWER = -10;

// Enable only after verifying safe wiring,
// permitted RF operation and test setup.
const bool ENABLE_RF_TX = true;

// ===== SENSORS =====
OneWire oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);

// ===== CC1101 =====

CC1101 radio = new Module(
  10,           // CSN
  3,            // GDO0
  RADIOLIB_NC,  // Reset unused
  4             // GDO2
);


bool radioReady = false;

// ===== 32-BYTE PAYLOAD =====
uint8_t payload[32] = {0};

// ===== SENSOR AVERAGING =====
float readAverage(int pin) {
  long total = 0;

  for (int i = 0; i < 20; i++) {
    total += analogRead(pin);
    delay(5);
  }

  return total / 20.0;
}

// ===== CHECK RADIO SETTINGS =====
bool checkRF(int state, const char* step) {
  if (state == RADIOLIB_ERR_NONE) {
    return true;
  }

  Serial.print("ERROR at ");
  Serial.print(step);
  Serial.print(": ");
  Serial.println(state);

  return false;
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(10);

  tempSensor.begin();

  Serial.println("Starting CC1101 transmitter...");

  if (!ENABLE_RF_TX) {
    Serial.println("RF disabled - sensor test mode");
    return;
  }

  SPI.begin();

  // Frequency, bitrate, deviation,
  // bandwidth, TX power, preamble bits
  int state = radio.begin(
    RF_FREQ,
    RF_RATE,
    RF_DEV,
    RF_BW,
    RF_POWER,
    64
  );

  if (!checkRF(state, "radio.begin")) return;

  // Enable GFSK
  state = radio.setDataShaping(
    RADIOLIB_SHAPING_0_5
  );
  if (!checkRF(state, "GFSK")) return;

  // Set sync word 0x1234
  state = radio.setSyncWord(0x12, 0x34);
  if (!checkRF(state, "sync")) return;

  // Exactly 32 payload bytes
  state = radio.fixedPacketLengthMode(32);
  if (!checkRF(state, "packet length")) return;

  // Enable data whitening
  state = radio.setEncoding(
    RADIOLIB_ENCODING_WHITENING
  );
  if (!checkRF(state, "whitening")) return;

  // Enable CRC
  state = radio.setCrcFiltering(true);
  if (!checkRF(state, "CRC")) return;

  radioReady = true;

  Serial.println("CC1101 READY!");
}

void loop() {

  // ===== TEMPERATURE =====
  tempSensor.requestTemperatures();
  float temp = tempSensor.getTempCByIndex(0);

  // ===== TURBIDITY =====
  float turbidity = readAverage(TURBIDITY_PIN);

  // ===== SIMULATED pH =====
  float phRaw = readAverage(PH_PIN);
  float ph = constrain(
    phRaw * 14.0 / 1023.0,
    0.0,
    14.0
  );

  // ===== BUILD MESSAGE =====
  String tempText =
    (temp == DEVICE_DISCONNECTED_C)
      ? "ERR"
      : String(temp, 2);

  String message =
    "T=" + tempText +
    ";U=" + String((int)turbidity) +
    ";P=" + String(ph, 2) +
    ";S=1";

  // Reject oversized payloads
  if (message.length() >= sizeof(payload)) {
    Serial.println("ERROR: Payload too long!");
    delay(1000);
    return;
  }

  // Clear and fill exactly 32 bytes
  memset(payload, 0, sizeof(payload));
  message.getBytes(payload, sizeof(payload));

  // ===== PRINT PACKET =====
  Serial.print("TX: ");
  Serial.print(message);

  Serial.print(" | Bytes: ");
  Serial.print(sizeof(payload));

  // ===== TRANSMIT =====
  if (ENABLE_RF_TX && radioReady) {

    int state = radio.transmit(
      payload,
      sizeof(payload)
    );

    Serial.print(" | Result: ");

    if (state == RADIOLIB_ERR_NONE) {
      Serial.println("OK");
    } else {
      Serial.print("FAIL ");
      Serial.println(state);
    }

  } else {
    Serial.println(" | Result: RF DISABLED");
  }

  delay(1000);
}
