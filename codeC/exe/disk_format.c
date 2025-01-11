#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int format_disk(const char *disk, const char *fs_choice) {
    char command[256];

    if (strcmp(fs_choice, "NTFS") == 0) {
        printf("Formatting disk %s as NTFS...\n", disk);
        snprintf(command, sizeof(command), "format %s /FS:NTFS /Q /Y", disk);
    } else if (strcmp(fs_choice, "FAT32") == 0) {
        printf("Formatting disk %s as FAT32...\n", disk);
        snprintf(command, sizeof(command), "format %s /FS:FAT32 /Q /Y", disk);
    } else {
        printf("Unsupported filesystem: %s\n", fs_choice);
        return 0;
    }

    if (system(command) != 0) {
        printf("Failed to format disk %s.\n", disk);
        return 0;
    }

    printf("Disk %s formatted successfully as %s.\n", disk, fs_choice);
    return 1;
}
