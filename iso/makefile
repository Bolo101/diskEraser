# Define variables

SCRIPT_64     := forgeIso64.sh
SCRIPT_32  := forgeIso32.sh

DIR_64     := iso-64-bits
DIR_32     := iso-32-bits

BUILD_DIR_64    := ./iso-64-bits/debian-live-build
BUILD_DIR_32    := ./iso-32-bits/debian-live-build

.PHONY: all 32 all-iso clean help

# Default target: run the script

all:
	cd $(DIR_64) && chmod +x $(SCRIPT_64) && bash $(SCRIPT_64)

32:
	cd $(DIR_32) && chmod +x $(SCRIPT_32) && bash $(SCRIPT_32)

# Build all ISOs

all-iso:
	@echo "Building all ISOs..."
	@$(MAKE) all
	@$(MAKE) 32
	@echo "All ISOs built successfully!"

# Clean target: remove the debian-live-build directory in all folders

clean:
	rm -rf $(BUILD_DIR_64)
	rm -rf $(BUILD_DIR_32)

# Help target

help:
	@echo "Available commands:"
	@echo "  make all     - Build XFCE ISO (64-bit)"
	@echo "  make 32      - Build XFCE ISO (32-bit)"
	@echo "  make all-iso - Build ALL ISOs sequentially"
	@echo "  make clean   - Remove the build directories in all folders"

# Catch-all for invalid commands

.DEFAULT:
	@echo "Invalid command: '$@'"
	@echo ""
	@$(MAKE) help
	@false