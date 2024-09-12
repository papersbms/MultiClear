#include <ESP32Servo.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <deque>

// Servo control
Servo myServo;
int servoPin = 5;

// FSR sensor
int fsrPin = 32;
int fsrReading = 0;

// BLE service and characteristic UUIDs
#define SERVICE_UUID        ""
#define CHARACTERISTIC_UUID ""

BLECharacteristic *pCharacteristic;
BLEServer *pServer;
bool deviceConnected = false;
bool bluetoothReceivedG = false;
std::deque<char> commandStack;

// Timer to track 15 seconds
unsigned long lastCommandTime = 0;
bool isWaitingForBluetooth = false;
bool commandInterrupt = false;

// Callback for when a client connects/disconnects
class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
      Serial.println("Client connected");
    };

    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
      Serial.println("Client disconnected");

      // Restart advertising when client disconnects
      pServer->startAdvertising();
      Serial.println("Advertising restarted");
    }
};

// Callback for BLE characteristic writes
class MyCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      std::string value = pCharacteristic->getValue();
      
      if (value.length() > 0) {
        for (int i = 0; i < value.length(); i++) {
          char receivedChar = value[i];
          Serial.print("Received from Bluetooth: ");
          Serial.println(receivedChar);

          if (receivedChar == 'g') {
            bluetoothReceivedG = true;  // Mark that 'g' was received
          }
        }
      }
    }
};

// Function to handle incoming serial data from the voice module
void VoiceMode() {
  if (Serial.available() > 0) {
    Serial.println("Data available from voice module!");  // Debugging: show if data is available
    char incomingByte = Serial.read();
    Serial.print("Received from voice module: ");
    Serial.println(incomingByte);  // Print the received character for debugging

    if (incomingByte == 'R') {
      Serial.println("Received R from voice module, reversing motor...");
      controlMotorReverse();
      commandInterrupt = true;  // Set interrupt flag to true

      auto it = std::find(commandStack.begin(), commandStack.end(), 'G');
      if (it != commandStack.end()) {
        Serial.println("Releasing G from the stack...");
        commandStack.erase(it);
      }
    } 
    else if (incomingByte == 'S') {
      Serial.println("Received S from voice module, stopping motor...");
      controlMotorStop();
      commandInterrupt = true;  // Set interrupt flag to true
    }
    else if (incomingByte == 'G') {
      Serial.println("Received G from voice module, pushing to stack...");
      commandStack.push_back('G');
      lastCommandTime = millis();  // Start the timer
      isWaitingForBluetooth = true;
    }
  }
}

// Function to control motor forward
void controlMotorForward() {
  Serial.println("Motor forward...");
  myServo.write(60);  // Rotate the motor forward
}

// Function to control motor reverse
void controlMotorReverse() {
  Serial.println("Motor reverse...");
  myServo.write(120);  // Rotate the motor reverse
}

// Function to stop the motor
void controlMotorStop() {
  Serial.println("Motor stop...");
  myServo.write(90);  // Set motor to neutral position (90 degrees)
}

// Function to check if 15 seconds have passed since receiving 'G'
void checkTimer() {
  if (isWaitingForBluetooth) {
    if (bluetoothReceivedG) {
      controlMotorForward();
      isWaitingForBluetooth = false;
      bluetoothReceivedG = false;
    } else if (millis() - lastCommandTime >= 15000) {  // 15 seconds timeout
      Serial.println("15 seconds passed without receiving 'g'.");
      controlMotorForward();
      isWaitingForBluetooth = false;
    }
  }
}

// Function to monitor the FSR sensor and trigger motor forward if needed
void checkFSRSensor() {
  // If a command interrupt ('R' or 'S') is active, skip the FSR check
  if (commandInterrupt) {
    Serial.println("Command interrupt detected, skipping FSR check...");
    commandInterrupt = false;  // Reset the flag
    return;
  }

  fsrReading = analogRead(fsrPin);
  Serial.print("FSR reading: ");
  Serial.println(fsrReading);

  if (fsrReading > 5) {
    Serial.println("FSR reading above threshold, motor forward...");
    controlMotorForward();
  }
}

void setup() {
  Serial.begin(115200);
  myServo.attach(servoPin);
  controlMotorStop();

  pinMode(fsrPin, INPUT);

  // Initialize BLE
  BLEDevice::init("ESP32_Motor_Control");
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  BLEService *pService = pServer->createService(SERVICE_UUID);
  pCharacteristic = pService->createCharacteristic(
                      CHARACTERISTIC_UUID,
                      BLECharacteristic::PROPERTY_WRITE   // Enable writing to characteristic
                    );

  // Set the callback for characteristic writes
  pCharacteristic->setCallbacks(new MyCallbacks());

  // Start the service and start advertising
  pService->start();
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->start();

  Serial.println("Waiting for a client to connect...");
}

void loop() {
  VoiceMode();  // Continuously check for incoming voice commands
  checkTimer();  // Check if 15 seconds have passed for 'G' command
  checkFSRSensor();  // Check FSR sensor values to trigger motor forward
}
