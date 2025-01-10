#include <stdio.h>
#include <stdlib.h>

int run_command(const char *command) {
    int ret = system(command);
    if (ret != 0) {
        printf("Command failed: %s\n", command);
        return 0;
    }
    return 1;
}

void list_disks() {
    printf("List of available disks:\n");
    const char *command = "wmic diskdrive list brief";
    if (!run_command(command)) {
        printf("Failed to list disks. Ensure the program is run with appropriate permissions.\n");
    }
}
