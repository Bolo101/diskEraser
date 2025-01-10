#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>

int run_command(const char *command) {
    int ret = system(command);
    if (ret == -1 || WEXITSTATUS(ret) != 0) {
        fprintf(stderr, "Command failed: %s\n", command);
        return 0;
    }
    return 1;
}

void list_disks() {
    printf("List of available disks:\n");
    const char *command = "lsblk -d -o NAME,SIZE,TYPE";
    if (!run_command(command)) {
        fprintf(stderr, "Failed to list disks. Ensure the program is run with appropriate permissions.\n");
    }
}
