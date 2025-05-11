#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>

const char* ssid = "NACHEATS-PC";
const char* password = "12345678";
const char* serverUrl = "http://192.168.137.1:5000/beacon";

const char* targetSSID = "ESP_Movil_";
const char* beaconId = "beacon_03";

const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 0;
const int daylightOffset_sec = 0;

void setup() {
  Serial.begin(115200);
  connectToWiFi();

  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  Serial.println("Sincronizando tiempo con NTP...");
  struct tm timeinfo;
  while (!getLocalTime(&timeinfo)) {
    Serial.print(".");
    delay(1000);
  }
  Serial.println("\nTiempo sincronizado.");
}

void loop() {
  Serial.println("Iniciando escaneo Wi-Fi...");
  int numNetworks = WiFi.scanNetworks();

  if (numNetworks == 0) Serial.println("No se encontraron redes.");
  else {
    for (int i = 0; i < numNetworks; ++i) {
      String ssid = WiFi.SSID(i);
      int rssi = WiFi.RSSI(i);

      if (ssid.indexOf(targetSSID) != -1) {
        Serial.println("Nodo Móvil detectado:");
        Serial.print("SSID: ");
        Serial.println(ssid);
        Serial.print("RSSI: ");
        Serial.print(rssi);
        Serial.println(" dBm");

        String nodeId = ssid.substring(strlen(targetSSID));

        time_t now = time(nullptr);

        sendBeaconData(ssid, rssi, now);
      }
    }
  }

  WiFi.scanDelete();
  delay(5000);
}

void connectToWiFi() {
  Serial.println("Escaneando redes Wi-Fi para encontrar NACHEATS-PC...");
  int numNetworks = WiFi.scanNetworks();

  bool networkFound = false;
  for (int i = 0; i < numNetworks; ++i) {
    String foundSSID = WiFi.SSID(i);
    if (foundSSID == ssid) {
      networkFound = true;
      break;
    }
  }

  if (networkFound) {
    Serial.print("Conectando a ");
    Serial.println(ssid);
    WiFi.begin(ssid, password);

    while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
    }
    Serial.println("\nConectado a Wi-Fi");
  } else {
    Serial.println("Red NACHEATS-PC no encontrada. Intentando nuevamente en 5 segundos...");
    delay(5000);
    connectToWiFi();
  }
}

void sendBeaconData(String nodeId, int rssi, unsigned long timestamp) {
  time_t now = time(nullptr);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    String jsonPayload = "{\"id_beacon\":\"" + String(beaconId) + "\","
                                                                  "\"id_movil\":\""
                         + nodeId + "\","
                                    "\"rssi\":"
                         + String(rssi) + ","
                                          "\"timestamp\":"
                         + String(now) + "}";

    int httpResponseCode = http.POST(jsonPayload);

    if (httpResponseCode > 0) {
      Serial.print("Datos enviados. Código de respuesta: ");
      Serial.println(httpResponseCode);
    } else {
      Serial.print("Error al enviar datos. Código de error: ");
      Serial.println(httpResponseCode);
    }

    http.end();
  } else {
    Serial.println("No conectado a Wi-Fi. No se pueden enviar datos.");
  }
}
