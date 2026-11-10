#pragma once
// Host-only test doubles. The production sketch is compiled unmodified below.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <iomanip>
#include <sstream>
#include <string>
using std::isnan;
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define DHT22 22
#define DEVICE_DISCONNECTED_C -127.0
class String {
  std::string value;
 public:
  String(const char* s):value(s){} String(std::string s):value(s){}
  unsigned int length() const{return value.size();}
  char operator[](unsigned int i) const{return value[i];}
  char charAt(unsigned int i) const{return value[i];}
  bool operator==(const char* s) const{return value==s;}
  bool startsWith(const char* s) const{return value.rfind(s,0)==0;}
  int indexOf(char c,unsigned int start=0) const{auto p=value.find(c,start);return p==std::string::npos?-1:static_cast<int>(p);}
  String substring(unsigned int start) const{return value.substr(std::min<size_t>(start,value.size()));}
  String substring(unsigned int start,unsigned int end) const{return value.substr(start,end-start);}
  void trim(){auto a=value.find_first_not_of(" \t\r\n");auto b=value.find_last_not_of(" \t\r\n");value=a==std::string::npos?"":value.substr(a,b-a+1);}
  void toUpperCase(){std::transform(value.begin(),value.end(),value.begin(),[](unsigned char c){return std::toupper(c);});}
  float toFloat() const{return std::strtof(value.c_str(),nullptr);}
  void toCharArray(char* out,unsigned int size) const{if(size){std::strncpy(out,value.c_str(),size-1);out[size-1]=0;}}
  const char* c_str() const{return value.c_str();}
};
class SerialDouble {
 public:
  std::string input, output;
  void begin(int){}
  int available(){return input.size();}
  int read(){char c=input[0];input.erase(0,1);return c;}
  void print(const char* v){output+=v;}
  void print(const String& v){output+=v.c_str();}
  template<class T> void print(T v){std::ostringstream out;out<<+v;output+=out.str();}
  void print(float v,int precision){std::ostringstream out;out<<std::fixed<<std::setprecision(precision)<<v;output+=out.str();}
  void println(){output+='\n';}
  template<class T>void println(T v){print(v);println();}
};
inline SerialDouble Serial;
inline unsigned long millis(){return 1000;}
inline void digitalWrite(uint8_t,int){}
inline void analogWrite(uint8_t,int){}
inline void pinMode(uint8_t,int){}
class DHT {public:DHT(int,int){} void begin(){} float readTemperature(){return 25;}float readHumidity(){return 60;}};
class OneWire {public:OneWire(int){}};
class DallasTemperature {public:DallasTemperature(OneWire*){}void begin(){}void setResolution(int){}void setWaitForConversion(bool){}void requestTemperatures(){}float getTempCByIndex(int){return 30;}};
class LiquidCrystal_I2C {public:LiquidCrystal_I2C(int,int,int){}void init(){}void backlight(){}void clear(){}void setCursor(int,int){}template<class... T>void print(T...){} };
