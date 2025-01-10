#include <stdio.h>
#include <stdlib.h>
#include <windows.h>
#include <time.h>

void display_progress_bar(unsigned long long progress, unsigned long long total, int pass_num, const char *device) {
    int bar_length = 50;
    float percent = (float)(progress) / total * 100;
    int filled_length = (int)(bar_length * progress / total);
    char bar[51];
    memset(bar, '=', filled_length);
    memset(bar + filled_length, '-', bar_length - filled_length);
    bar[bar_length] = '\0';
    printf("\rPass %d: [%s] %.2f%% %s", pass_num, bar, percent, device);
    fflush(stdout);
}

void write_random_data(const char *device, int passes) {
    HANDLE hDevice;
    DWORD bytesWritten;
    unsigned char buffer[4096];  // 4 KB buffer

    // Open the raw disk device
    hDevice = CreateFile(device, GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL);
    if (hDevice == INVALID_HANDLE_VALUE) {
        printf("Failed to open disk %s\n", device);
        return;
    }

    // Seed the random number generator
    srand((unsigned int)time(NULL));

    unsigned long long written = 0;
    unsigned long long total_size = 1000000000; // Estimate size in bytes for demonstration
    for (int pass = 1; pass <= passes; ++pass) {
        printf("\nWriting random data pass %d to %s...\n", pass, device);
        while (written < total_size) {
            // Fill the buffer with random data
            for (int i = 0; i < sizeof(buffer); ++i) {
                buffer[i] = rand() % 256;
            }
            WriteFile(hDevice, buffer, sizeof(buffer), &bytesWritten, NULL);
            written += bytesWritten;
            display_progress_bar(written, total_size, pass, device);
        }
        written = 0; // Reset written for next pass
    }

    CloseHandle(hDevice);
}

void write_zero_data(const char *device) {
    HANDLE hDevice;
    DWORD bytesWritten;
    unsigned char buffer[4096] = {0};  // 4 KB buffer filled with zeros

    hDevice = CreateFile(device, GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL);
    if (hDevice == INVALID_HANDLE_VALUE) {
        printf("Failed to open disk %s\n", device);
        return;
    }

    unsigned long long written = 0;
    unsigned long long total_size = 1000000000; // Estimate size in bytes for demonstration
    while (written < total_size) {
        WriteFile(hDevice, buffer, sizeof(buffer), &bytesWritten, NULL);
        written += bytesWritten;
        display_progress_bar(written, total_size, 0, device);
    }

    CloseHandle(hDevice);
}

void erase_disk(const char *device, int passes) {
    printf("Erasing %s with multiple random data passes and a final zero pass...\n", device);

    write_random_data(device, passes);
    write_zero_data(device);

    printf("Disk %s successfully erased with random data and zeros.\n", device);
}
