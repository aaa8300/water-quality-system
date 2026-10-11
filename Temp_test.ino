void setup() {
  // put your setup code here, to run once:

}

void loop() {
  // put your main code here, to run repeatedly:

}
#include <OneWire.h>

OneWire ds(2);

void setup() {
  Serial.begin(9600);
  delay(1000);
}

void loop() {
  byte address[8];

  ds.reset_search();

  if (ds.search(address)) {
    Serial.println("Sensor detected!");
  } else {
    Serial.println("No sensors connected!");
  }

  delay(2000);
}

