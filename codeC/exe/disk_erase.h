#ifndef DISK_ERASE_H
#define DISK_ERASE_H

#include <stdio.h>

// Function to display progress bar for erasure
void display_progress_bar(unsigned long long progress, unsigned long long total, int pass_num, const char *device);

// Function to write random data to the disk
void write_random_data(const char *device, int passes);

// Function to write zero data to the disk
void write_zero_data(const char *device);

// Function to erase the disk
void erase_disk(const char *disk, int passes);

#endif // DISK_ERASE_H
