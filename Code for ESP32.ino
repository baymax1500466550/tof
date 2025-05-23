#include <Wire.h>
#include "HT_SSD1306Wire.h"
#include <WiFi.h>

static SSD1306Wire display(0x3c, 500000, SDA_OLED, SCL_OLED, GEOMETRY_128_64, RST_OLED);

// Soft-AP credentials
const char* ssid     = "ROS";
const char* password = "0123456789";

#define MAX_DEVICES 4

struct DeviceInfo {
  String ip;
  String mac;
};

DeviceInfo devices[MAX_DEVICES];
int deviceCount = 0;

const String robotMac = "B8:27:EB:8E:B2:93";

void addDevice(const String& ip, const String& mac) {
  // Check if device already exists, update IP if so
  for (int i = 0; i < deviceCount; i++) {
    if (devices[i].mac == mac) {
      devices[i].ip = ip;
      return;
    }
  }
  // Add new device
  if (deviceCount < MAX_DEVICES) {
    devices[deviceCount++] = {ip, mac};
  } else {
    // Shift buffer left and insert new device at end
    for (int i = 1; i < MAX_DEVICES; i++) {
      devices[i - 1] = devices[i];
    }
    devices[MAX_DEVICES - 1] = {ip, mac};
  }
}

// Remove disconnected device by MAC address
void removeDeviceByMac(const uint8_t* macRaw) {
  char macBuf[18];
  snprintf(macBuf, sizeof(macBuf),
           "%02X:%02X:%02X:%02X:%02X:%02X",
           macRaw[0], macRaw[1], macRaw[2],
           macRaw[3], macRaw[4], macRaw[5]);
  String mac(macBuf);

  // Find and remove device from buffer
  for (int i = 0; i < deviceCount; i++) {
    if (devices[i].mac == mac) {
      for (int j = i + 1; j < deviceCount; j++) {
        devices[j - 1] = devices[j];
      }
      deviceCount--;
      break;
    }
  }
}

// Redraw device list: IP line, MAC line, separator line
// Show message if no devices connected
void redrawDevices() {
  display.clear();
  display.setTextAlignment(TEXT_ALIGN_LEFT);
  display.setFont(ArialMT_Plain_10);
  int screenWidth = display.getWidth();

  if (deviceCount == 0) {
    display.drawString(0, 0, "No devices connected");
  } else {
    int y = 0;
    for (int i = 0; i < deviceCount; i++) {
      String ipLine = devices[i].ip;
      // Append "(robot)" tag for the specific MAC
      if (devices[i].mac == robotMac) {
        ipLine += " (robot)";
      }
      // Draw IP address
      display.drawString(0, y, ipLine);
      y += 12;
      // Draw MAC address
      display.drawString(0, y, devices[i].mac);
      y += 12;
      // Draw separator line
      display.drawLine(0, y - 1, screenWidth - 1, y - 1);
      y += 2; // Small gap after line
    }
  }
  display.display();
}

// Event handler: new device assigned an IP by DHCP server
void onStaIpAssigned(WiFiEvent_t event, arduino_event_info_t info) {
  // Extract assigned IP address
  IPAddress ipAddr = IPAddress(info.wifi_ap_staipassigned.ip.addr);
  String ip = ipAddr.toString();

  // Format MAC address
  uint8_t* macRaw = info.wifi_ap_staipassigned.mac;
  char macBuf[18];
  snprintf(macBuf, sizeof(macBuf),
           "%02X:%02X:%02X:%02X:%02X:%02X",
           macRaw[0], macRaw[1], macRaw[2],
           macRaw[3], macRaw[4], macRaw[5]);
  String mac(macBuf);

  // Update device list and redraw
  addDevice(ip, mac);
  redrawDevices();
}

// Event handler: device disconnected from AP
void onStaDisconnected(WiFiEvent_t event, arduino_event_info_t info) {
  // Remove device by MAC and redraw
  removeDeviceByMac(info.wifi_ap_stadisconnected.mac);
  redrawDevices();
}

void setup() {
  // If using external Vext to power OLED, enable:
  pinMode(Vext, OUTPUT);
  digitalWrite(Vext, LOW);
  delay(100);

  // Initialize OLED display
  display.init();
  display.clear();
  display.setContrast(255);
  display.display();

  // Start WiFi Soft-AP
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ssid, password);
  delay(200); // Wait for DHCP server

  // Display AP SSID and IP on OLED
  IPAddress apIP = WiFi.softAPIP();
  display.clear();
  display.setTextAlignment(TEXT_ALIGN_LEFT);
  display.setFont(ArialMT_Plain_10);
  display.drawString(0,  0, "AP SSID:");
  display.drawString(0, 12, ssid);
  display.drawString(0, 24, "AP IP:");
  display.drawString(0, 36, apIP.toString());
  display.display();

  // Register event handlers for station join/leave
  WiFi.onEvent(onStaIpAssigned,   ARDUINO_EVENT_WIFI_AP_STAIPASSIGNED);
  WiFi.onEvent(onStaDisconnected, ARDUINO_EVENT_WIFI_AP_STADISCONNECTED);
}

void loop() {
  // Main loop is empty; all logic handled in event callbacks
}
