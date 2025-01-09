#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "utils.h"

int partition_disk(const char *disk) {
    char device[256];
    snprintf(device, sizeof(device), "/dev/%s", disk);

    printf("Partitioning disk %s...\n", disk);

    char command[512];

    // Create a GPT partition table
    snprintf(command, sizeof(command), "parted %s --script mklabel gpt", device);
    if (!run_command(command)) {
        fprintf(stderr, "Failed to create GPT partition table on %s.\n", device);
        return 0;
    }

    // Create a primary partition spanning the entire disk
    snprintf(command, sizeof(command), "parted %s --script mkpart primary 0%% 100%%", device);
    if (!run_command(command)) {
        fprintf(stderr, "Failed to create primary partition on %s.\n", device);
        return 0;
    }

    printf("Disk %s partitioned successfully.\n", disk);
    return 1;
}
