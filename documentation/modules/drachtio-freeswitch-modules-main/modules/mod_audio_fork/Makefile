# Makefile for mod_audio_fork

# FreeSWITCH paths
FS_INCLUDES=/usr/local/freeswitch/include/freeswitch
FS_MODULES=/usr/local/freeswitch/mod

# Compiler flags
CXX=g++
CC=gcc
CFLAGS=-fPIC -O2 -Wall `pkg-config --cflags libwebsockets freeswitch`
CXXFLAGS=$(CFLAGS) -std=c++11
LDFLAGS=-shared `pkg-config --libs libwebsockets freeswitch`

# Source files
C_SOURCES=mod_audio_fork.c
CPP_SOURCES=audio_pipe.cpp lws_glue.cpp parser.cpp
OBJECTS=$(C_SOURCES:.c=.o) $(CPP_SOURCES:.cpp=.o)

# Target
TARGET=mod_audio_fork.so

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CXX) $(LDFLAGS) -o $@ $^

%.o: %.c
	$(CC) $(CFLAGS) -I$(FS_INCLUDES) -c $<

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -I$(FS_INCLUDES) -c $<

install: $(TARGET)
	cp $(TARGET) $(FS_MODULES)/

clean:
	rm -f $(OBJECTS) $(TARGET)

.PHONY: all install clean
