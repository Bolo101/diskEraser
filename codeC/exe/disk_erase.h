#ifndef DISK_ERASE_H
#define DISK_ERASE_H

#include <stdio.h>
#include <stdlib.h>
#include <windows.h>

void write_random_data(const char *device, int passes);
void write_zero_data(const char *device);
void erase_disk(const char *disk, int passes);

#endif /* DISK_ERASE_H */
