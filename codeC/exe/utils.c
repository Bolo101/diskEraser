#include <stdio.h>
#include <stdlib.h>
#include <windows.h>  // For sleep function on Windows

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

// Function to display a progress bar
void display_progress(const char *message, int duration) {
    printf("%s\n", message);
    for (int i = 0; i <= 100; i += 10) {
        printf("\r[%-10s] %d%%", "##########" + (10 - i / 10), i);
        fflush(stdout);
        Sleep(duration * 1000);  // Sleep for 'duration' seconds
    }
    printf("\n");
}
