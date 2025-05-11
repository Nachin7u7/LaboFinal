#include <WiFi.h>
#include <HTTPClient.h>
#include "esp_system.h"
#include <time.h>

const char* ssid = "ESP_Movil_01";
const char* password = "12345678";
const char* serverUrl = "http://192.168.137.1:5000/node";

const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 0;
const int daylightOffset_sec = 0;

void setup() {
  Serial.begin(115200);

  IPAddress local_IP(192, 168, 4, 1);
  IPAddress gateway(192, 168, 4, 1);
  IPAddress subnet(255, 255, 255, 0);
  WiFi.softAPConfig(local_IP, gateway, subnet);

  WiFi.softAP(ssid, password);
  Serial.println("Nodo Móvil iniciado como SoftAP");
  Serial.print("SSID: ");
  Serial.println(ssid);

  Serial.println("Escaneando redes WiFi...");
  int n = WiFi.scanNetworks();
  bool networkFound = false;

  for (int i = 0; i < n; i++) {
    Serial.printf("Red encontrada: %s\n", WiFi.SSID(i).c_str());
    if (WiFi.SSID(i) == "NACHEATS-PC") {
      networkFound = true;
      break;
    }
  }

  if (networkFound) {
    WiFi.begin("NACHEATS-PC", "12345678");
    Serial.print("Conectando al WiFi...");
    while (WiFi.status() != WL_CONNECTED) {
      delay(1000);
      Serial.print(".");
    }
    Serial.println("\nConectado al WiFi del hotspot");
  } else {
    Serial.println("Red 'NACHEATS-PC' no encontrada. No se pudo conectar.");
  }

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
  float tempC = temperatureRead();

  Serial.print("Temperatura (aproximada): ");
  Serial.print(tempC);
  Serial.println(" °C");

  time_t now = time(nullptr);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    String payload = "{";
    payload += "\"id_movil\":\"" + String(ssid) + "\",";
    payload += "\"temperatura\":" + String(tempC) + ",";
    payload += "\"timestamp\":" + String(now);
    payload += "}";

    int httpResponseCode = http.POST(payload);
    if (httpResponseCode > 0) {
      Serial.println("Datos enviados al servidor:");
      Serial.println(payload);
      Serial.printf("Respuesta del servidor: %d\n", httpResponseCode);
    } else {
      Serial.printf("Error al enviar datos: %s\n", http.errorToString(httpResponseCode).c_str());
    }
    http.end();
  } else {
    Serial.println("No conectado al WiFi del hotspot");
  }

  delay(3000);
}
