#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int format_disk(const char *fs_choice) {
    const char *partition = "C:"; // Change based on the partition you want to format
    char command[256];

    if (strcmp(fs_choice, "NTFS") == 0) {
        printf("Formatting %s as NTFS...\n", partition);
        snprintf(command, sizeof(command), "format %s /FS:NTFS /Q /Y", partition);
    } else if (strcmp(fs_choice, "FAT32") == 0) {
        printf("Formatting %s as FAT32...\n", partition);
        snprintf(command, sizeof(command), "format %s /FS:FAT32 /Q /Y", partition);
    } else {
        printf("Unsupported filesystem: %s\n", fs_choice);
        return 0;
    }

    if (system(command) != 0) {
        printf("Failed to format partition %s.\n", partition);
        return 0;
    }

    printf("Partition %s formatted successfully as %s.\n", partition, fs_choice);
    return 1;
}
