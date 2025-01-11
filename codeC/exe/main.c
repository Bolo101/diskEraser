#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "disk_erase.h"
#include "disk_partition.h"
#include "disk_format.h"
#include "utils.h"

void select_disk(char *selected_disk, size_t size) {
    list_disks();
    printf("Enter the disk to erase (e.g., C:): ");
    fgets(selected_disk, size, stdin);
    selected_disk[strcspn(selected_disk, "\n")] = 0;  // Remove newline character
}

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
            format_disk(disk, "ntfs");
            break;
        } else if (strcmp(choice, "2") == 0) {
            printf("Formatting disk %s to EXT4...\n", disk);
            format_disk(disk, "ext4");
            break;
        } else if (strcmp(choice, "3") == 0) {
            printf("Formatting disk %s to VFAT...\n", disk);
            format_disk(disk, "vfat");
            break;
        } else {
            printf("Invalid choice. Please try again.\n");
        }
    }
}

int main() {
    char selected_disk[100];
    int passes = 7;

    // Step 1: Select a disk
    select_disk(selected_disk, sizeof(selected_disk));

    if (strlen(selected_disk) == 0) {
        printf("No disk selected. Exiting.\n");
        return 1;
    }

    // Step 2: Erase the selected disk
    printf("Erasing disk %s with %d passes...\n", selected_disk, passes);
    erase_disk(selected_disk, passes);

    // Step 3: Partition the disk
    printf("Partitioning disk %s...\n", selected_disk);
    partition_disk(selected_disk);

    // Step 4: Choose and format the filesystem
    choose_filesystem(selected_disk);

    printf("Operation completed successfully on disk %s.\n", selected_disk);
    return 0;
}
