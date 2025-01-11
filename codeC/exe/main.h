#ifndef MAIN_H
#define MAIN_H

#include <stdio.h>

// Function to select a disk for erasure
void select_disk(char *selected_disk, size_t size);

// Function to choose the filesystem type and format the disk
void choose_filesystem(const char *disk);

#endif // MAIN_H
