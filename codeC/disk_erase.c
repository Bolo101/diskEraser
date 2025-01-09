#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <time.h>

void display_progress_bar(off_t progress, off_t total, int pass_num, const char *device) {
    int bar_length = 50;
    int filled_length = (int)((double)progress / total * bar_length);
    printf("\rPass %d [%.*s%.*s] %.2f%% %s",
           pass_num,
           filled_length, "==================================================",
           bar_length - filled_length, "--------------------------------------------------",
           (double)progress / total * 100, device);
    fflush(stdout);
}

int write_random_data(const char *device, int passes) {
    int fd = open(device, O_WRONLY);
    if (fd == -1) {
        perror("Failed to open device");
        return 0;
    }

    off_t disk_size = lseek(fd, 0, SEEK_END);
    if (disk_size == -1) {
        perror("Failed to determine disk size");
        close(fd);
        return 0;
    }
    lseek(fd, 0, SEEK_SET);

    char *buffer = malloc(4096);
    if (!buffer) {
        perror("Memory allocation failed");
        close(fd);
        return 0;
    }

    for (int pass = 1; pass <= passes; pass++) {
        printf("\nWriting random data pass %d to %s...\n", pass, device);
        off_t written = 0;
        while (written < disk_size) {
            size_t to_write = (disk_size - written > 4096) ? 4096 : (disk_size - written);
            for (size_t i = 0; i < to_write; i++) {
                buffer[i] = rand() % 256;
            }
            if (write(fd, buffer, to_write) == -1) {
                perror("Write failed");
                free(buffer);
                close(fd);
                return 0;
            }
            written += to_write;
            display_progress_bar(written, disk_size, pass, device);
        }
        lseek(fd, 0, SEEK_SET);
    }

    printf("\n");
    free(buffer);
    close(fd);
    return 1;
}

int erase_disk(const char *disk, int passes) {
    char device[256];
    snprintf(device, sizeof(device), "/dev/%s", disk);
    return write_random_data(device, passes);
}
