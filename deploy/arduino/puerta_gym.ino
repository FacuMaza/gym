/*
 * GYM-PRO — Control de puerta electromagnética
 * Arduino Nano V3 (ATmega328) con chip USB CH340
 *
 * Cableado (módulo relé de 1 canal, activo en HIGH):
 *   Arduino D8  -> IN del módulo relé
 *   GND         -> GND común Arduino + fuente relé
 *   5V          -> VCC del módulo relé (si es de 5V)
 *
 * El relé va en SERIE con el 220V del electroimán (NO lo conectes directo al Arduino).
 * Consultá a un electricista. Relé apagado = imán con energía = puerta cerrada.
 *
 * Protocolo USB serial 9600 baud:
 *   PING        -> PONG
 *   UNLOCK      -> OK  (pulso por RELAY_PULSE_MS)
 *   UNLOCK 5000 -> OK  (pulso 5000 ms)
 */

const int RELAY_PIN = 8;
const unsigned long RELAY_PULSE_MS = 3000;
const unsigned long SERIAL_BAUD = 9600;

String lineaEntrada = "";

void activarRele(unsigned long ms) {
  digitalWrite(RELAY_PIN, HIGH);
  delay(ms);
  digitalWrite(RELAY_PIN, LOW);
}

void procesarComando(String cmd) {
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "PING") {
    Serial.println(F("PONG"));
    return;
  }

  if (cmd == "UNLOCK") {
    activarRele(RELAY_PULSE_MS);
    Serial.println(F("OK"));
    return;
  }

  if (cmd.startsWith("UNLOCK ")) {
    unsigned long ms = cmd.substring(7).toInt();
    if (ms < 200) ms = 200;
    if (ms > 30000) ms = 30000;
    activarRele(ms);
    Serial.println(F("OK"));
    return;
  }

  Serial.println(F("ERR"));
}

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  Serial.begin(SERIAL_BAUD);
  while (!Serial) {
    ;
  }
  Serial.println(F("READY"));
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineaEntrada.length() > 0) {
        procesarComando(lineaEntrada);
        lineaEntrada = "";
      }
    } else {
      lineaEntrada += c;
      if (lineaEntrada.length() > 40) {
        lineaEntrada = "";
      }
    }
  }
}
