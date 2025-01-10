#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

int partition_disk(const char *disk) {
    char command[256];
    snprintf(command, sizeof(command), "diskpart /s partition_script.txt");

    FILE *script = fopen("partition_script.txt", "w");
    if (!script) {
        printf("Failed to create partition script for disk %s.\n", disk);
        return 0;
    }

    fprintf(script, "select disk %s\n", disk);
    fprintf(script, "clean\n");
    fprintf(script, "create partition primary\n");
    fclose(script);

    if (system(command) != 0) {
        printf("Failed to partition disk %s.\n", disk);
        return 0;
    }

    printf("Disk %s partitioned successfully.\n", disk);
    return 1;
}
