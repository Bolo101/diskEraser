# Define variables

SCRIPT_XFCE     := ./forgeIsoXfce.sh
SCRIPT_KDE      := ./forgeIsoKde.sh
SCRIPT_XFCE_32  := ./forgeIsoXfce32.sh
SCRIPT_KDE_32   := ./forgeIsoKde32.sh

BUILD_DIR := $(shell pwd)/debian-live-build

.PHONY: all kde xfce32 kde32 clean help

# Default target: run the script

all:
	 chmod +x $(SCRIPT_XFCE)
	 bash $(SCRIPT_XFCE)

kde:
	 chmod +x $(SCRIPT_KDE)
	 bash $(SCRIPT_KDE)

xfce32:
	 chmod +x $(SCRIPT_XFCE_32)
	 bash $(SCRIPT_XFCE_32)

kde32:
	 chmod +x $(SCRIPT_KDE_32)
	 bash $(SCRIPT_KDE_32)

# Clean target: remove the debian-live-build directory

clean:
	 rm -rf $(BUILD_DIR)

# Help target

help:
	 @echo "Available commands:"
	 @echo "  make all    - Build XFCE ISO (64-bit)"
	 @echo "  make kde    - Build KDE ISO (64-bit)"
	 @echo "  make xfce32 - Build XFCE ISO (32-bit)"
	 @echo "  make kde32  - Build KDE ISO (32-bit)"
	 @echo "  make clean  - Remove the build directory"

# Catch-all for invalid commands

.DEFAULT:
	 @echo "Invalid command: '$@'"
	 @echo ""
	 @$(MAKE) help
	 @false