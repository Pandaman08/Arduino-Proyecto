#include <iostream>
#include "../../firmware/arduino_secado/arduino_secado.ino"
int main() {
  std::string line;
  while (std::getline(std::cin,line)) {
    if (line=="TEST:SENSOR_ERR") err("SENSOR_DHT");
    else {Serial.input=line+"\n";readSerialCommands();}
    std::cout<<Serial.output<<std::flush;
    Serial.output.clear();
  }
}
