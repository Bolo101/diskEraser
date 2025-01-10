#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "disk_erase.h"
#include "disk_partition.h"
#include "disk_format.h"
#include "utils.h"


#define MAX_DISKS 10
#define MAX_DISK_NAME_LEN 50

void list_disks_and_select(char disks[][MAX_DISK_NAME_LEN], int *num_disks) {
    list_disks();
    printf("Enter the disks to erase (comma-separated, e.g., sda,sdb): ");
    char input[256];
    fgets(input, sizeof(input), stdin);
    input[strcspn(input, "\n")] = '\0'; // Remove trailing newline

    char *token = strtok(input, ",");
    *num_disks = 0;
    while (token != NULL && *num_disks < MAX_DISKS) {
        strncpy(disks[*num_disks], token, MAX_DISK_NAME_LEN - 1);
        (*num_disks)++;
        token = strtok(NULL, ",");
    }
}

int confirm_erasure(const char *disk) {
    char confirmation;
    printf("Are you sure you want to securely erase %s? This cannot be undone. (y/n): ", disk);
    while (1) {
        confirmation = getchar();
        while (getchar() != '\n'); // Clear stdin
        if (confirmation == 'y' || confirmation == 'Y') return 1;
        if (confirmation == 'n' || confirmation == 'N') return 0;
        printf("Invalid input. Please enter 'y' or 'n': ");
    }
}

int choose_filesystem(char *fs_choice) {
    printf("Choose a filesystem to format the disks:\n");
    printf("1. NTFS\n2. EXT4\n3. VFAT\n");
    int choice;
    scanf("%d", &choice);
    getchar(); // Consume leftover newline
    switch (choice) {
        case 1: strcpy(fs_choice, "ntfs"); return 1;
        case 2: strcpy(fs_choice, "ext4"); return 1;
        case 3: strcpy(fs_choice, "vfat"); return 1;
        default: printf("Invalid choice.\n"); return 0;
    }
}

void process_disk(const char *disk, const char *fs_choice, int passes) {
    printf("Starting operations on disk: %s\n", disk);

    if (!erase_disk(disk, passes)) {
        printf("Error erasing disk %s. Skipping...\n", disk);
        return;
    }

    if (!partition_disk(disk)) {
        printf("Error partitioning disk %s. Skipping...\n", disk);
        return;
    }

    if (!format_disk(disk, fs_choice)) {
        printf("Error formatting disk %s. Skipping...\n", disk);
        return;
    }

    printf("Completed operations on disk: %s\n", disk);
}

int main(int argc, char *argv[]) {
    if (geteuid() != 0) {
        fprintf(stderr, "This script must be run as root!\n");
        return 1;
    }

    char disks[MAX_DISKS][MAX_DISK_NAME_LEN];
    int num_disks = 0;
    list_disks_and_select(disks, &num_disks);
    if (num_disks == 0) {
        printf("No disks selected. Exiting.\n");
        return 0;
    }

    char fs_choice[10];
    if (!choose_filesystem(fs_choice)) {
        printf("Filesystem selection failed. Exiting.\n");
        return 0;
    }

    int passes = 7;
    printf("Enter the number of random data passes (default: 7): ");
    scanf("%d", &passes);
    getchar(); // Consume leftover newline

    for (int i = 0; i < num_disks; i++) {
        if (confirm_erasure(disks[i])) {
            process_disk(disks[i], fs_choice, passes);
        } else {
            printf("Skipping disk: %s\n", disks[i]);
        }
    }

    printf("All operations completed successfully.\n");
    return 0;
}
