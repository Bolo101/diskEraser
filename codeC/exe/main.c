#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h> // For sleep function on POSIX
#include "disk_erase.h"
#include "disk_partition.h"
#include "disk_format.h"
#include "utils.h"

// Function to display a progress bar
void display_progress(const char *message, int duration) {
    printf("%s\n", message);
    for (int i = 0; i <= 100; i += 10) {
        printf("\r[%-10s] %d%%", "##########" + (10 - i / 10), i);
        fflush(stdout);
        sleep(1);  // Simulates work being done (use _sleep on Windows)
    }
    printf("\n");
}

// Function to select a single disk and return its identifier
void select_disk(char *selected_disk, size_t size) {
    list_disks();
    printf("Enter the disk to erase (e.g., C:): ");
    fgets(selected_disk, size, stdin);
    selected_disk[strcspn(selected_disk, "\n")] = 0;  // Remove newline character
}

// Function to allow the user to choose a filesystem
void choose_filesystem(const char *disk) {
    if (disk == NULL || strlen(disk) == 0) {
        printf("Error: No valid disk provided.\n");
        return;
    }

    printf("Available Filesystems:\n");
    printf("1. NTFS\n");
    printf("2. EXT4\n");
    printf("3. VFAT\n");

    char choice[10];
    while (1) {
        printf("Enter your choice (1, 2, or 3): ");
        fgets(choice, sizeof(choice), stdin);
        choice[strcspn(choice, "\n")] = 0;  // Remove newline character

        if (strcmp(choice, "1") == 0) {
            printf("Formatting disk %s to NTFS...\n", disk);
            format_disk(disk, "ntfs");  // Call format_disk
            break;
        } else if (strcmp(choice, "2") == 0) {
            printf("Formatting disk %s to EXT4...\n", disk);
            format_disk(disk, "ext4");  // Call format_disk
            break;
        } else if (strcmp(choice, "3") == 0) {
            printf("Formatting disk %s to VFAT...\n", disk);
            format_disk(disk, "vfat");  // Call format_disk
            break;
        } else {
            printf("Invalid choice. Please try again.\n");
        }
    }
}

int main() {
    char selected_disk[100];  // Buffer to hold the selected disk
    int passes = 7;  // Default number of overwrite passes for secure erasure

    // Step 1: Select a disk
    select_disk(selected_disk, sizeof(selected_disk));

    if (strlen(selected_disk) == 0) {
        printf("No disk selected. Exiting.\n");
        return 1;
    }

    // Step 2: Erase the selected disk with progress display
    printf("Erasing disk %s with %d passes...\n", selected_disk, passes);
    display_progress("Erasing in progress:", 10);  // Progress bar for disk erasure
    erase_disk(selected_disk, passes);  // Pass both the disk and the number of passes

    // Step 3: Partition the disk (if needed)
    printf("Partitioning disk %s...\n", selected_disk);
    display_progress("Partitioning in progress:", 5);  // Progress bar for partitioning
    partition_disk(selected_disk);

    // Step 4: Choose and format the filesystem
    choose_filesystem(selected_disk);  // Pass the disk as an argument

    printf("Operation completed successfully on disk %s.\n", selected_disk);
    return 0;
}
