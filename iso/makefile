# Define variables

SCRIPT_XFCE     := forgeIsoXfce.sh
SCRIPT_KDE      := forgeIsoKde.sh
SCRIPT_XFCE_32  := forgeIsoXfce32.sh
SCRIPT_KDE_32   := forgeIsoKde32.sh

DIR_XFCE_64     := xfce-64-bits
DIR_KDE_64      := kde-64-bits
DIR_XFCE_32     := xfce-32-bits
DIR_KDE_32      := kde-32-bits

BUILD_DIR_XFCE_64    := ./xfce-64-bits/debian-live-build
BUILD_DIR_KDE_64     := ./kde-64-bits/debian-live-build
BUILD_DIR_XFCE_32    := ./xfce-32-bits/debian-live-build
BUILD_DIR_KDE_32     := ./kde-32-bits/debian-live-build

.PHONY: all kde xfce32 kde32 all-iso clean help

# Default target: run the script

all:
	cd $(DIR_XFCE_64) && chmod +x $(SCRIPT_XFCE) && bash $(SCRIPT_XFCE)

kde:
	cd $(DIR_KDE_64) && chmod +x $(SCRIPT_KDE) && bash $(SCRIPT_KDE)

xfce32:
	cd $(DIR_XFCE_32) && chmod +x $(SCRIPT_XFCE_32) && bash $(SCRIPT_XFCE_32)

kde32:
	cd $(DIR_KDE_32) && chmod +x $(SCRIPT_KDE_32) && bash $(SCRIPT_KDE_32)

# Build all ISOs

all-iso:
	@echo "Building all ISOs..."
	@$(MAKE) all
	@$(MAKE) kde
	@$(MAKE) xfce32
	@$(MAKE) kde32
	@echo "All ISOs built successfully!"

# Clean target: remove the debian-live-build directory in all folders

clean:
	rm -rf $(BUILD_DIR_XFCE_64)
	rm -rf $(BUILD_DIR_KDE_64)
	rm -rf $(BUILD_DIR_XFCE_32)
	rm -rf $(BUILD_DIR_KDE_32)

# Help target

help:
	@echo "Available commands:"
	@echo "  make all     - Build XFCE ISO (64-bit)"
	@echo "  make kde     - Build KDE ISO (64-bit)"
	@echo "  make xfce32  - Build XFCE ISO (32-bit)"
	@echo "  make kde32   - Build KDE ISO (32-bit)"
	@echo "  make all-iso - Build ALL ISOs sequentially"
	@echo "  make clean   - Remove the build directories in all folders"

# Catch-all for invalid commands

.DEFAULT:
	@echo "Invalid command: '$@'"
	@echo ""
	@$(MAKE) help
	@false