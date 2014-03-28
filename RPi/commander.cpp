/*
 Copyright (C) 2011 J. Coliz <maniacbug@ymail.com>

 This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License
 version 2 as published by the Free Software Foundation.
 */

#include <cstdlib>
#include <iostream>
#include <string>
#include <sstream>

#include "../RF24.h"

//
// Hardware configuration
//

// Set up nRF24L01 radio on SPI bus

RF24 radio("/dev/spidev0.0", 8000000, 25);  //spi device, speed and CSN,only CSN is NEEDED in RPI

//
// Topology
//

// Radio pipe addresses for the 2 nodes to communicate.
const uint64_t pipes[2] = { 0xF0F0F0F0E1LL, 0xF0F0F0F0D2LL };

const int PAYLOAD = 32; // bytes
const int TIMEOUT = 500; // ms

void setup(void)
{
  //
  // Setup and configure rf radio
  //

  radio.begin();

  // optionally, increase the delay between retries & # of retries
  radio.setRetries(20, 20);

  radio.setPayloadSize(PAYLOAD);
  // TODO: set other crap (data rate, spi rate, etc)
  radio.setDataRate(RF24_2MBPS);
  radio.setChannel(0x4c);
  radio.setPALevel(RF24_PA_MAX);

  //
  // Open pipes to other nodes for communication
  //

  // TODO: configure this to match correctly on the Arduino
  radio.openWritingPipe(pipes[0]);
  radio.openReadingPipe(1, pipes[1]);

  //
  // Start listening
  //

  radio.startListening();

  //
  // Dump the configuration of the rf unit for debugging
  //

  //radio.printDetails();
  std::cerr << "OK Listening for commands" << std::endl;
}

void loop(void)
{
  // Read the current command from the user
  std::string command;
  std::getline(std::cin, command);

  std::cerr << "Got '" << command << "'.\n";

  // Split the command on spaces
  std::stringstream ss("0 ");
  ss << command;
  ss << " 0";
  unsigned char bytes[PAYLOAD];
  int buf = 0;

  // Read each space-separated value into an integer and put it into bytes
  int used = 0;
  for (int i = 0; i < PAYLOAD && ss >> buf; i++) {
    bytes[i] = (unsigned char)buf;
    used = i;
  }

  std::cerr << "Read " << used << " bytes from stdin." << std::endl;

  // Stop listening so we can talk.
  radio.stopListening();

  // Send the bytes 
  std::cerr << "Sending bytes: ";
  for (int i = 0; i < used; i++) {
    std::cerr << (int)bytes[i] << " ";
  }
  std::cerr << std::endl;

  bool ok = radio.write( bytes, used );
  
  if (ok) {
    std::cerr << "ok..." << std::endl;
  } else {
    std::cerr << "failed..." << std::endl;
    // TODO: retry!
  }

  // Now, continue listening
  radio.startListening();

  // Wait here until we get a response, or timeout (500ms)
  unsigned long started_waiting_at = __millis();
  bool timeout = false;
  while ( !radio.available() && ! timeout ) {
    __msleep(5); //add a small delay to let radio.available to check payload
    timeout = ((__millis() - started_waiting_at) > TIMEOUT);
  }

  // Describe the results
  if (timeout) {
    std::cerr << "response timed out..." << std::endl;
    // TODO: retry!
  } else {
    // Grab the response, compare, and send to debugging spew
    radio.read( bytes, PAYLOAD ); // TODO: replace PAYLOAD

    // Print the bytes
    for (int i = 0; i < PAYLOAD; i++) {
      std::cout << (unsigned int)bytes[i] << " ";
    }
    std::cout << std::endl;
  }
}

int main(int argc, char** argv)
{
  setup();
  while(1)
    loop();

  return 0;
}


// vim:cin:ai:sts=2 sw=2 ft=cpp
