#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "utils.h"

int format_disk(const char *disk, const char *fs_choice) {
    char partition[256];
    snprintf(partition, sizeof(partition), "/dev/%s1", disk); // Assuming first partition

    char command[512];
    if (strcmp(fs_choice, "ntfs") == 0) {
        printf("Formatting %s as NTFS...\n", partition);
        snprintf(command, sizeof(command), "mkfs.ntfs -f %s", partition);
    } else if (strcmp(fs_choice, "ext4") == 0) {
        printf("Formatting %s as EXT4...\n", partition);
        snprintf(command, sizeof(command), "mkfs.ext4 %s", partition);
    } else if (strcmp(fs_choice, "vfat") == 0) {
        printf("Formatting %s as VFAT...\n", partition);
        snprintf(command, sizeof(command), "mkfs.vfat -F 32 %s", partition);
    } else {
        fprintf(stderr, "Unsupported filesystem type: %s\n", fs_choice);
        return 0;
    }

    if (!run_command(command)) {
        fprintf(stderr, "Failed to format partition %s.\n", partition);
        return 0;
    }

    printf("Partition %s formatted successfully as %s.\n", partition, fs_choice);
    return 1;
}
