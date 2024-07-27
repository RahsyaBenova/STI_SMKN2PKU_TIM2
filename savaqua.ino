#include <WiFi.h>
#include <WebServer.h>
#include <PubSubClient.h>
#include <WiFiClientSecure.h>

// WiFi credentials
const char* ssid = "OrangGantengPekanbaru";
const char* password = "12345678";

// HiveMQ Cloud Broker settings
const char* mqtt_server = "c0ae257fb0f1403bb96d10c278d890ee.s1.eu.hivemq.cloud";
const char* mqtt_username = "savaqua";
const char* topic = "/sensor/data";
const char* mqtt_password = "Savaqua123";
const int mqtt_port = 8883;

// HiveMQ Cloud Let's Encrypt CA certificate
static const char *root_ca PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC
jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc
oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq
4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA
mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d
emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----
)EOF";

// Pin definitions
const int solenoidPin = 26;
const int flowSensorPin = 27;

WebServer server(80);
WiFiClientSecure espClient;
PubSubClient client(espClient);

volatile int pulseCount = 0;
float calibrationFactor = 4.5; // kalibrasi sensor aliran
float flowRate;
unsigned long currentMillis;
unsigned long previousMillis = 0;
unsigned long interval = 1000;
float totalLiters = 0.0;
float targetLiters = 0.0;
bool isDispensing = false;

void IRAM_ATTR pulseCounter() {
  pulseCount++;
}

void setup() {
  Serial.begin(115200);
  pinMode(solenoidPin, OUTPUT);
  pinMode(flowSensorPin, INPUT_PULLUP);
  digitalWrite(solenoidPin, HIGH);  // Mulai dengan solenoid tertutup

  attachInterrupt(digitalPinToInterrupt(flowSensorPin), pulseCounter, FALLING);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");

  // Tambahkan baris ini untuk mencetak alamat IP
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.on("/start", handleStart);
  server.on("/stop", handleStop);
  server.on("/setVolume", handleSetVolume);
  server.begin();

  espClient.setCACert(root_ca);
  client.setServer(mqtt_server, mqtt_port);

  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("ESP32Client", mqtt_username, mqtt_password)) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      delay(5000);
    }
  }
}

void loop() {
  server.handleClient();
  if (isDispensing) {
    currentMillis = millis();
    if (currentMillis - previousMillis >= interval) {
      float duration = (currentMillis - previousMillis) / 1000.0; // duration in seconds
      previousMillis = currentMillis;

      if (duration > 0) {
        flowRate = (pulseCount / calibrationFactor) / duration;
        pulseCount = 0;
        float flowLiters = (flowRate / 60) * duration;
        totalLiters += flowLiters;
        Serial.print("Flow rate: ");
        Serial.print(flowRate);
        Serial.print(" L/min\tTotal: ");
        Serial.print(totalLiters);
        Serial.println(" L");

        // Publish flow rate and total liters to MQTT
        String payload = "Flow rate: " + String(flowRate) + " L/min, Total: " + String(totalLiters) + " L";
        client.publish(topic, payload.c_str());
      } else {
        Serial.println("Duration is zero, skipping calculation to avoid NaN");
      }

      if (totalLiters >= targetLiters) {
        digitalWrite(solenoidPin, HIGH);  // Menutup solenoid
        isDispensing = false;
        totalLiters = 0.0;
        Serial.println("Target reached. Stopping...");
      }
    }
  }
  client.loop();
}

void handleRoot() {
  String html = "<html><body>";
  html += "<h1>Water Dispensing Control</h1>";
  html += "<form action=\"/setVolume\" method=\"POST\">";
  html += "Enter water volume (liters): <input type=\"text\" name=\"volume\">";
  html += "<input type=\"submit\" value=\"Set Volume\">";
  html += "</form>";
  html += "<br>";
  html += "<button onclick=\"location.href='/start'\">Start</button>";
  html += "<button onclick=\"location.href='/stop'\">Stop</button>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleStart() {
  if (targetLiters > 0) {
    digitalWrite(solenoidPin, LOW);  // Membuka solenoid
    isDispensing = true;
    totalLiters = 0.0;
    Serial.println("Dispensing started...");
  }
  server.sendHeader("Location", "/");
  server.send(303);
}

void handleStop() {
  digitalWrite(solenoidPin, HIGH);  // Menutup solenoid
  isDispensing = false;
  totalLiters = 0.0;
  Serial.println("Dispensing stopped...");
  server.sendHeader("Location", "/");
  server.send(303);
}

void handleSetVolume() {
  if (server.hasArg("volume")) {
    targetLiters = server.arg("volume").toFloat();
    Serial.print("Target volume set to: ");
    Serial.print(targetLiters);
    Serial.println(" L");
  }
  server.sendHeader("Location", "/");
  server.send(303);
}
