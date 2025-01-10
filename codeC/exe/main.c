#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "disk_erase.h"
#include "disk_partition.h"
#include "disk_format.h"
#include "utils.h"

void select_disks() {
    list_disks();
    char selected_disks[1024];
    printf("Enter the disk numbers to erase (comma-separated, e.g., 1,2): ");
    fgets(selected_disks, sizeof(selected_disks), stdin);
    selected_disks[strcspn(selected_disks, "\n")] = 0;  // Remove newline character

    char *disk = strtok(selected_disks, ",");
    while (disk != NULL) {
        printf("Erasing disk %s...\n", disk);
        // Here you can call the functions to erase, partition, and format the selected disk
        disk = strtok(NULL, ",");
    }
}

void choose_filesystem() {
    while (1) {
        printf("Choose a filesystem to format the disks:\n");
        printf("1. NTFS\n");
        printf("2. EXT4\n");
        printf("3. VFAT\n");
        char choice[10];
        printf("Enter your choice (1, 2, or 3): ");
        fgets(choice, sizeof(choice), stdin);
        choice[strcspn(choice, "\n")] = 0;  // Remove newline character

        if (strcmp(choice, "1") == 0) {
            format_disk("Disk1", "ntfs");  // Example disk name "Disk1"
            break;
        }
        else if (strcmp(choice, "2") == 0) {
            format_disk("Disk1", "ext4");  // Example disk name "Disk1"
            break;
        }
        else if (strcmp(choice, "3") == 0) {
            format_disk("Disk1", "vfat");  // Example disk name "Disk1"
            break;
        }
        else {
            printf("Invalid choice. Please select a valid option.\n");
        }
    }
}

int main() {
    select_disks();
    choose_filesystem();
    return 0;
}
